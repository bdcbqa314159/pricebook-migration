"""Equity MC exposure → equity CVA (c3), through the c2 generic engine.

**The anchor is a martingale identity, not another MC.** For a LONG equity option the future MtM
is always positive, so `EE(tᵢ) = E^Q[V(tᵢ)]` — and under deterministic rates the discounted value
is a martingale, giving

    EE(tᵢ) = V₀ / df(0, tᵢ)

exactly. The right-hand side is c1's closed-form price grossed up by a discount factor: no new
formula, no second simulation, and nothing the exposure builder itself computes. That is the
equity analogue of rates-MC → the swaption approximation, with c1 again the anchor.

A **forward** is included alongside, because for a long option the `max(·, 0)` floor is a no-op —
an exposure builder that forgot the floor entirely would still pass the option test. The forward's
MtM goes negative, so the floor bites and its own closed form catches that.
"""

import math
from datetime import date, timedelta

import numpy as np

import pytest

from pricebook.foundation import Currency, PricingResult
from pricebook.foundation.equity import EquityUnderlying
from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey, MarketSnapshot
from pricebook.market.vol_surface import EquitySurfaceKey, Surface
from pricebook.models.black import black, vol_time_measure
from pricebook.models.black_model import BlackModel
from pricebook.models.process import BlackScholesProcess
from pricebook.products.equity import EquityOption
from pricebook.products.option import OptionType
from pricebook.risk.exposure import equity_exposure_profile

VAL = date(2026, 1, 15)
ACME = EquityUnderlying("ACME")
S0, VOL, R, Q = 100.0, 0.25, 0.04, 0.02
EXPIRY = VAL + timedelta(days=365 * 2)
DATES = tuple(VAL + timedelta(days=365 * n // 2) for n in (1, 2, 3))  # 6m, 1y, 18m
MC = MonteCarloConfig(paths=200_000, seed=20261029)


def _market() -> MarketSnapshot:
    curve = DiscountCurve(
        time_measure=vol_time_measure(VAL), times=(0.0, 30.0), dfs=(1.0, math.exp(-R * 30.0))
    )
    return MarketSnapshot(
        valuation_date=VAL,
        curves=CurveSet({CurveKey(CurveRole.DISCOUNT, Currency.USD, None): curve}),
        scalars={EquitySpotKey(ACME): S0, DividendYieldKey(ACME): Q},
        surfaces={EquitySurfaceKey(ACME): Surface(vols=(VOL,))},
    )


def _process(market: MarketSnapshot | None = None) -> BlackScholesProcess:
    return BlackScholesProcess(market or _market(), ACME, Currency.USD)


def _option(strike: float = 100.0) -> EquityOption:
    return EquityOption(ACME, strike, EXPIRY, OptionType.CALL, Currency.USD)


def _c1_price(option: EquityOption, market: MarketSnapshot) -> float:
    from pricebook.engine.equity import price_equity_option

    out = price_equity_option(option, BlackModel(market=market))
    assert isinstance(out, PricingResult), out
    return out.pv.amount


# ── 1. the closed-form anchor ───────────────────────────────────────────────────────────────
def test_equity_EE_is_CONSTANT_at_V0_the_martingale_closed_form() -> None:
    """**`EE(tᵢ) = V₀` at every date, flat.** Profiles are discounted to today, and a long
    option's discounted value is a martingale, so the discounted expected exposure is the
    option's own price — the same number at every horizon.

    This is strictly sharper than the undiscounted form (`V₀/df`) the slice first asserted: a
    *constant* is a stronger claim than a curve, and it fails if the discounting is dropped,
    doubled, or applied at the wrong date. The undiscounted version passed while the profile was
    5.14% too large for `cva`, because it checked the builder against itself rather than against
    the convention `cva` requires."""
    market = _market()
    for strike in (80.0, 100.0, 130.0):
        option = _option(strike)
        v0 = _c1_price(option, market)
        profile = equity_exposure_profile(option, _process(market), DATES, MC)
        assert isinstance(profile, tuple) and len(profile) == len(DATES), profile
        for (d, ee), expected_date in zip(profile, DATES):
            assert d == expected_date
            assert ee == pytest.approx(v0, rel=0.02), (strike, d, ee, v0)


def test_the_profile_is_FLAT_not_trending_which_a_wrong_discounting_would_break() -> None:
    """The shape claim behind the constant above: no trend either way. A missing discount makes it
    rise like `1/df`; discounting twice makes it fall like `df`. Asserting flatness catches both
    directions, which `sorted(ees)` (the original test) only caught one of — and it passed on the
    undiscounted profile."""
    ees = [ee for _, ee in equity_exposure_profile(_option(), _process(), DATES, MC)]
    assert max(ees) / min(ees) < 1.02, ees


def test_convergence_the_error_falls_like_one_over_sqrt_P() -> None:
    market = _market()
    want = _c1_price(_option(), market)  # discounted EE of a long option IS its price
    errs = []
    for paths in (2_000, 8_000, 32_000, 128_000):
        prof = equity_exposure_profile(
            _option(), _process(market), (DATES[1],), MonteCarloConfig(paths=paths, seed=99)
        )
        errs.append(abs(prof[0][1] - want))
    assert errs[0] > errs[-1]
    assert errs[0] / max(errs[-1], 1e-12) > 3.0, errs  # 64x paths ⇒ ~8x error reduction


# ── 2. the floor, which a long option cannot test ───────────────────────────────────────────
def test_a_FORWARD_exposure_exercises_the_positive_part_an_option_cannot() -> None:
    """For a long option `max(V, 0)` is a no-op, so an exposure builder that dropped the floor
    entirely would still pass every test above. A forward's MtM goes negative, and its EE has its
    own closed form:

        EE(tᵢ) = df(tᵢ,T)·e^{(r−q)(T−tᵢ)} · black( F(0,tᵢ), K·e^{−(r−q)(T−tᵢ)}, σ, tᵢ, CALL )

    i.e. the positive part of a forward IS a call — composed from ng's own `black` atom, so the
    reference reuses the atom rather than restating the formula."""
    from pricebook.products.equity import EquityForward

    market = _market()
    curve = market.curves.discount(Currency.USD, None)
    tm = vol_time_measure(VAL)
    k = 100.0
    fwd = EquityForward(ACME, k, EXPIRY, Currency.USD)
    profile = equity_exposure_profile(fwd, _process(market), DATES, MC)
    big_t = tm.year_fraction(EXPIRY)
    for d, ee in profile:
        t = tm.year_fraction(d)
        carry = math.exp((R - Q) * (big_t - t))
        df_t_to_T = curve.df(EXPIRY) / curve.df(d)
        want = (
            curve.df(d)  # the profile is discounted to today
            * df_t_to_T * carry
            * black(S0 * math.exp((R - Q) * t), k / carry, VOL, t, OptionType.CALL)
        )
        assert ee == pytest.approx(want, rel=0.03), (d, ee, want)
        assert ee > 0.0


# ── 3. the structural claim ─────────────────────────────────────────────────────────────────
def test_ONE_engine_produces_BOTH_a_rates_and_an_equity_exposure() -> None:
    """The abstraction is real, not a two-branch switch: the equity builder and the HW rates
    builder go through the same `StateProcess` sampler and the same generic core, and neither
    exposure module names a concrete dynamics in a type test."""
    import ast
    import inspect

    import pricebook.risk.exposure as exposure

    tree = ast.parse(inspect.getsource(exposure))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "isinstance":
            arg = ast.unparse(node.args[1])
            assert "HullWhite" not in arg and "BlackScholesProcess" not in arg, arg


def test_the_equity_profile_feeds_the_UNCHANGED_cva_atom() -> None:
    """`cva(profile, survival, recovery)` is untouched across a THIRD asset's exposure — the
    profile/atom split holding is the standing XVA acceptance criterion."""
    import inspect

    from pricebook.risk.xva import cva

    assert list(inspect.signature(cva).parameters) == ["profile", "survival", "recovery"]


def test_seed_reproducibility_is_byte_identical() -> None:
    a = equity_exposure_profile(_option(), _process(), DATES, MonteCarloConfig(paths=5_000, seed=3))
    b = equity_exposure_profile(_option(), _process(), DATES, MonteCarloConfig(paths=5_000, seed=3))
    assert a == b  # invariant 1
    c = equity_exposure_profile(_option(), _process(), DATES, MonteCarloConfig(paths=5_000, seed=4))
    assert a != c


def test_black_vec_IS_black_elementwise() -> None:
    """The identity that keeps two call shapes from becoming two formulas (§3d). `black_vec`
    exists only because 200k scalar `black` calls per date took this file from sub-second to 59s
    — the second instance of the per-path-loop mistake `NG-WATCH-CLOCK` was ledgered for. Having
    a vector twin is fine; having an *unbound* one is how they drift."""
    import numpy as np

    from pricebook.models.black import black, black_vec

    forwards = np.array([40.0, 80.0, 99.999, 100.0, 100.001, 150.0, 400.0])
    for strike in (50.0, 100.0, 200.0):
        for vol in (0.0, 0.05, 0.25, 1.5):
            for t in (0.0, 0.25, 3.0):
                for kind in (OptionType.CALL, OptionType.PUT):
                    got = black_vec(forwards, strike, vol, t, kind)
                    want = [black(float(f), strike, vol, t, kind) for f in forwards]
                    assert np.allclose(got, want, rtol=0.0, atol=0.0), (strike, vol, t, kind)


def test_every_exposure_profile_is_PV_DIMENSIONED_the_convention_cva_requires() -> None:
    """**The gate that was missing when the discounting bug shipped.**

    `cva` weights by the survival increment and discounts **nothing**, so every profile that feeds
    it must already be discounted to today. Three builders did (the rates MC multiplies by
    `model.bond(0,tᵢ,r₀)`; the two analytic ones return a `PricingResult` PV) and the equity one
    did not — so equity CVA was 5.14% too large, while every individual oracle passed, because
    each checked a builder against itself and none compared the builders to one another.

    The check: a profile value must be a **present value**, i.e. bounded by the undiscounted
    expectation and strictly below it whenever rates are positive and the date is in the future.
    Run across both MC builders, with the rates one as the control that was always right."""
    import importlib.util
    import sys

    from pricebook.foundation.numerics import MonteCarloConfig
    from pricebook.risk.exposure import mc_exposure_profile
    from pricebook.risk.mtm import mtm_samples

    market = _market()
    cfg = MonteCarloConfig(paths=20_000, seed=31)

    # equity: the profile must sit BELOW the raw expectation by exactly the discount factor
    option = _option()
    curve = market.curves.discount(Currency.USD, None)
    profile = equity_exposure_profile(option, _process(market), DATES, cfg)
    samples = mtm_samples(option, _process(market), DATES, cfg)
    for (d, ee), (d2, raw) in zip(profile, samples):
        assert d == d2
        undiscounted = float(np.maximum(raw, 0.0).mean())
        assert ee == pytest.approx(curve.df(d) * undiscounted, rel=1e-12), d
        assert ee < undiscounted, d  # positive rates, future date ⇒ strictly discounted

    # rates: the control — this builder discounted from the start, and still does
    sys.path.insert(0, ".")
    spec = importlib.util.spec_from_file_location("mce", "tests/L5/test_mc_exposure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    hw = mod._hw()
    rates_profile = mc_exposure_profile(mod._swap(0.020, 1_000_000.0), hw, cfg)
    disc = hw.market.curves.discount(hw.currency)
    # the rates control, asserted against its own samples the same way (not a tautology — the
    # first draft wrote `ee < ee/df`, which is true for any positive ee and tests nothing)
    swap = mod._swap(0.020, 1_000_000.0)
    for d, ee in rates_profile:
        if ee <= 0.0:
            continue
        raw = mtm_samples(swap, hw, (d,), cfg)[0][1]
        undiscounted = abs(swap.notional) * float(np.maximum(raw / swap.notional, 0.0).mean())
        assert ee == pytest.approx(disc.df(d) * undiscounted, rel=5e-2), (d, ee, undiscounted)
