"""Equity greeks by bump-and-reprice, and the generic `ScalarBump` underneath them.

The oracle is **analytic vs finite-difference** (the slice-0 pattern): each greek is computed by
bumping the snapshot and repricing through the c1 pricer, and checked against a closed form that
the pricer never touches. Delta's reference is written here as `e^{−qT}·N(d₁)`; vega's is ng's
existing `black_vega` scaled by the discount factor — so neither reference is the bump path
restated.

`ScalarBump` is generic over the scalar key, and `RecoveryBump` is refactored onto it: two
consumers (equity spot/dividend and credit recovery) is the §6b rule-of-two moment, and two
scalar-bump paths would be the §3d divergence smell. The credit `rec01` must come through that
refactor **unchanged to the ULP** — the refactor moves the home, not the number.
"""

import math
from datetime import date, timedelta

import pytest
from scipy.stats import norm

from pricebook.foundation import Currency, PricingResult
from pricebook.foundation.equity import EquityUnderlying
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey, MarketSnapshot
from pricebook.market.vol_surface import EquitySurfaceKey, Surface
from pricebook.models.black import black_vega, vol_time_measure
from pricebook.models.black_model import BlackModel
from pricebook.products.equity import EquityOption
from pricebook.products.option import OptionType
from pricebook.risk.bump import ScalarBump
from pricebook.risk.equity import equity_delta, equity_dividend_rho, equity_gamma, equity_vega
from pricebook.risk.priceable import priceable

VAL = date(2026, 1, 15)
ACME = EquityUnderlying("ACME")
EXPIRY = VAL + timedelta(days=365)
S, VOL, R, Q, T = 100.0, 0.20, 0.05, 0.03, 1.0


def _market(spot: float = S, vol: float = VOL, q: float = Q) -> MarketSnapshot:
    curve = DiscountCurve(
        time_measure=vol_time_measure(VAL), times=(0.0, 10.0), dfs=(1.0, math.exp(-R * 10.0))
    )
    return MarketSnapshot(
        valuation_date=VAL,
        curves=CurveSet({CurveKey(CurveRole.DISCOUNT, Currency.USD, None): curve}),
        scalars={EquitySpotKey(ACME): spot, DividendYieldKey(ACME): q},
        surfaces={EquitySurfaceKey(ACME): Surface(vols=(vol,))},
    )


def _opt(strike: float = 100.0, kind: OptionType = OptionType.CALL) -> EquityOption:
    return EquityOption(underlying=ACME, strike=strike, expiry=EXPIRY, option_type=kind)


def _p(option: EquityOption):
    return priceable(option, BlackModel)


def _d1(k: float) -> float:
    return (math.log(S / k) + (R - Q + 0.5 * VOL * VOL) * T) / (VOL * math.sqrt(T))


# ── 1. analytic vs finite difference ────────────────────────────────────────────────────────
def test_delta_matches_the_closed_form_exp_minus_qT_N_d1() -> None:
    """BSM spot delta `∂C/∂S = e^{−qT}·N(d₁)` for a call, `−e^{−qT}·N(−d₁)` for a put. The
    reference never forms the forward, so it is not the pricer's own composition restated."""
    for strike in (80.0, 100.0, 125.0):
        got = equity_delta(_p(_opt(strike)), _market())
        assert got == pytest.approx(math.exp(-Q * T) * norm.cdf(_d1(strike)), abs=1e-6), strike
        got_put = equity_delta(_p(_opt(strike, OptionType.PUT)), _market())
        assert got_put == pytest.approx(-math.exp(-Q * T) * norm.cdf(-_d1(strike)), abs=1e-6)


def test_vega_matches_ngs_OWN_black_vega_scaled_by_the_discount_factor() -> None:
    """ng already owns the undiscounted Black vega; the equity vega is that, discounted. Using it
    as the reference checks the *plumbing* (which surface is bumped, how it is scaled) rather than
    re-deriving `F·φ(d₁)√t`, which would just restate the formula under test."""
    df, fwd = math.exp(-R * T), S * math.exp((R - Q) * T)
    for strike in (80.0, 100.0, 125.0):
        got = equity_vega(_p(_opt(strike)), _market())
        assert got == pytest.approx(df * black_vega(fwd, strike, VOL, T), rel=1e-5), strike


def test_gamma_is_positive_peaks_near_the_forward_and_is_type_blind() -> None:
    """Gamma has no closed-form reference written here on purpose — a second-difference FD is too
    noisy for a 1e-6 match, so the oracle is STRUCTURAL: strictly positive, maximal near the
    forward (not near spot — the same forward-vs-spot trap c1's σ→0 test guards), and identical
    for a call and a put, which is put-call parity in the second derivative."""
    fwd = S * math.exp((R - Q) * T)
    gammas = {k: equity_gamma(_p(_opt(k)), _market()) for k in (80.0, 95.0, 105.0, 125.0)}
    assert all(g > 0.0 for g in gammas.values())
    assert max(gammas, key=lambda k: gammas[k]) == min(gammas, key=lambda k: abs(k - fwd))
    for k in gammas:
        assert equity_gamma(_p(_opt(k, OptionType.PUT)), _market()) == pytest.approx(
            gammas[k], rel=1e-6
        )


def test_dividend_sensitivity_is_negative_for_a_call_and_positive_for_a_put() -> None:
    """`∂C/∂q = −T·S·e^{−qT}·N(d₁)` — a higher dividend yield lowers the forward."""
    got = equity_dividend_rho(_p(_opt()), _market())
    assert got == pytest.approx(-T * S * math.exp(-Q * T) * norm.cdf(_d1(100.0)), abs=1e-5)
    assert equity_dividend_rho(_p(_opt(kind=OptionType.PUT)), _market()) > 0.0


def test_greek_put_call_parity_delta_call_minus_delta_put_is_exp_minus_qT() -> None:
    """Differentiating `C − P = df·(F − K)` in spot gives `Δ_C − Δ_P = e^{−qT}` — model-free, so
    it cross-checks the two bumps against each other rather than against a formula."""
    for strike in (80.0, 100.0, 125.0):
        c = equity_delta(_p(_opt(strike)), _market())
        p = equity_delta(_p(_opt(strike, OptionType.PUT)), _market())
        assert c - p == pytest.approx(math.exp(-Q * T), abs=1e-6), strike


# ── 2. the generic ScalarBump, and that the refactor moved the home not the number ──────────
def test_scalar_bump_moves_only_its_own_key() -> None:
    base = _market()
    bumped = ScalarBump(EquitySpotKey(ACME)).apply(base, 1.0)
    assert bumped.scalars[EquitySpotKey(ACME)] == pytest.approx(S + 1.0)
    assert bumped.scalars[DividendYieldKey(ACME)] == base.scalars[DividendYieldKey(ACME)]
    assert base.scalars[EquitySpotKey(ACME)] == S  # the base is never mutated


def test_recovery_bump_is_the_SAME_mechanism_not_a_second_one() -> None:
    """§3d: one scalar-bump mechanism. `RecoveryBump` must *be* a `ScalarBump`, not a parallel
    implementation that happens to agree today."""
    from pricebook.foundation.reference_entity import ReferenceEntity
    from pricebook.market.snapshot import RecoveryKey
    from pricebook.risk.bump import RecoveryBump

    assert RecoveryBump(ReferenceEntity("ACME")) == ScalarBump(RecoveryKey(ReferenceEntity("ACME")))
