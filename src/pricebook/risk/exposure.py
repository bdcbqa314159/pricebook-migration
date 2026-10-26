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

from collections.abc import Sequence
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


def netted_exposure_profile(
    swaps: Sequence[VanillaSwap], model: CalibratedModel
) -> ExposureProfile | PricingFailure:
    """`EE(tᵢ)` for a **netting set** — the trades' positions netted first, then the exposure taken
    on the net.

    That order is the whole content of netting: `EE(max(Σ MtM, 0)) ≤ Σ EE(max(MtM, 0))`, because
    exposure is a convex function of the position and offsetting trades cancel *before* the floor at
    zero rather than after. Taking exposures first and summing them would lose exactly the benefit
    netting exists to capture.

    **The analytic proxy constrains what can be netted, and the constraint fails as a value.** A
    swaption-on-the-net only exists when the set aggregates to a swap-equivalent — one index, one
    currency, one schedule family — so a heterogeneous set returns a `PricingFailure` and
    `deferred→` the MC-exposure slice. Netting a general multi-asset set is MC's job by
    construction; the alternative would be silently netting incompatible positions into a plausible
    number, which is the worst outcome available here.

    **`cva` is untouched by this.** Netting is a new *profile builder*, not a change to the integral
    — which is what slice 1's split was for, and `test_cva_signature_is_UNCHANGED_by_netting`
    asserts it so the claim cannot quietly lapse.

    **It takes the swaps, not a `Book`.** A `Book` is L6 (`shell/`) and risk is L5, so depending on
    it here is an upward import — the acyclic gate named it the moment it was tried
    (`risk(L5) imports shell(L6)`), and `shell/portfolio.py` already imports `risk`, so it was a real
    cycle rather than a stylistic point. The *netting set* is a portfolio concept and stays at L6;
    what L5 needs is the positions. `shell.book_cva` is the L6 composition that unwraps one."""
    if not swaps:
        return ()
    net = _net_swap(list(swaps))
    if isinstance(net, PricingFailure):
        return net
    return swaption_exposure_profile(net, model)


def _net_swap(swaps: list[VanillaSwap]) -> VanillaSwap | PricingFailure:
    """Aggregate a swap-equivalent set into one net swap: notionals add (signed), and the
    notional-weighted fixed rate preserves the net fixed leg's PV.

    The set must share index, currency, day counts and schedule — those are what make a single net
    swap *the same position* rather than an approximation of it. Anything else is a `PricingFailure`:
    the netting is exact here or it is MC's."""
    first = swaps[0]
    for other in swaps[1:]:
        if other.float_leg.index != first.float_leg.index:
            return PricingFailure(
                f"netting set spans two indices ({first.float_leg.index.id.name} and "
                f"{other.float_leg.index.id.name}); the analytic net needs one — deferred to MC"
            )
        if other.currency != first.currency:
            return PricingFailure("netting set spans two currencies; deferred to MC exposure")
        if other.fixed_leg.schedule != first.fixed_leg.schedule:
            return PricingFailure("netting set spans two schedules; deferred to MC exposure")
        if (other.fixed_leg.day_count, other.float_leg.day_count) != (
            first.fixed_leg.day_count, first.float_leg.day_count
        ):
            return PricingFailure("netting set spans two day-count conventions; deferred to MC")
    net_notional = sum(s.notional for s in swaps)
    if abs(net_notional) < 1e-12:
        # a perfectly offsetting set: flat position, no exposure, and no fixed rate to define
        return VanillaSwap(
            0.0, first.currency,
            FixedLeg(first.fixed_leg.schedule, first.fixed_leg.day_count, first.fixed_leg.rate),
            FloatLeg(first.float_leg.schedule, first.float_leg.day_count, first.float_leg.index),
        )
    # the notional-weighted rate is the one whose single fixed leg pays what the set's legs pay
    rate = sum(s.notional * s.fixed_leg.rate for s in swaps) / net_notional
    return VanillaSwap(
        net_notional, first.currency,
        FixedLeg(first.fixed_leg.schedule, first.fixed_leg.day_count, rate),
        FloatLeg(first.float_leg.schedule, first.float_leg.day_count, first.float_leg.index),
    )
