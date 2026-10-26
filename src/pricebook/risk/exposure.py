"""Exposure profiles — the pluggable half of XVA (L5).

`EE(tᵢ)`, the expected positive exposure of a trade at a future time, is the input every XVA integral
consumes. **The exposure METHOD is pluggable; the XVA atoms that consume it are not** (§3d) — so an
MC exposure engine, when it lands, feeds the *same* `cva` atom and the two cannot drift into two CVA
definitions. That is why this module returns a plain profile — `((date, EE), ...)` — rather than a
CVA number.

**Slice 1's method is the swaption approximation.** The standard physical-exposure result: the
expected positive exposure of a swap at `tᵢ` **is** the value of a physical-settled swaption expiring
at `tᵢ` on the remaining leg. So `EE(tᵢ)` is the pricer the swaption cluster already oracled, composed
rather than re-derived — and the exposure inherits that cluster's oracles for free.

Provenance:
  quarry: quarry/pricebook/models/mc_exposure.py (the MC exposure method — NOT crossed here; it is
          the general-exposure slice, which feeds this same atom)
  source: Gregory, "Counterparty Credit Risk and Credit Value Adjustment" Ch. 8 (the swaption
          approximation to swap EPE); Brigo-Morini-Pallavicini
  oracle: one point per schedule interval (a count); the last point is exactly 0; the profile decays;
          a failed point propagates as a value rather than counting as zero exposure
  slice:  cva-analytic (B7 slice 1)
"""

from __future__ import annotations

from datetime import date

from pricebook.engine.registry import dispatch as price
from pricebook.foundation.results import PricingFailure
from pricebook.foundation.schedule import future_periods
from pricebook.models.protocols import CalibratedModel
from pricebook.products.option import OptionType, Swaption
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap

#: An exposure profile: `EE` at each future time, ascending. The shape every XVA atom consumes.
ExposureProfile = tuple[tuple[date, float], ...]


def swaption_exposure_profile(
    swap: VanillaSwap, model: CalibratedModel
) -> ExposureProfile | PricingFailure:
    """`EE(tᵢ)` at each of `swap`'s own schedule points, each priced as a physical swaption on the
    remaining leg.

    **Direction is derived, never a knob.** `VanillaSwap`'s PV is the fixed-rate PAYER's, so a
    positive notional is a payer and its positive exposure is a **payer** swaption (a CALL on the
    swap rate); a negative notional is a receiver, hence a PUT. The sub-swap is built on
    `abs(notional)` so the option PV is the exposure itself rather than its negation.

    The final point is exactly `0.0`: at maturity no leg remains, so there is nothing to be exposed
    to. A profile that carried the full exposure to the end would overstate every XVA built on it."""
    periods = swap.fixed_leg.schedule.periods
    if not periods:
        return ()
    kind = OptionType.CALL if swap.notional >= 0.0 else OptionType.PUT
    out: list[tuple[date, float]] = []
    for p in periods:
        expiry = p.accrual_end
        remaining_fixed = future_periods(swap.fixed_leg.schedule, expiry)
        if not remaining_fixed.periods:
            out.append((expiry, 0.0))
            continue
        sub = VanillaSwap(
            abs(swap.notional),
            swap.currency,
            FixedLeg(remaining_fixed, swap.fixed_leg.day_count, swap.fixed_leg.rate),
            FloatLeg(
                future_periods(swap.float_leg.schedule, expiry),
                swap.float_leg.day_count,
                swap.float_leg.index,
            ),
        )
        priced = price(Swaption(sub, expiry, kind), model)
        if isinstance(priced, PricingFailure):
            # a point that cannot be priced is NOT zero exposure — a smaller, plausible-looking
            # charge is the worst outcome here, so the failure propagates (invariant 4)
            return PricingFailure(f"exposure at {expiry.isoformat()}: {priced.reason}")
        out.append((expiry, priced.pv.amount))
    return tuple(out)
