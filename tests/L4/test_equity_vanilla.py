"""Equity vanilla option — the (c) arc's oracle anchor (rung 1, Black-Scholes closed form).

ng prices the equity option by **composing** what already exists: the equity forward
`F = S·e^{−qT}/DF` and the existing `black` atom, discounted. The oracle checks that composition
against the **Black-Scholes-Merton spot form** written directly in (S, K, r, q, σ, T) — a
different algebraic arrangement of the same mathematics, so it tests ng's *finance* (the forward
construction and the discounting) rather than re-running ng's own code (§7bb: an oracle must test
the finance, never the numerics of the library underneath).
"""

import math
from datetime import date, timedelta

import pytest
from scipy.stats import norm  # the INDEPENDENT N(·) for the reference formula

from pricebook.engine.equity import price_equity_option
from pricebook.foundation import Currency, DayCountConvention, PricingResult
from pricebook.foundation.equity import EquityUnderlying
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey, MarketSnapshot
from pricebook.market.vol_surface import EquitySurfaceKey, Surface
from pricebook.models.black_model import BlackModel
from pricebook.products.equity import EquityOption
from pricebook.products.option import OptionType

VAL = date(2026, 1, 15)
ACME = EquityUnderlying("ACME")
DC = DayCountConvention.ACT_365_FIXED
T_DAYS = 365  # exactly one ACT/365 year, so the textbook T = 1.0 is exact
EXPIRY = VAL + timedelta(days=T_DAYS)


def _market(spot: float = 100.0, vol: float = 0.20, r: float = 0.05, q: float = 0.0) -> MarketSnapshot:
    curve = DiscountCurve(
        valuation_date=VAL, times=(0.0, 10.0), zero_rates=(r, r), day_count=DC
    )
    curves = CurveSet({CurveKey(Currency.USD, CurveRole.DISCOUNT, None): curve})
    return MarketSnapshot(
        valuation_date=VAL,
        curves=curves,
        scalars={EquitySpotKey(ACME): spot, DividendYieldKey(ACME): q},
        surfaces={EquitySurfaceKey(ACME): Surface(vols=(vol,))},
    )


def _bsm(s: float, k: float, r: float, q: float, vol: float, t: float, call: bool = True) -> float:
    """Black-Scholes-Merton in SPOT form — the reference. Note it never forms `F` explicitly, so
    it is not a restatement of ng's forward-then-Black composition."""
    d1 = (math.log(s / k) + (r - q + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if call:
        return s * math.exp(-q * t) * norm.cdf(d1) - k * math.exp(-r * t) * norm.cdf(d2)
    return k * math.exp(-r * t) * norm.cdf(-d2) - s * math.exp(-q * t) * norm.cdf(-d1)


def _price(option: EquityOption, **mkt) -> float:
    out = price_equity_option(option, BlackModel(market=_market(**mkt)))
    assert isinstance(out, PricingResult), out
    return out.pv.amount


def _opt(strike: float = 100.0, kind: OptionType = OptionType.CALL) -> EquityOption:
    return EquityOption(underlying=ACME, strike=strike, expiry=EXPIRY, option_type=kind)


# ── 1. the textbook value, and the closed form it comes from ────────────────────────────────
def test_the_textbook_black_scholes_call() -> None:
    """S=100, K=100, σ=20%, T=1, r=5%, q=0 — the standard worked example, ≈ 10.4506."""
    assert _price(_opt()) == pytest.approx(10.4506, abs=5e-5)


def test_every_strike_and_both_types_match_the_BSM_SPOT_form_to_1e_10() -> None:
    for strike in (60.0, 90.0, 100.0, 110.0, 160.0):
        for kind, call in ((OptionType.CALL, True), (OptionType.PUT, False)):
            for q in (0.0, 0.03):
                got = _price(_opt(strike, kind), q=q)
                want = _bsm(100.0, strike, 0.05, q, 0.20, 1.0, call)
                assert got == pytest.approx(want, abs=1e-10, rel=1e-12), (strike, kind, q)


def test_put_call_parity_C_minus_P_equals_DF_times_F_minus_K() -> None:
    """`C − P = DF·(F − K)` — model-free, so it checks the forward construction and the discount
    against each other rather than against another Black call."""
    for strike in (60.0, 100.0, 160.0):
        for q in (0.0, 0.03):
            c, p = _price(_opt(strike), q=q), _price(_opt(strike, OptionType.PUT), q=q)
            df = math.exp(-0.05)
            fwd = 100.0 * math.exp((0.05 - q) * 1.0)
            assert c - p == pytest.approx(df * (fwd - strike), abs=1e-10)


# ── 2. the forward identity — the new composition this slice adds ───────────────────────────
def test_the_equity_forward_is_S_times_exp_r_minus_q_T() -> None:
    from pricebook.market.building_blocks import equity_forward

    df = math.exp(-0.05)
    for q in (0.0, 0.02, 0.05, 0.09):
        assert equity_forward(100.0, q, df, 1.0) == pytest.approx(
            100.0 * math.exp((0.05 - q) * 1.0), rel=1e-12
        )


def test_a_higher_dividend_yield_lowers_the_forward_and_the_call_monotonically() -> None:
    prices = [_price(_opt(), q=q) for q in (0.0, 0.02, 0.05, 0.09)]
    assert prices == sorted(prices, reverse=True)
    assert all(p > 0.0 for p in prices)


def test_q_equals_zero_reduces_to_NO_DIVIDEND_black_scholes() -> None:
    assert _price(_opt(110.0), q=0.0) == pytest.approx(
        _bsm(100.0, 110.0, 0.05, 0.0, 0.20, 1.0), abs=1e-10
    )


# ── 3. degeneracies ─────────────────────────────────────────────────────────────────────────
def test_zero_vol_is_the_DISCOUNTED_INTRINSIC_ON_THE_FORWARD_not_on_spot() -> None:
    """The trap this guards: at σ=0 the payoff is `(F−K)⁺` discounted, NOT `(S−K)⁺`. With r=5%
    and q=0 the forward is 105.13, so a K=102 call is worth 2.98 discounted — in the money —
    while spot intrinsic would say it is worthless."""
    df, fwd = math.exp(-0.05), 100.0 * math.exp(0.05)
    assert _price(_opt(102.0), vol=0.0) == pytest.approx(df * (fwd - 102.0), abs=1e-12)
    assert _price(_opt(102.0), vol=0.0) > 0.0
    assert _price(_opt(200.0), vol=0.0) == pytest.approx(0.0, abs=1e-12)


def test_expiry_at_the_valuation_date_is_intrinsic() -> None:
    expired = EquityOption(underlying=ACME, strike=90.0, expiry=VAL, option_type=OptionType.CALL)
    assert _price(expired) == pytest.approx(10.0, abs=1e-12)  # F = S at t=0, DF = 1


def test_an_unknown_underlying_is_a_FAILURE_not_a_crash_or_a_zero() -> None:
    from pricebook.foundation import PricingFailure

    other = EquityOption(
        underlying=EquityUnderlying("NOT_MARKED"), strike=100.0, expiry=EXPIRY,
        option_type=OptionType.CALL,
    )
    out = price_equity_option(other, BlackModel(market=_market()))
    assert isinstance(out, PricingFailure)  # invariant 4: failure is a value


def test_the_L0_identity_satisfies_the_Underlying_protocol() -> None:
    from pricebook.foundation.underlying import AssetClass, Underlying

    assert isinstance(ACME, Underlying)
    assert ACME.asset_class is AssetClass.EQUITY
    assert EquityUnderlying("ACME") == ACME  # keyed by VALUE, like ReferenceEntity
