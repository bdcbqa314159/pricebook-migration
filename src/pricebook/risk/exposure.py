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

import math
from collections.abc import Sequence
from datetime import date

import numpy as np

from pricebook.engine.registry import dispatch as price
from pricebook.foundation.day_count import Accrual
from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.foundation.results import PricingFailure
from pricebook.foundation.schedule import future_periods
from pricebook.models.hull_white import HullWhite
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


def mc_exposure_profile(
    swap: VanillaSwap, model: HullWhite, numerics: MonteCarloConfig
) -> ExposureProfile | PricingFailure:
    """`EE(tᵢ)` by Monte-Carlo under Hull-White — ng's first simulation.

    **Exact sampling, so MC's only error is statistical.** Under the `tᵢ`-forward measure HW's short
    rate is exactly Gaussian,

        r(tᵢ) ~ N( f(0,tᵢ),  σ²(1 − e^{−2a·tᵢ}) / (2a) )

    and the mean being the *instantaneous forward* is an identity, not an approximation: the `α(t)`
    shift that fits the curve and the forward-measure drift adjustment cancel, because
    `(1 − e^{−aT}) − (1 − e^{−2aT})/2 ≡ (1 − e^{−aT})²/2`. So the dates are sampled **directly** —
    no time stepping, no Euler bias — which is what lets the oracle be *agreement with the closed
    form* rather than mere convergence. Dropping the drift adjustment is the classic error here and
    would bias every exposure by `σ²B(0,t)²/2`; a test checks the sampled mean against `f(0,t)`
    directly, not through a price.

    **Marginals, deliberately.** Each date is drawn under its own forward measure, so draws are
    consistent per date but are not one joint path set. `EE(tᵢ)` needs only the marginal, and so does
    path-wise netting across *trades at one date*. **Wrong-way risk does not** — it conditions on the
    default time — so joint paths arrive with WWR, named rather than assumed.

    **The exposure composes HW's own bond.** The swap's value at `tᵢ` is
    `(1 − P(tᵢ,tₙ)) − Σ K·τⱼ·P(tᵢ,tⱼ)` — the same coupon bond HW's Jamshidian decomposes, so MC and
    the closed form share the atom rather than agreeing by coincidence (§3d).

    **Output is `(date, EE)`**, unchanged — so `cva` is untouched by MC exactly as it was by netting."""
    periods = swap.fixed_leg.schedule.periods
    if not periods:
        return ()
    sign = 1.0 if swap.notional >= 0.0 else -1.0
    try:
        out: list[tuple[date, float]] = []
        for p in periods:
            expiry = p.accrual_end
            t_exp = model.market.curves.discount(model.currency).time_measure.year_fraction(expiry)
            flows = _remaining_fixed_flows(swap, expiry, model)
            if not flows:
                out.append((expiry, 0.0))
                continue
            draws = _simulate_short_rate(model, t_exp, numerics)
            t_last = flows[-1][0]
            # `P(t,T;r) = exp(logA − B·r)` and neither logA nor B depends on r, so each maturity's
            # curve-dependent part is computed ONCE and the path dimension is pure numpy. The naive
            # per-path loop called `bond` 200k × (n+1) times and took ~70s for this file alone.
            fixed_leg = np.zeros_like(draws)
            for t_j, c in flows:
                fixed_leg += c * _bond_vec(model, t_exp, t_j, draws)
            value = sign * (1.0 - _bond_vec(model, t_exp, t_last, draws) - fixed_leg)
            discounted = model.bond(0.0, t_exp, model.r0) * float(np.mean(np.maximum(value, 0.0)))
            out.append((expiry, abs(swap.notional) * discounted))
    except (ValueError, KeyError, ZeroDivisionError) as exc:
        return PricingFailure(f"MC exposure: {exc}")
    return tuple(out)


def _remaining_fixed_flows(
    swap: VanillaSwap, expiry: date, model: HullWhite
) -> list[tuple[float, float]]:
    """The fixed leg's `(tⱼ, K·τⱼ)` still outstanding at `expiry`, each `τ` from the leg's own
    convention — so a semi-annual or odd-day-count underlying values correctly."""
    measure = model.market.curves.discount(model.currency).time_measure
    flows: list[tuple[float, float]] = []
    for p in swap.fixed_leg.schedule.periods:
        if p.payment_date <= expiry:
            continue
        tau = Accrual(p.accrual_start, p.accrual_end, swap.fixed_leg.day_count).year_fraction()
        flows.append((measure.year_fraction(p.payment_date), swap.fixed_leg.rate * tau))
    return flows


def _simulate_short_rate(model: HullWhite, t: float, numerics: MonteCarloConfig):
    """`r(t)` under the `t`-forward measure: Gaussian, mean `f(0,t)`, variance
    `σ²(1 − e^{−2at})/(2a)`. Exact — see `mc_exposure_profile` for why the mean is the forward.

    Seeded per call *and per date* from the config's seed, so the profile is reproducible
    byte-identically (invariant 1) while different dates do not share draws."""
    mean = model._instantaneous_forward(t)
    if model.sigma == 0.0 or t <= 0.0:
        return np.full(numerics.paths, mean)
    var = model.sigma**2 * (1.0 - math.exp(-2.0 * model.a * t)) / (2.0 * model.a)
    rng = np.random.default_rng((numerics.seed, round(t * 1_000_000)))
    return rng.normal(mean, math.sqrt(var), numerics.paths)


def _bond_vec(model: HullWhite, t: float, maturity: float, r):
    """`P(t,T; r)` over an array of `r`. The same closed form `HullWhite.bond` evaluates for one
    rate — `logA` and `B` are curve-and-parameter facts, independent of `r`, so they are computed
    once per maturity and the path dimension stays in numpy (§3d: one formula, two call shapes)."""
    return np.exp(model._log_a(t, maturity) - model.b(t, maturity) * r)
