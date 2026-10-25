"""Vanilla optionlet pricers — the caplet/floorlet, the cap/floor ladder, and the European
swaption, registered behind the L4 registry.

`price_caplet` composes the `forward` atom (F over the accrual, §3d) and `df` (discounting) with
the model's OWN vol law: `PV = df(pay) · N · τ · law.price(F, K, vol, t, CALL)`, the undiscounted
law value times the discount factor. Which law (lognormal / shifted / normal) is the MODEL's data,
so the pricer has no law branch — swapping the law swaps the formula, the vol units and the valid
domain together (`vol_law.defined` replaces the hard-coded `F ≤ 0` lognormal guard, audit #15).
The model must carry the `ImpliedVol` capability — validated STRUCTURALLY
against the runtime-checkable protocol (Q3′b: the registry validates capability satisfaction, it does
not `isinstance`-on-concrete-type nor auto-select a method). Market is reached only through
`model.market` (A1); failure is a value (invariant 4).

**The F-identity is now structural, not guarded (slice 25, ruling A).** The pricer computes F over the
contract's OWN accrual with the shared `forward` atom and **passes it to the vol capability**, so the
price formula and the smile compose the same F by construction. The slice-23 guard that refused a
non-canonical (stub / odd-day-count) optionlet existed only because the capability used to
*reconstruct* F from the index's canonical accrual; it no longer reconstructs anything, so the guard
is gone and a stub optionlet prices correctly at its own forward (`OPEN.md` ML-D1, closed).

Provenance:
  quarry: quarry/pricebook/options/capfloor.py (caplet pricing)
  source: CLAUDE.md §1 (capability + no law switch) · §2 (A1) · §3d (shared atoms); Black (1976)
  oracle: caplet reprices to Black-76 to <1e-12 (byte-identical through Lognormal.price); put-call
          parity; vol→0 discounted intrinsic; a negative forward prices under the normal law
  slice:  black-caplet (C2 slice 1) · law promotion in sabr-multilaw (T1 slice 22)
"""

from __future__ import annotations

from pricebook.engine.registry import register
from pricebook.engine.seasoned import current_period_failure
from pricebook.foundation import (
    Money,
    PricingFailure,
    PricingResult,
    Tenor,
    TenorUnit,
    future_periods,
)
from pricebook.market.building_blocks import float_leg_pv, forward, rpv01
from pricebook.models.black import vol_time_measure
from pricebook.models.protocols import CalibratedModel, ImpliedVol, SwaptionVol
from pricebook.products.option import CapFloor, Caplet, Swaption, cap_ladder
from pricebook.products.swap import VanillaSwap


@register(Caplet)
def price_caplet(caplet: Caplet, model: CalibratedModel) -> PricingResult | PricingFailure:
    """Mark one optionlet (caplet CALL / floorlet PUT) in the model's OWN vol law. Requires
    `ImpliedVol` (validated structurally)."""
    if not isinstance(model, ImpliedVol):  # capability check — a protocol, not a concrete-type ladder
        return PricingFailure("caplet requires a model with the ImpliedVol capability")
    accrual, index = caplet.accrual, caplet.index
    currency = index.id.currency
    vd = model.market.valuation_date
    if accrual.end <= vd:  # invariant 6: a paid optionlet has no future PV
        return PricingResult(pv=Money(0.0, currency))
    seasoned = current_period_failure(accrual.start, vd)  # #3a: fixing past, not yet paid
    if seasoned is not None:
        return seasoned
    curves = model.market.curves
    try:
        expiry = accrual.start  # T = valuation → fixing, ACT/365F for the vol
        t = vol_time_measure(vd).year_fraction(expiry)
        pay_df = curves.discount(currency).df(accrual.end)
        fwd = forward(curves.projection(index), accrual)
        tau = accrual.year_fraction()
        law = model.vol_law  # the law is the model's data; the pricer never branches on it (§1)
        if not law.defined(fwd, caplet.strike) and t > 0.0:  # #15, now the LAW's own domain
            return PricingFailure(
                f"forward {fwd} / strike {caplet.strike} outside the {type(law).__name__} law's domain"
            )
        vol = model.implied_vol(index, expiry, caplet.strike, fwd)  # ruling A: F is an INPUT
    except (ValueError, KeyError, ZeroDivisionError) as exc:
        return PricingFailure(str(exc))
    pv = pay_df * caplet.notional * tau * law.price(fwd, caplet.strike, vol, t, caplet.option_type)
    return PricingResult(pv=Money(pv, currency))


@register(CapFloor)
def price_capfloor(cap: CapFloor, model: CalibratedModel) -> PricingResult | PricingFailure:
    """Mark a cap (CALL) or floor (PUT) as the sum of its ladder. It composes `price_caplet` over
    `cap_ladder(cap)` — the ONE ladder definition the vol strip and the SABR-cap calibration compose
    too (§3d), so no stage can disagree about which caplets a cap is (audit #10).

    Everything the optionlet pricer enforces therefore applies per caplet, for free: the model's own
    vol law (so a cap is law-polymorphic — a negative forward prices under the normal/shifted laws
    and fails under the lognormal one), the ruling-2 canonical-accrual F-identity guard, and
    invariant 6 (a paid optionlet contributes 0). The FIRST failure is returned as the cap's value —
    a cap with one unpriceable caplet has no defensible PV (invariant 4)."""
    total = 0.0
    for caplet in cap_ladder(cap):
        leg = price_caplet(caplet, model)
        if isinstance(leg, PricingFailure):
            return leg
        total += leg.pv.amount
    return PricingResult(pv=Money(total, cap.index.id.currency))


def underlying_tenor(swap: VanillaSwap) -> Tenor:
    """The underlying swap's EXACT tenor — period count × the schedule's coupon step (the #7 enrichment),
    NOT `round(days/365)`. A 6M underlying keys `6M`, 18M keys `18M`, 5Y normalizes to `5Y` (whole years
    collapse to YEAR so existing surfaces stay keyed as before). This is the swaption vol's key dimension
    and must be exact — `SwaptionSurfaceKey` exists to distinguish 2Y5Y from 2Y10Y (#5)."""
    sched = swap.fixed_leg.schedule
    months = len(sched.periods) * (12 // sched.terms.frequency.per_year())
    if months % 12 == 0:
        return Tenor(months // 12, TenorUnit.YEAR)
    return Tenor(months, TenorUnit.MONTH)


@register(Swaption)
def price_swaption(swaption: Swaption, model: CalibratedModel) -> PricingResult | PricingFailure:
    """Mark a European swaption on the annuity numeraire, in the model's OWN vol law. Requires the
    `SwaptionVol` capability (validated structurally). Composes the SHARED atoms `rpv01` (annuity =
    numeraire) and `float_leg_pv` (→ forward swap rate `S = float_leg_pv/annuity`) — never the
    calibrator's private `_par_rate` — so engine and calibrator cannot disagree (§3d).
    PV = N·annuity·law.price(S, K, ·)."""
    if not isinstance(model, SwaptionVol):  # capability check — a protocol, not a concrete-type ladder
        return PricingFailure("swaption requires a model with the SwaptionVol capability")
    swap = swaption.swap
    index = swap.float_leg.index
    currency = swap.currency
    strike = swap.fixed_leg.rate
    vd = model.market.valuation_date
    if swaption.expiry <= vd:  # #20: an expired swaption has no future optional value (exercise = L6)
        return PricingResult(pv=Money(0.0, currency))
    curves = model.market.curves
    try:
        discount = curves.discount(currency, swap.collateral)  # same discount the swap engine uses
        projection = curves.projection(index)
        # invariant 6: the underlying's mark is FUTURE PV only (a spot-forward swaption loses none)
        fixed_sched = future_periods(swap.fixed_leg.schedule, vd)
        float_sched = future_periods(swap.float_leg.schedule, vd)
        seasoned = current_period_failure(fixed_sched.periods[0].accrual_start, vd) if fixed_sched.periods else None
        if seasoned is not None:  # #3a: underlying's current period is in progress
            return seasoned
        annuity = rpv01(fixed_sched, swap.fixed_leg.day_count, discount)
        s = float_leg_pv(float_sched, swap.float_leg.day_count, discount, projection) / annuity
        law = model.vol_law  # as for the caplet: polymorphic law, no branch in the pricer
        if not law.defined(s, strike):  # #15, now the LAW's own domain (t > 0 guaranteed above)
            return PricingFailure(
                f"forward swap rate {s} / strike {strike} outside the {type(law).__name__} law's domain"
            )
        swap_tenor = underlying_tenor(swap)
        vol = model.swaption_vol(index, swaption.expiry, swap_tenor, strike, s)  # the marked S
        t = vol_time_measure(vd).year_fraction(swaption.expiry)
    except (ValueError, KeyError, ZeroDivisionError) as exc:
        return PricingFailure(str(exc))
    pv = swap.notional * annuity * law.price(s, strike, vol, t, swaption.option_type)
    return PricingResult(pv=Money(pv, currency))
