"""`StateProcess` — the simulatable-dynamics abstraction, introduced with BOTH its consumers.

§6b's rule of two, met at birth rather than anticipated: Hull-White's exact Gaussian sampler is
**refactored onto** the protocol (no behaviour change — the byte-identity capture proves it), and
`BlackScholesProcess` is written against it. One signature, two asset classes, and the generic MC
core composes it without knowing which it holds.

The protocol is the **marginal exact sampler** both dynamics already had: `sample_state(t, …)`
draws the state variable at one date under that date's own forward measure. It is deliberately
NOT a path/grid sampler — neither consumer needs stepping (both transitions are exact), and a grid
would be a knob that cannot change the answer (`MonteCarloConfig` says so). A joint-path shape
arrives with the first consumer that needs one (wrong-way risk), named rather than guessed.
"""

import math
from datetime import date

import numpy as np
import pytest

from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.models.process import BlackScholesProcess, StateProcess
from pricebook.risk.monte_carlo import mc_mean

MC = MonteCarloConfig(paths=200_000, seed=4242)


# ── the abstraction is real: both dynamics satisfy ONE protocol ──────────────────────────────
def test_hull_white_and_black_scholes_both_satisfy_the_SAME_protocol() -> None:
    """The structural claim. If either needed its own interface the abstraction would be a
    two-branch switch wearing a protocol's clothes."""
    import importlib.util
    import sys

    sys.path.insert(0, ".")
    spec = importlib.util.spec_from_file_location("mce", "tests/L5/test_mc_exposure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    hw = mod._hw()
    bs = _bs_process()
    assert isinstance(hw, StateProcess)
    assert isinstance(bs, StateProcess)
    for p in (hw, bs):
        drawn = p.sample_state(1.0, MonteCarloConfig(paths=16, seed=1))
        assert isinstance(drawn, np.ndarray) and drawn.shape == (16,)


def _bs_process() -> BlackScholesProcess:
    from pricebook.foundation import Currency
    from pricebook.foundation.equity import EquityUnderlying
    from pricebook.market.curve import DiscountCurve
    from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
    from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey, MarketSnapshot
    from pricebook.market.vol_surface import EquitySurfaceKey, Surface
    from pricebook.models.black import vol_time_measure

    val = date(2026, 1, 15)
    acme = EquityUnderlying("ACME")
    curve = DiscountCurve(
        time_measure=vol_time_measure(val), times=(0.0, 10.0), dfs=(1.0, math.exp(-0.05 * 10.0))
    )
    market = MarketSnapshot(
        valuation_date=val,
        curves=CurveSet({CurveKey(CurveRole.DISCOUNT, Currency.USD, None): curve}),
        scalars={EquitySpotKey(acme): 100.0, DividendYieldKey(acme): 0.03},
        surfaces={EquitySurfaceKey(acme): Surface(vols=(0.20,))},
    )
    return BlackScholesProcess(market=market, underlying=acme, currency=Currency.USD)


# ── BlackScholesProcess: exact lognormal sampling, checked against the analytic moments ─────
def test_the_sampled_spot_has_the_RISK_NEUTRAL_FORWARD_as_its_mean() -> None:
    """`E[S_t] = S₀·e^{(r−q)t}` — the forward, not the spot. Getting this wrong (dropping the
    `−½σ²` in the exponent, or the dividend) biases every equity MC price, and a price-level test
    would hide it inside the option's convexity. Checked on the drawn states directly."""
    s = _bs_process().sample_state(1.0, MC)
    want = 100.0 * math.exp((0.05 - 0.03) * 1.0)
    stderr = float(np.std(s, ddof=1)) / math.sqrt(MC.paths)
    assert abs(float(np.mean(s)) - want) < 3.0 * stderr, (float(np.mean(s)), want, stderr)


def test_the_sampled_spot_has_the_LOGNORMAL_variance() -> None:
    """`Var[S_t] = S₀²e^{2(r−q)t}(e^{σ²t} − 1)` — a second moment, so it catches a σ used as a
    variance (or a √t dropped) that the mean alone cannot see."""
    s = _bs_process().sample_state(1.0, MC)
    f = 100.0 * math.exp((0.05 - 0.03) * 1.0)
    want = f * f * (math.exp(0.20**2 * 1.0) - 1.0)
    assert float(np.var(s, ddof=1)) == pytest.approx(want, rel=0.02)


def test_sampling_is_reproducible_and_seed_dependent() -> None:
    p = _bs_process()
    cfg = MonteCarloConfig(paths=500, seed=11)
    assert np.array_equal(p.sample_state(1.0, cfg), p.sample_state(1.0, cfg))  # invariant 1
    other = MonteCarloConfig(paths=500, seed=12)
    assert not np.array_equal(p.sample_state(1.0, cfg), p.sample_state(1.0, other))


def test_zero_vol_collapses_to_the_deterministic_forward() -> None:
    from pricebook.market.vol_surface import EquitySurfaceKey, Surface
    from dataclasses import replace as dc_replace

    p = _bs_process()
    flat = dc_replace(
        p, market=dc_replace(p.market, surfaces={EquitySurfaceKey(p.underlying): Surface(vols=(0.0,))})
    )
    s = flat.sample_state(1.0, MonteCarloConfig(paths=32, seed=1))
    assert np.allclose(s, 100.0 * math.exp((0.05 - 0.03) * 1.0))


# ── the arc's point: MC over BS paths reproduces c1's closed form ───────────────────────────
def test_a_european_equity_option_by_MC_reproduces_c1s_CLOSED_FORM() -> None:
    """**The (c) arc's anchor doing its job.** c1 was built first precisely so the MC has a rung-1
    reference, and this is the check: the MC price over `BlackScholesProcess` states, through the
    generic `mc_mean` core, must agree with the c1 pricer within 3 standard errors.

    Note what this tests that the moment tests do not: the whole composition — sampler, payoff,
    discounting — against an independent closed form, rather than the sampler's marginals against
    their own formulas."""
    from pricebook.engine.equity import price_equity_option
    from pricebook.foundation import PricingResult
    from pricebook.models.black_model import BlackModel
    from pricebook.products.equity import EquityOption
    from pricebook.products.option import OptionType

    p = _bs_process()
    expiry = date(2027, 1, 15)
    t = 365.0 / 365.0
    df = math.exp(-0.05 * t)

    for strike in (80.0, 100.0, 120.0):
        payoffs = mc_mean(p, t, MC, lambda s, k=strike: np.maximum(s - k, 0.0))
        mc_price = df * payoffs.mean
        stderr = df * payoffs.stderr
        closed = price_equity_option(
            EquityOption(p.underlying, strike, expiry, OptionType.CALL, p.currency),
            BlackModel(market=p.market),
        )
        assert isinstance(closed, PricingResult), closed
        assert abs(mc_price - closed.pv.amount) < 3.0 * stderr, (
            strike, mc_price, closed.pv.amount, stderr,
        )


def test_the_generic_core_names_NEITHER_concrete_process() -> None:
    """The abstraction is structural: `mc_mean` must not mention `HullWhite` or
    `BlackScholesProcess`, or it is a switch rather than a protocol (§1)."""
    import inspect

    import pricebook.risk.monte_carlo as core

    src = inspect.getsource(core)
    assert "HullWhite" not in src
    assert "BlackScholesProcess" not in src
