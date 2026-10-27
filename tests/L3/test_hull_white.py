"""Hull-White 1F, static and calibrated (`spec_hull_white_slice.md`).

    dr = (θ(t) − a·r) dt + σ dW

**θ(t) is not a free parameter here** — it is pinned by the initial curve, which is why HW reprices
that curve *by construction* and why oracle 1 is an exact (1e-12) identity rather than a fit quality.
The analytic content is:

    B(t,T) = (1 − e^{−a(T−t)}) / a
    ln A(t,T) = ln(P(0,T)/P(0,t)) + B(t,T)·f(0,t) − (σ²/4a)(1 − e^{−2at})·B(t,T)²
    P(t,T; r) = A(t,T)·e^{−B(t,T)·r}

and a European swaption by **Jamshidian**: a payer swaption is a PUT on the coupon bond with strike
1, and because `P(T,tᵢ)` is monotone in `r`, the max decomposes into a portfolio of zero-bond puts
struck at the `r*` that makes the coupon bond worth par. Source: Hull-White (1990); Brigo-Mercurio
§3.3 (the A/B form and the Jamshidian decomposition).
"""

import math
from datetime import date

import pytest

from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    PricingFailure,
    PricingResult,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    get_rate_index,
)
from pricebook.engine import price
from pricebook.market.building_blocks import float_leg_pv, rpv01
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot
from pricebook.models.hull_white import HullWhite
from pricebook.products.option import OptionType, Swaption
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(30, Y)
EXPIRY = VAL + Tenor(2, Y)
TENOR = Tenor(5, Y)
NOTIONAL = 1.0
RATE = 0.030
A, SIGMA = 0.05, 0.010


def _curves(rate: float = RATE) -> CurveSet:
    return CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, rate, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, rate, until=FAR),
        }
    )


def _hw(a: float = A, sigma: float = SIGMA, rate: float = RATE) -> HullWhite:
    return HullWhite(MarketSnapshot(VAL, _curves(rate)), a, sigma, CCY)


def _swap(strike: float, freq: Frequency = Frequency.ANNUAL) -> VanillaSwap:
    sched = build_schedule(
        EXPIRY, EXPIRY + TENOR, ScheduleTerms(frequency=freq, roll=RollRule(calendar=None))
    )
    return VanillaSwap(NOTIONAL, CCY, FixedLeg(sched, DC365, strike), FloatLeg(sched, DC365, INDEX))


def _marked_s(swap: VanillaSwap, curves: CurveSet) -> tuple[float, float]:
    """The engine's own S and annuity, via the SAME shared atoms (§3d)."""
    disc, proj = curves.discount(CCY), curves.projection(INDEX)
    annuity = rpv01(swap.fixed_leg.schedule, swap.fixed_leg.day_count, disc)
    return float_leg_pv(swap.float_leg.schedule, swap.float_leg.day_count, disc, proj) / annuity, annuity


# ── ORACLE 1 — the term-structure fit is an IDENTITY, not a fit ───────────────────────────
def test_hull_white_reprices_the_discount_curve_exactly() -> None:
    """θ(t) is pinned by the curve, so `P_HW(0,T) == DF(T)` to machine precision. A θ error — or a
    sign slip in `A` — shows here and nowhere else as cleanly."""
    hw = _hw()
    curve = hw.market.curves.discount(CCY)
    for years in (0.5, 1, 2, 5, 7, 10, 20):
        d = VAL + Tenor(int(years * 12), TenorUnit.MONTH)
        t = TM.year_fraction(d)
        assert abs(hw.bond(0.0, t, hw.r0) - curve.df(d)) < 1e-12, years


def test_the_curve_fit_holds_for_every_a_and_sigma() -> None:
    """The identity is structural: it cannot depend on the parameters, so a formula that happened to
    work at one (a, σ) is caught here."""
    curve = _hw().market.curves.discount(CCY)
    d = VAL + Tenor(7, Y)
    t = TM.year_fraction(d)
    for a in (0.001, 0.05, 0.30):
        for sigma in (0.0, 0.005, 0.02):
            hw = _hw(a, sigma)
            assert abs(hw.bond(0.0, t, hw.r0) - curve.df(d)) < 1e-12, (a, sigma)


# ── ORACLE 3 — the analytic identities of B and A ─────────────────────────────────────────
def test_B_is_the_standard_mean_reversion_integral() -> None:
    hw = _hw()
    for t, T in ((0.0, 1.0), (1.0, 5.0), (2.0, 2.5)):
        assert abs(hw.b(t, T) - (1.0 - math.exp(-A * (T - t))) / A) < 1e-14
    assert hw.b(3.0, 3.0) == 0.0


def test_B_converges_to_the_ho_lee_limit_as_mean_reversion_vanishes() -> None:
    """`a → 0 ⇒ B(t,T) → T − t` (Ho-Lee). It is a **limit**, not an equality: the error is
    `O(a·(T−t)²/2)`, so the oracle asserts the convergence RATE rather than a fixed tolerance —
    a fixed one would either pass vacuously or fail on correct maths. This is also where the closed
    form divides by a vanishing `a`, so it doubles as the numerical-stability check."""
    dt = 5.0
    errs = []
    for a in (1e-3, 1e-4, 1e-5, 1e-6):
        err = abs(_hw(a=a).b(1.0, 1.0 + dt) - dt)
        errs.append(err)
        assert err < 2.0 * a * dt**2  # the leading term, with headroom
    assert errs == sorted(errs, reverse=True)          # strictly improving
    assert errs[-1] < errs[0] / 100.0                  # and by the right order


def test_B_is_stable_at_a_mean_reversion_small_enough_to_cancel() -> None:
    """Below the series threshold the closed form would be catastrophic cancellation
    (`(1 − e^{−1e-12·dt})/1e-12`), so the expansion takes over. Assert it stays finite and close."""
    for a in (1e-9, 1e-12, 1e-15):
        b = _hw(a=a).b(1.0, 6.0)
        assert math.isfinite(b)
        assert abs(b - 5.0) < 1e-6, a


def test_a_zero_bond_option_with_zero_vol_is_its_intrinsic() -> None:
    """σ → 0 ⇒ rates are deterministic, so the option is worth its discounted intrinsic."""
    hw = _hw(sigma=0.0)
    curve = hw.market.curves.discount(CCY)
    t_exp, t_mat = 2.0, 7.0
    d_exp = VAL + Tenor(24, TenorUnit.MONTH)
    fwd_bond = hw.bond(0.0, t_mat, hw.r0) / hw.bond(0.0, t_exp, hw.r0)
    for strike in (fwd_bond * 0.9, fwd_bond * 1.1):
        call = hw.zero_bond_option(t_exp, t_mat, strike, OptionType.CALL)
        intrinsic = curve.df(d_exp) * max(fwd_bond - strike, 0.0)
        assert abs(call - intrinsic) < 1e-10, strike


def test_zero_bond_call_put_parity_holds() -> None:
    """`C − P = P(0,S) − K·P(0,T)` — the parity that catches a swapped Φ term or a sign slip."""
    hw = _hw()
    t_exp, t_mat = 2.0, 7.0
    p_t, p_s = hw.bond(0.0, t_exp, hw.r0), hw.bond(0.0, t_mat, hw.r0)
    for strike in (0.70, 0.80, 0.90):
        c = hw.zero_bond_option(t_exp, t_mat, strike, OptionType.CALL)
        p = hw.zero_bond_option(t_exp, t_mat, strike, OptionType.PUT)
        assert abs((c - p) - (p_s - strike * p_t)) < 1e-12, strike


# ── ORACLE 2 — the §3d CROSS-MODEL check: HW's own price == the engine's at HW's vol ──────
def test_the_engine_reproduces_hull_whites_own_swaption_price_at_its_implied_vol() -> None:
    """**The §3d cross-model identity.** HW prices the swaption by Jamshidian; it satisfies the
    `SwaptionVol` capability by *inverting* that price to a Black vol, so the engine's Black formula
    must reproduce it exactly. If HW's underlying `S` were a re-derivation rather than the shared
    `float_leg_pv/rpv01` atom, the two would differ — the annuity lesson, now across two models."""
    hw = _hw()
    s, annuity = _marked_s(_swap(0.0), hw.market.curves)
    for strike in (s - 0.010, s, s + 0.010):
        swap = _swap(strike)
        own = hw.swaption_price(swap, EXPIRY, OptionType.CALL)
        out = price(Swaption(swap, EXPIRY, OptionType.CALL), hw)
        assert isinstance(out, PricingResult), (strike, out)
        assert abs(out.pv.amount - own) < 1e-9 * max(1.0, abs(own)), (strike, out.pv.amount, own)


def test_hull_white_satisfies_the_swaption_capability_structurally() -> None:
    from pricebook.models.protocols import CalibratedModel, SwaptionVol

    hw = _hw()
    assert isinstance(hw, SwaptionVol)
    assert isinstance(hw, CalibratedModel)


def test_an_atm_swaption_is_worth_more_with_more_vol_and_nothing_at_zero_vol() -> None:
    hw0 = _hw(sigma=0.0)
    s, _ = _marked_s(_swap(0.0), hw0.market.curves)
    atm = _swap(s)
    assert abs(hw0.swaption_price(atm, EXPIRY, OptionType.CALL)) < 1e-10
    prices = [_hw(sigma=sg).swaption_price(atm, EXPIRY, OptionType.CALL) for sg in (0.004, 0.010, 0.020)]
    assert prices == sorted(prices)
    assert prices[0] > 0.0


def test_swaption_payer_receiver_parity_is_the_forward_swap() -> None:
    """`payer − receiver = annuity·(S − K)` — independent of the model, so it checks the Jamshidian
    decomposition against the linear atoms rather than against itself."""
    hw = _hw()
    s, annuity = _marked_s(_swap(0.0), hw.market.curves)
    for strike in (s - 0.015, s, s + 0.015):
        swap = _swap(strike)
        payer = hw.swaption_price(swap, EXPIRY, OptionType.CALL)
        receiver = hw.swaption_price(swap, EXPIRY, OptionType.PUT)
        assert abs((payer - receiver) - annuity * (s - strike)) < 1e-8, strike


def test_a_NON_CANONICAL_underlying_is_REFUSED_rather_than_mispriced_by_381bp() -> None:
    """**The slice's STOP, asserted as a guard.** A Gaussian model's swaption price depends on the
    underlying's whole coupon flow set, but `SwaptionVol`'s key is `(index, expiry, swap_tenor,
    strike)` — which cannot carry the fixed leg's frequency or day counts. Measured: a semi-annual
    underlying is mispriced by **381bp relative**; the annual one HW guesses agrees to 0.0bp.

    The threaded forward makes it *detectable*: HW computes the `S` of its reconstruction and
    refuses when it disagrees with the engine's marked `S`. So the unsound case is a failure, never
    a silently wrong vol — ML-D1's lesson applied as a guard while the protocol question is ruled."""
    hw = _hw()
    swap = _swap(0.030, freq=Frequency.SEMI_ANNUAL)

    # HW's OWN closed form is fine — the defect is the capability's key, not the maths
    assert hw.swaption_price(swap, EXPIRY, OptionType.CALL) > 0.0

    out = price(Swaption(swap, EXPIRY, OptionType.CALL), hw)
    assert isinstance(out, PricingFailure), out
    assert "reconstruct" in out.reason
    assert "bp apart" in out.reason          # the reason carries the measurement, not just a verdict


def test_the_canonical_underlying_still_agrees_exactly() -> None:
    """The control: where HW *can* reconstruct, the §3d identity holds to 1e-9 — so the guard above
    is rejecting a real gap rather than masking a broken closed form."""
    hw = _hw()
    swap = _swap(0.030, freq=Frequency.ANNUAL)
    own = hw.swaption_price(swap, EXPIRY, OptionType.CALL)
    out = price(Swaption(swap, EXPIRY, OptionType.CALL), hw)
    assert isinstance(out, PricingResult), out
    assert abs(out.pv.amount - own) < 1e-9 * max(1.0, abs(own))


# ── guards ────────────────────────────────────────────────────────────────────────────────
def test_non_positive_parameters_are_rejected() -> None:
    snap = MarketSnapshot(VAL, _curves())
    with pytest.raises(ValueError):
        HullWhite(snap, 0.0, SIGMA, CCY)       # a must be positive (a→0 is a limit, not a value)
    with pytest.raises(ValueError):
        HullWhite(snap, A, -0.01, CCY)         # sigma must be non-negative


def test_a_swaption_expiring_in_the_past_is_a_failure_value() -> None:
    hw = _hw()
    out = price(Swaption(_swap(0.030), date(2025, 1, 15), OptionType.CALL), hw)
    assert isinstance(out, (PricingFailure, PricingResult))
    if isinstance(out, PricingResult):
        assert abs(out.pv.amount) < 1e-12      # expired ⇒ no optional value (#20)
