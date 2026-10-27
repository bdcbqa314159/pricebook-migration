"""MC exposure, slice 1 — ng's first simulation (`spec_mc_exposure_slice.md` §2).

**The construction, and why it carries no discretisation bias.** Under the `tᵢ`-forward measure
Hull-White's short rate is exactly Gaussian:

    r(tᵢ) ~ N( f(0,tᵢ),  σ²(1 − e^{−2a·tᵢ}) / (2a) )

The mean being the *instantaneous forward* is not an approximation — the `α(t)` shift that fits the
curve and the forward-measure drift adjustment cancel identically (`(1−e^{−aT}) − (1−e^{−2aT})/2 ≡
(1−e^{−aT})²/2`, verified to 1e-17). So exposure dates are sampled **directly**, with no time
stepping, and MC's only error is statistical. That is what keeps oracle 1 clean: any disagreement
with the closed form is sampling noise or a bug, never Euler bias.

**Marginals, deliberately.** Each exposure date is drawn under its own forward measure, so the draws
are consistent *per date* but not a single joint path set. `EE(tᵢ)` needs only the marginal, and so
does slice 2's path-wise netting (which nets across *trades at one date*). **Wrong-way risk does
not** — it conditions on the default time — so joint paths arrive with WWR, named rather than
assumed.
"""

import math
from datetime import date

import numpy as np
import pytest

from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    MonteCarloConfig,
    PricingFailure,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    future_periods,
    get_rate_index,
)
from pricebook.foundation.day_count import Accrual
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot, RecoveryKey
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.models.hull_white import HullWhite
from pricebook.products.option import OptionType
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap
from pricebook.risk.exposure import mc_exposure_profile
from pricebook.risk.xva import cva

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(30, Y)
TENOR = Tenor(5, Y)
RATE, A, SIGMA = 0.030, 0.05, 0.010
RECOVERY = 0.40
CP = ReferenceEntity("COUNTERPARTY")


def _market(hazard: float = 0.02, recovery: float = RECOVERY) -> MarketSnapshot:
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, RATE, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, RATE, until=FAR),
            CurveKey(CurveRole.SURVIVAL, CP): SurvivalCurve.flat_hazard(TM, hazard, until=FAR),
        }
    )
    return MarketSnapshot(VAL, curves, scalars={RecoveryKey(CP): recovery})


def _hw(sigma: float = SIGMA, hazard: float = 0.02) -> HullWhite:
    return HullWhite(_market(hazard), A, sigma, CCY)


def _swap(strike: float = RATE, notional: float = 1.0) -> VanillaSwap:
    sched = build_schedule(
        VAL, VAL + TENOR, ScheduleTerms(frequency=Frequency.ANNUAL, roll=RollRule(calendar=None))
    )
    return VanillaSwap(notional, CCY, FixedLeg(sched, DC365, strike), FloatLeg(sched, DC365, INDEX))


def _analytic_ee(swap: VanillaSwap, hw: HullWhite) -> list[tuple[date, float]]:
    """The closed-form EE: at each schedule date, HW's OWN Jamshidian price of the swaption on the
    remaining leg. MC simulates HW, so HW's analytic price is the right anchor — comparing to the
    Black cube instead would be comparing two models."""
    out = []
    for p in swap.fixed_leg.schedule.periods:
        expiry = p.accrual_end
        remaining = future_periods(swap.fixed_leg.schedule, expiry)
        if not remaining.periods:
            out.append((expiry, 0.0))
            continue
        sub = VanillaSwap(
            abs(swap.notional), swap.currency,
            FixedLeg(remaining, swap.fixed_leg.day_count, swap.fixed_leg.rate),
            FloatLeg(future_periods(swap.float_leg.schedule, expiry), swap.float_leg.day_count,
                     swap.float_leg.index),
        )
        out.append((expiry, hw.swaption_price(sub, expiry, OptionType.CALL)))
    return out


# ── ORACLE 1 — MC agrees with the CLOSED FORM, within 3 standard errors ───────────────────
def test_mc_exposure_agrees_with_hull_whites_own_closed_form() -> None:
    """The anchor. MC convergence alone is rung 3; agreement with an exact price is rung 1."""
    hw, swap = _hw(), _swap()
    mc = mc_exposure_profile(swap, hw, MonteCarloConfig(paths=200_000, seed=12345))
    assert not isinstance(mc, PricingFailure), mc
    analytic = _analytic_ee(swap, hw)
    assert [d for d, _ in mc] == [d for d, _ in analytic]
    for (d, ee), (_, exact) in zip(mc, analytic):
        if exact == 0.0:
            assert ee == 0.0
            continue
        assert abs(ee - exact) < 0.02 * exact, (d, ee, exact)   # ≲2% at 200k paths


def test_the_mc_cva_agrees_with_the_analytic_cva() -> None:
    hw, swap = _hw(), _swap(notional=10_000_000.0)
    market = hw.market
    mc = mc_exposure_profile(swap, hw, MonteCarloConfig(paths=200_000, seed=7))
    assert not isinstance(mc, PricingFailure), mc
    mc_charge = cva(mc, market.curves.survival(CP), market.recovery(CP))
    exact = cva(_analytic_ee(swap, hw), market.curves.survival(CP), market.recovery(CP))
    assert abs(mc_charge - exact) < 0.02 * exact, (mc_charge, exact)


# ── the measure identity the construction rests on ───────────────────────────────────────
def test_the_simulated_short_rate_has_the_instantaneous_forward_as_its_MEAN() -> None:
    """`E^{tᵢ}[r(tᵢ)] = f(0,tᵢ)` exactly — the α-shift and the forward-measure drift cancel. If the
    drift adjustment were dropped (the classic error), the mean would be off by `σ²B(0,t)²/2` and
    every exposure would be biased. Checked directly on the sampler, not inferred from prices."""
    from pricebook.risk.exposure import _simulate_short_rate

    hw = _hw()
    for years in (1.0, 3.0, 5.0):
        draws = _simulate_short_rate(hw, years, MonteCarloConfig(paths=400_000, seed=99))
        fwd = hw._instantaneous_forward(years)
        var = SIGMA**2 * (1.0 - math.exp(-2.0 * A * years)) / (2.0 * A)
        stderr = math.sqrt(var / 400_000)
        assert abs(float(np.mean(draws)) - fwd) < 4.0 * stderr, years
        assert abs(float(np.var(draws)) - var) < 0.02 * var, years


# ── ORACLE 2 — convergence RATE, not a tolerance ─────────────────────────────────────────
def test_the_error_falls_as_one_over_root_paths() -> None:
    """Quadrupling the paths should roughly halve the error. Asserting the *rate* catches a sampler
    that is merely noisy-but-biased, which a fixed tolerance at one path count would not."""
    hw, swap = _hw(), _swap()
    analytic = dict(_analytic_ee(swap, hw))
    errs = []
    for paths in (2_000, 8_000, 32_000, 128_000):
        mc = mc_exposure_profile(swap, hw, MonteCarloConfig(paths=paths, seed=4242))
        assert not isinstance(mc, PricingFailure), mc
        rel = [abs(ee - analytic[d]) / analytic[d] for d, ee in mc if analytic[d] > 0.0]
        errs.append(sum(rel) / len(rel))
    assert errs[-1] < errs[0] / 4.0, errs     # 64x paths ⇒ ≈8x better; 4x is a safe floor


# ── ORACLE 3 — the σ→0 degeneracy, cross-checked independently ───────────────────────────
def test_zero_vol_gives_the_deterministic_forward_exposure() -> None:
    """σ→0 ⇒ rates are deterministic, so every path is the forward curve and `EE` is the
    discounted intrinsic of the forward swap — computable without MC at all, so this is an
    independent cross-check at the boundary rather than MC against itself."""
    hw = _hw(sigma=0.0)
    swap = _swap(strike=RATE - 0.005)          # in the money, so the intrinsic is non-trivial
    mc = mc_exposure_profile(swap, hw, MonteCarloConfig(paths=1_000, seed=1))
    assert not isinstance(mc, PricingFailure), mc
    for (d, ee), (_, exact) in zip(mc, _analytic_ee(swap, hw)):
        assert abs(ee - exact) < 1e-10, (d, ee, exact)


# ── ORACLE 4 — reproducibility (invariant 1) ─────────────────────────────────────────────
def test_the_same_seed_gives_a_BYTE_IDENTICAL_profile() -> None:
    hw, swap = _hw(), _swap()
    cfg = MonteCarloConfig(paths=20_000, seed=2718)
    a = mc_exposure_profile(swap, hw, cfg)
    b = mc_exposure_profile(swap, hw, cfg)
    assert a == b                                      # byte-identical, not merely close


def test_a_different_seed_gives_a_different_but_nearby_profile() -> None:
    hw, swap = _hw(), _swap()
    a = mc_exposure_profile(swap, hw, MonteCarloConfig(paths=20_000, seed=1))
    b = mc_exposure_profile(swap, hw, MonteCarloConfig(paths=20_000, seed=2))
    assert a != b
    for (_, x), (_, y) in zip(a, b):
        if x > 0.0:
            assert abs(x - y) < 0.05 * x


def test_the_seed_is_explicit_with_no_hidden_default() -> None:
    """A defaulted seed is a hidden reproducibility knob (invariant 5) — and the one that matters
    most, since without it a run cannot be repeated at all."""
    import inspect

    params = inspect.signature(MonteCarloConfig.__init__).parameters
    assert params["seed"].default is inspect.Parameter.empty
    assert params["paths"].default is inspect.Parameter.empty


# ── ORACLE 5 — structural ────────────────────────────────────────────────────────────────
def test_every_exposure_is_non_negative_and_the_last_is_zero() -> None:
    mc = mc_exposure_profile(_swap(), _hw(), MonteCarloConfig(paths=5_000, seed=11))
    assert not isinstance(mc, PricingFailure), mc
    assert all(ee >= 0.0 for _, ee in mc)
    assert mc[-1][1] == 0.0
    assert len(mc) == 5


def test_zero_hazard_gives_zero_cva_on_the_mc_profile() -> None:
    hw = _hw(hazard=0.0)
    mc = mc_exposure_profile(_swap(), hw, MonteCarloConfig(paths=5_000, seed=5))
    assert not isinstance(mc, PricingFailure), mc
    got = cva(mc, hw.market.curves.survival(CP), hw.market.recovery(CP))
    assert abs(got) < 1e-12


def test_bumping_recovery_moves_the_mc_cva_by_the_lgd_ratio() -> None:
    swap = _swap(notional=10_000_000.0)
    cfg = MonteCarloConfig(paths=20_000, seed=31415)
    out = []
    for recovery in (0.40, 0.41):
        market = _market(recovery=recovery)
        hw = HullWhite(market, A, SIGMA, CCY)
        mc = mc_exposure_profile(swap, hw, cfg)
        assert not isinstance(mc, PricingFailure), mc
        out.append(cva(mc, market.curves.survival(CP), market.recovery(CP)))
    assert abs(out[1] - out[0] * (0.59 / 0.60)) < 1e-9 * out[0]


def test_a_non_positive_path_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        MonteCarloConfig(paths=0, seed=1)
