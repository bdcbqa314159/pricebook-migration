"""The CDS engine — mark a vanilla single-name CDS (L4).

    PV(bought protection) = N · [ protection_leg − spread · risky_annuity ]

composing **the same two atoms the slice-1 bootstrap fitted with** (§3d). That is the whole point of
having built them in the calibration slice: calibrate-to-par-spread and price-to-zero are then one
fact, not two implementations that happen to agree. The rates `rpv01` lesson, in credit, before it
could bite — and the reason the oracle is an **off-par closed form**: a par CDS is worth zero, so a
par-only test telescopes and a divergent annuity would be invisible.

Provenance:
  quarry: quarry/pricebook/credit/cds.py (`premium_leg_pv`/`protection_leg_pv` conventions — mined
          for content; the shape is ng's, composing shared atoms rather than private loops)
  source: ISDA Standard CDS Model; O'Kane (2008) "Modelling Single-name and Multi-name Credit
          Derivatives" Ch. 5-6
  oracle: off-par flat-hazard mark vs the analytic PV (non-telescoping); every bootstrapped pillar
          marks to zero; the seasoned accrued/clean decomposition
  slice:  credit-cds-mark (B6 slice 2)
"""

from __future__ import annotations

from pricebook.foundation import Accrual, Money
from pricebook.foundation.numerics import IntegrationConfig
from pricebook.foundation.results import PricingFailure, PricingResult
from pricebook.foundation.schedule import future_periods
from pricebook.engine.registry import register
from pricebook.market.building_blocks import protection_leg, risky_annuity
from pricebook.models.protocols import CalibratedModel
from pricebook.products.credit import CDS


@register(CDS)
def price_cds(
    cds: CDS, model: CalibratedModel, numerics: IntegrationConfig | None = None
) -> PricingResult | PricingFailure:
    """Mark the CDS. Requires an `IntegrationConfig` — the protection leg is an integral and a
    guessed grid is the hidden reproducibility knob invariant 5 forbids.

    **Invariant 6** — only FUTURE premium periods are discounted; periods that already paid are the
    L6 shell's realized cash, never re-valued here. The current period, if one is in progress, is
    earned-but-unpaid: it is reported as `accrued` (negative for bought protection, since the buyer
    *owes* it) and `clean = pv − accrued`."""
    if numerics is None:
        return PricingFailure(
            "a CDS mark needs an explicit integration config (its protection leg is an integral); "
            "a guessed grid is a hidden reproducibility knob (invariant 5)"
        )
    currency = cds.notional.currency
    vd = model.market.valuation_date
    schedule = cds.premium.schedule
    maturity = schedule.periods[-1].accrual_end
    if maturity <= vd:  # nothing left to protect; the realized leg is the L6 shell's
        return PricingResult(pv=Money(0.0, currency))

    try:
        discount = model.market.curves.discount(currency)
        survival = model.market.curves.survival(cds.entity)
    except (KeyError, ValueError, NotImplementedError) as exc:
        return PricingFailure(f"CDS mark: {exc}")

    future = future_periods(schedule, vd)
    if not future.periods:
        return PricingResult(pv=Money(0.0, currency))

    # protection runs from today (or inception, if forward-starting) to maturity: the buyer is
    # protected over the REMAINING life only — invariant 6 applied to the contingent leg
    protection_start = max(vd, schedule.periods[0].accrual_start)
    # The protection window's day count is the TIME BASIS of the integration grid, not an accrual
    # convention — so it must be the survival curve's own measure, which is what the slice-1
    # bootstrap integrates over. Taking `cds.premium.day_count` here instead (ACT/360 against the
    # curve's ACT/365F) changes the step count and makes the bootstrap's par CDS mark non-zero:
    # the §3d divergence this slice exists to prevent, caught by the par-to-zero oracle.
    basis = getattr(getattr(survival, "measure", None), "day_count", cds.premium.day_count)
    try:
        protection = protection_leg(
            Accrual(protection_start, maturity, basis),
            cds.recovery,
            discount,
            survival,
            numerics.steps_per_year,
        )
        premium = cds.premium.spread * risky_annuity(
            future, cds.premium.day_count, discount, survival
        )
    except (ValueError, KeyError, ZeroDivisionError) as exc:
        return PricingFailure(f"CDS mark: {exc}")

    notional = cds.notional.amount
    pv = notional * (protection - premium)
    accrued = _accrued(cds, vd, discount, survival, numerics)
    return PricingResult(
        pv=Money(pv, currency),
        accrued=None if accrued is None else Money(notional * accrued, currency),
    )


def _accrued(cds: CDS, vd, discount, survival, numerics: IntegrationConfig) -> float | None:
    """The earned-but-unpaid premium of the period in progress, per unit notional, NEGATIVE for
    bought protection — the buyer owes it. `None` when no period is in progress (invariant 6:
    clean/dirty and accrued are explicit value concepts, not by-products).

    The accrued is the *premium accrued to today*, undiscounted: it is cash owed now, not a future
    flow. It is survival-unweighted for the same reason — the entity has not defaulted, which is
    the state we are in."""
    for p in cds.premium.schedule.periods:
        # STRICTLY inside: a period starting exactly today has accrued nothing, and `Accrual`
        # rightly refuses a zero-length window
        if p.accrual_start < vd < p.accrual_end:
            tau = Accrual(p.accrual_start, vd, cds.premium.day_count).year_fraction()
            return -cds.premium.spread * tau
    return None
