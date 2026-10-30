"""Wrong-way risk — exposure and default correlated, and ONE `cva` that consumes both.

**The profile shape does not change, and that is the design.** Unilateral CVA is

    CVA = LGD · Σ E[ (V(tᵢ))⁺ | default in (tᵢ₋₁, tᵢ] ] · ΔQ(tᵢ)

Independence makes the conditional expectation equal the unconditional one, which is *exactly*
ng's existing `LGD · Σ EE(tᵢ)·ΔQ(tᵢ)`. So WWR does not need a richer profile type: it needs the
same `(date, EE)` tuple with **conditionally** computed values. The marginal profile is the ρ=0
degeneracy of the WWR profile, the same `cva` consumes both, and there is no second CVA.

**The ρ→0 identity is exact by construction, not by a branch.** Under the Gaussian copula,
`Z_exposure = ρ·Z_default + √(1−ρ²)·W`. At ρ=0 that collapses to `Z_exposure = W`, and `W` is drawn
from the *same* seeded stream the marginal sampler uses — so the states are identical draws and the
conditional profile reproduces the marginal one to floating-point, with no `if rho == 0` anywhere.
An implementation that special-cased ρ=0 would make this test vacuous, which is the failure mode
this project keeps finding.
"""

import math
from datetime import date, timedelta

import numpy as np
import pytest

from pricebook.foundation import Currency
from pricebook.foundation.equity import EquityUnderlying
from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import (
    CorrelationKey,
    DividendYieldKey,
    EquitySpotKey,
    MarketSnapshot,
)
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.market.vol_surface import EquitySurfaceKey, Surface
from pricebook.models.black import vol_time_measure
from pricebook.models.process import BlackScholesProcess
from pricebook.products.equity import EquityForward, EquityOption
from pricebook.products.option import OptionType
from pricebook.risk.exposure import equity_exposure_profile
from pricebook.risk.wwr import wwr_exposure_profile
from pricebook.risk.xva import cva

VAL = date(2026, 1, 15)
ACME = EquityUnderlying("ACME")
CP = ReferenceEntity("COUNTERPARTY")
S0, VOL, R, Q, K = 100.0, 0.25, 0.04, 0.02, 100.0
EXPIRY = VAL + timedelta(days=365 * 3)
DATES = tuple(VAL + timedelta(days=365 * n) for n in (1, 2, 3))
MC = MonteCarloConfig(paths=400_000, seed=20261031)
HAZARD = 0.03


def _survival() -> SurvivalCurve:
    return SurvivalCurve(
        measure=vol_time_measure(VAL), times=(0.0, 20.0), survivals=(1.0, math.exp(-HAZARD * 20.0))
    )


def _market(rho: float) -> MarketSnapshot:
    curve = DiscountCurve(
        time_measure=vol_time_measure(VAL), times=(0.0, 30.0), dfs=(1.0, math.exp(-R * 30.0))
    )
    return MarketSnapshot(
        valuation_date=VAL,
        curves=CurveSet(
            {
                CurveKey(CurveRole.DISCOUNT, Currency.USD, None): curve,
                CurveKey(CurveRole.SURVIVAL, CP): _survival(),
            }
        ),
        scalars={
            EquitySpotKey(ACME): S0,
            DividendYieldKey(ACME): Q,
            CorrelationKey(CP, ACME): rho,
        },
        surfaces={EquitySurfaceKey(ACME): Surface(vols=(VOL,))},
    )


def _process(rho: float) -> BlackScholesProcess:
    return BlackScholesProcess(_market(rho), ACME, Currency.USD)


def _fwd() -> EquityForward:
    return EquityForward(ACME, K, EXPIRY, Currency.USD)


def _wwr(rho: float, instrument=None):
    return wwr_exposure_profile(instrument or _fwd(), _process(rho), CP, DATES, MC)


# ── 1. THE anchor: the WWR machinery reduces to the marginal CVA at zero correlation ────────
def test_at_ZERO_correlation_the_wwr_profile_IS_the_marginal_profile() -> None:
    """The generalization identity. Not a tolerance on a different estimator — the same seeded
    draws, so this is floating-point agreement on identical inputs."""
    option = EquityOption(ACME, K, EXPIRY, OptionType.CALL, Currency.USD)
    marginal = equity_exposure_profile(option, _process(0.0), DATES, MC)
    joint = _wwr(0.0, option)
    assert [d for d, _ in joint] == [d for d, _ in marginal]
    for (_, a), (_, b) in zip(joint, marginal):
        assert a == pytest.approx(b, rel=1e-12), (a, b)


def test_at_ZERO_correlation_the_SAME_cva_gives_the_SAME_number() -> None:
    """One `cva`, not two: the atom is handed a WWR profile and a marginal profile and must agree
    at ρ=0. If WWR had needed its own CVA definition this could not be asserted at all."""
    surv, rec = _survival(), 0.40
    marginal = cva(equity_exposure_profile(_fwd(), _process(0.0), DATES, MC), surv, rec)
    wwr = cva(_wwr(0.0), surv, rec)
    assert wwr == pytest.approx(marginal, rel=1e-12)
    assert marginal > 0.0  # the identity would be trivial on a zero CVA


def test_the_wwr_profile_is_NOT_special_cased_at_rho_zero() -> None:
    """Guards the oracle above against the failure mode this project keeps finding: an
    `if rho == 0: return marginal` would make the anchor vacuous. Asserted on the AST — no
    comparison of a correlation against zero that returns early."""
    import ast
    import inspect

    import pricebook.risk.wwr as wwr

    tree = ast.parse(inspect.getsource(wwr))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name):
            if "rho" in node.left.id or "corr" in node.left.id:
                parent_is_guard = any(
                    isinstance(n, ast.If) and node in ast.walk(n) for n in ast.walk(tree)
                )
                assert not parent_is_guard, f"rho is branched on: {ast.unparse(node)}"


def test_rho_zero_continuity_small_rho_stays_near_the_marginal() -> None:
    """The identity holds *at* zero; this says the map is continuous there, so ρ=0 is not an
    isolated coincidence of the seeding."""
    base = cva(_wwr(0.0), _survival(), 0.40)
    near = cva(_wwr(0.02), _survival(), 0.40)
    assert near == pytest.approx(base, rel=0.05), (base, near)


# ── 2. sign and monotonicity — the structural claim a scalar match misses ────────────────────
def test_WRONG_way_correlation_RAISES_cva_and_RIGHT_way_LOWERS_it() -> None:
    """For a long forward, exposure rises with spot. **ρ > 0 is wrong-way by construction**: the
    default driver is signed so larger means *earlier* default, so positive ρ pairs early default
    with high spot — we are owed more exactly when they fail — and CVA must rise. Negative ρ is
    right-way and must lower it.

    That signing is a *decision*, documented in `risk/wwr.py`, not an accident of the copula
    parametrisation: with the driver taken as `Φ⁻¹` of the default CDF (its natural form) the sign
    is reversed, and "ρ > 0 is wrong-way" would be a claim about the parametrisation rather than
    about economics. The first implementation had exactly that, and these three tests are what
    found it. A sign error here is the classic WWR mistake and no magnitude check catches it."""
    surv, rec = _survival(), 0.40
    at_zero = cva(_wwr(0.0), surv, rec)
    wrong_way = cva(_wwr(0.60), surv, rec)
    right_way = cva(_wwr(-0.60), surv, rec)
    assert wrong_way > at_zero > right_way, (wrong_way, at_zero, right_way)


def test_cva_is_MONOTONE_in_the_correlation() -> None:
    surv, rec = _survival(), 0.40
    cvas = [cva(_wwr(r), surv, rec) for r in (-0.8, -0.4, 0.0, 0.4, 0.8)]
    assert cvas == sorted(cvas), cvas
    assert cvas[-1] > 1.5 * cvas[0], cvas  # the effect is material, not noise


# ── 3. the conditional expectation itself ───────────────────────────────────────────────────
def test_the_conditional_exposure_moves_with_rho_in_the_right_direction() -> None:
    """One level below CVA: the *profile* must shift, not just the aggregate. Checking only CVA
    would pass if the conditioning leaked in through the survival weights instead."""
    lo = [ee for _, ee in _wwr(-0.6)]
    mid = [ee for _, ee in _wwr(0.0)]
    hi = [ee for _, ee in _wwr(0.6)]
    for a, b, c in zip(lo, mid, hi):
        assert a < b < c, (a, b, c)


def test_correlation_is_L1_market_state_keyed_and_bumpable() -> None:
    from pricebook.risk.bump import ScalarBump

    key = CorrelationKey(CP, ACME)
    assert key == CorrelationKey(CP, ACME)  # keyed by VALUE
    bumped = ScalarBump(key).apply(_market(0.3), 0.1)
    assert bumped.scalars[key] == pytest.approx(0.4)


def test_an_out_of_range_correlation_is_REFUSED() -> None:
    with pytest.raises(ValueError, match="correlation"):
        wwr_exposure_profile(_fwd(), _process(1.4), CP, DATES, MC)


def test_seed_reproducibility() -> None:
    cfg = MonteCarloConfig(paths=20_000, seed=9)
    a = wwr_exposure_profile(_fwd(), _process(0.5), CP, DATES, cfg)
    b = wwr_exposure_profile(_fwd(), _process(0.5), CP, DATES, cfg)
    assert a == b


def test_the_driver_factoring_keeps_the_marginal_sampler_intact() -> None:
    """`sample_state` must now compose `state_from_normal` — one mapping from the standard normal
    to the state, shared by the marginal and the correlated samplers (§3d). If they were two
    mappings, ρ=0 agreement would be a coincidence of two formulas rather than an identity."""
    p = _process(0.0)
    cfg = MonteCarloConfig(paths=1_000, seed=3)
    z = np.random.default_rng((cfg.seed, round(1.0 * 1_000_000))).standard_normal(cfg.paths)
    assert np.array_equal(p.sample_state(1.0, cfg), p.state_from_normal(1.0, z))


def test_norm_ppf_vec_IS_norm_ppf_elementwise() -> None:
    """The identity binding the vector inverse-CDF to the scalar one (§3d), the same guard
    `black_vec` carries. It exists because the scalar version inside a 400k-path loop did not
    finish inside a 120-second timeout — the third per-path-loop instance in this project."""
    from pricebook.foundation.distributions import norm_ppf, norm_ppf_vec

    xs = np.array([1e-9, 0.001, 0.1, 0.5, 0.9, 0.999, 1 - 1e-9])
    assert np.allclose(norm_ppf_vec(xs), [norm_ppf(float(x)) for x in xs], rtol=0.0, atol=0.0)
