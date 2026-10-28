"""Linear (swap) pricer — registered behind the L4 engine registry.

`price_swap` composes the SAME `rpv01`/`float_leg_pv` building blocks the calibrator uses
(§3d), reaching the curves only through `model.market` (A1). It is registered for
`VanillaSwap` and reached via the registry's `dispatch` (re-exported here as `price`, the
public entry). PV is the fixed-rate PAYER's: `N·(float − rate·annuity)`, zero at par.
Failure is a value (invariant 4).

Provenance:
  quarry: quarry/pricebook/pricing/ (swap engine)
  source: CLAUDE.md §2 (stateless engine, A1) · §3d (shared atoms); §1 (registry dispatch)
  oracle: EURIBOR swap → zero NPV dual-curve to 1e-9; DV01 analytic vs finite-diff to 1e-6
  slice:  cash-instruments (T1 slice 3, Step A — swap pricer moved behind the registry, body unchanged)
"""

from __future__ import annotations

from pricebook.engine.registry import dispatch as price
from pricebook.engine.registry import register
from pricebook.engine.seasoned import (
    current_period_failure,
    current_period_float_rate,
    split_current_period,
)
from collections.abc import Sequence

from pricebook.foundation import (
    Accrual,
    Money,
    PricingFailure,
    PricingResult,
    SchedulePeriod,
    future_periods,
)
from pricebook.market.building_blocks import weighted_annuity, weighted_float_leg_pv
from pricebook.models.protocols import CalibratedModel
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap


def _notionals_for(
    leg: FixedLeg | FloatLeg, priced: Sequence[SchedulePeriod], scalar: float
) -> tuple[float, ...]:
    """The notionals weighting `priced`, which is the leg's schedule after `future_periods` has
    dropped the historical ones (invariant 6) — so the leg's schedule and the priced schedule
    are DIFFERENT lengths, and the notionals must follow the periods rather than their index.

    Keyed on `accrual_start`: lining a notional schedule up positionally against a filtered
    schedule is exactly how an amortiser silently prices on the wrong rung of its own ladder,
    which no par-swap oracle would catch (a flat schedule slides onto itself).
    """
    declared = leg.notionals  # declared on both leg types, so no `getattr` probe
    if declared is None:
        return (scalar,) * len(priced)
    by_start = {p.accrual_start: n for p, n in zip(leg.schedule.periods, declared)}
    return tuple(by_start[p.accrual_start] for p in priced)


__all__ = ["price", "price_swap"]


@register(VanillaSwap)
def price_swap(swap: VanillaSwap, model: CalibratedModel) -> PricingResult | PricingFailure:
    """Mark a vanilla swap off the model's curves. Payer PV = N·(float − rate·annuity)."""
    curves = model.market.curves
    vd = model.market.valuation_date
    dc = swap.float_leg.day_count
    try:
        discount = curves.discount(swap.currency, swap.collateral)  # CSA-keyed (A1: through the model)
        projection = curves.projection(swap.float_leg.index)
        # invariant 6: mark = FUTURE PV only; historical periods excluded ABOVE the atoms (unchanged).
        fixed_sched = future_periods(swap.fixed_leg.schedule, vd)
        float_sched = future_periods(swap.float_leg.schedule, vd)
        # ONE composition for both kinds (§3d): the annuity is always the WEIGHTED one, and a
        # constant-notional swap is the flat schedule. No `isinstance`, no parallel pricer — the
        # variable-N case is not a special case, it is the general one the flat case lives inside.
        fixed_n = _notionals_for(swap.fixed_leg, fixed_sched.periods, swap.notional)
        annuity = weighted_annuity(fixed_sched, fixed_n, swap.fixed_leg.day_count, discount)
        # the current in-progress float period is spliced from the past fixing (#3b); the strictly-future
        # periods price through the UNCHANGED float_leg_pv atom (spot/boundary → no split → byte-identical).
        current, future_float = split_current_period(float_sched, vd)
        float_n = _notionals_for(swap.float_leg, future_float.periods, swap.notional)
        floating = weighted_float_leg_pv(future_float, float_n, dc, discount, projection)
        accrued: Money | None = None
        if current is not None:
            cur = Accrual(current.accrual_start, current.accrual_end, dc)
            try:
                rate = current_period_float_rate(swap.float_leg.index, cur, projection, model.market.fixings, vd)
            except (ValueError, KeyError):  # no fixing for the current period → honest failure (invariant 4)
                return current_period_failure(current.accrual_start, vd) or PricingFailure(
                    f"missing fixing for the current period starting {current.accrual_start.isoformat()}"
                )
            cur_n = _notionals_for(swap.float_leg, (current,), swap.notional)[0]
            floating += cur_n * discount.df(current.payment_date) * cur.year_fraction() * rate
            elapsed = Accrual(current.accrual_start, vd, dc).year_fraction()  # earned-but-unpaid slice
            accrued = Money(cur_n * elapsed * (rate - swap.fixed_leg.rate), swap.currency)
    except (ValueError, KeyError) as exc:  # cashflow beyond a curve, or an unresolved curve key
        return PricingFailure(str(exc))
    pv = floating - swap.fixed_leg.rate * annuity  # both legs already notional-weighted
    basis = None if swap.collateral in (None, swap.currency) else swap.collateral
    return PricingResult(pv=Money(pv, swap.currency), accrued=accrued, basis=basis)
