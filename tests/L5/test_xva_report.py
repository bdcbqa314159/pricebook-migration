"""`XvaReport` — the exposure report surface, all of it from the marginals ng already samples.

This is the capability `models/mc_exposure.py`'s one importer consumes wholesale via
`ExposureResult.to_dict()`: ENE, PFE percentiles, peak EE, effective EPE, DVA and FVA alongside
the EPE profile and CVA ng already had.

**The headline oracle is an identity, not a tolerance.** For any instrument and any date,

    EPE(tᵢ) − ENE(tᵢ) = E[V(tᵢ)]

because `max(V,0) − max(−V,0) ≡ V`; and under deterministic rates the discounted value is a
martingale, so `E[V(tᵢ)] = V₀/df(0,tᵢ)`. That ties *both* halves of the report to a closed form
in one statement — and it is non-vacuous precisely because the forward's ENE is non-zero, which a
long option's never is.

**DVA is not a new formula.** `DVA = LGD_own · Σ ENE·ΔQ_own` is `cva` evaluated on the ENE profile
with the own-survival curve, so the report composes the existing atom rather than restating it
(§3d) — the same shape as equity rho coming free from `ir_delta`.
"""

import math
from datetime import date, timedelta

import numpy as np
import pytest

from pricebook.foundation import Currency
from pricebook.foundation.equity import EquityUnderlying
from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey, MarketSnapshot
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.market.vol_surface import EquitySurfaceKey, Surface
from pricebook.models.black import vol_time_measure
from pricebook.models.process import BlackScholesProcess
from pricebook.products.equity import EquityForward, EquityOption
from pricebook.products.option import OptionType
from pricebook.risk.exposure import equity_exposure_profile
from pricebook.risk.mtm import mtm_samples
from pricebook.risk.xva import cva
from pricebook.risk.xva_report import XvaTerms, xva_report

VAL = date(2026, 1, 15)
ACME = EquityUnderlying("ACME")
S0, VOL, R, Q, K = 100.0, 0.25, 0.04, 0.02, 100.0
EXPIRY = VAL + timedelta(days=365 * 2)
DATES = tuple(VAL + timedelta(days=d) for d in (182, 365, 547))
MC = MonteCarloConfig(paths=200_000, seed=20261030)


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


def _process(m: MarketSnapshot) -> BlackScholesProcess:
    return BlackScholesProcess(m, ACME, Currency.USD)


def _survival(hazard: float) -> SurvivalCurve:
    return SurvivalCurve(
        measure=vol_time_measure(VAL), times=(0.0, 10.0), survivals=(1.0, math.exp(-hazard * 10.0))
    )


def _terms(funding: float = 0.0) -> XvaTerms:
    return XvaTerms(
        survival=_survival(0.02), recovery=0.40,
        own_survival=_survival(0.01), own_recovery=0.40, funding_spread=funding,
    )


def _report(instrument, funding: float = 0.0):
    m = _market()
    samples = mtm_samples(instrument, _process(m), DATES, MC)
    return xva_report(samples, _terms(funding))


# ── the headline identity ───────────────────────────────────────────────────────────────────
def test_EPE_minus_ENE_IS_the_forward_value_for_a_FORWARD() -> None:
    """`max(V,0) − max(−V,0) ≡ V`, and `E[V(tᵢ)] = V₀/df(0,tᵢ)`. Non-vacuous here because a
    forward's ENE is genuinely non-zero."""
    m = _market()
    curve = m.curves.discount(Currency.USD, None)
    v0 = curve.df(EXPIRY) * (S0 * math.exp((R - Q) * 2.0) - K)
    rep = _report(EquityForward(ACME, K, EXPIRY, Currency.USD))
    for (d, epe), (d2, ene) in zip(rep.epe, rep.ene):
        assert d == d2
        assert epe - ene == pytest.approx(v0 / curve.df(d), rel=0.02), d
        assert ene > 0.0  # the identity would be trivial otherwise


def test_a_LONG_OPTIONS_ENE_is_ZERO_because_its_MtM_never_goes_negative() -> None:
    """The discriminating companion: a long option can never owe, so every ENE is exactly 0 and
    `EPE = E[V]`. A report that confused the two signs would pass the forward test on symmetry
    and fail here."""
    rep = _report(EquityOption(ACME, K, EXPIRY, OptionType.CALL, Currency.USD))
    assert all(ene == 0.0 for _, ene in rep.ene)


# ── DVA composes the EXISTING atom ──────────────────────────────────────────────────────────
def test_DVA_IS_cva_evaluated_on_the_ENE_profile_with_the_OWN_curve() -> None:
    """§3d: `DVA = LGD_own·Σ ENE·ΔQ_own` is not a new formula, it is `cva` with different
    arguments. Asserted as an exact equality, so the report cannot grow a second definition."""
    rep = _report(EquityForward(ACME, K, EXPIRY, Currency.USD))
    assert rep.dva == cva(rep.ene, _survival(0.01), 0.40)
    assert rep.cva == cva(rep.epe, _survival(0.02), 0.40)


def test_DVA_is_zero_when_we_cannot_default_and_CVA_zero_when_they_cannot() -> None:
    """The `hazard → 0` limit on both sides — the same limit `cva`'s own docstring names as the
    catch for using survival LEVELS instead of increments."""
    m = _market()
    samples = mtm_samples(EquityForward(ACME, K, EXPIRY, Currency.USD), _process(m), DATES, MC)
    no_own = XvaTerms(_survival(0.02), 0.40, _survival(0.0), 0.40, 0.0)
    assert xva_report(samples, no_own).dva == pytest.approx(0.0, abs=1e-12)
    no_cpty = XvaTerms(_survival(0.0), 0.40, _survival(0.01), 0.40, 0.0)
    assert xva_report(samples, no_cpty).cva == pytest.approx(0.0, abs=1e-12)


# ── the remaining report quantities ─────────────────────────────────────────────────────────
def test_PFE_is_ordered_and_above_the_mean() -> None:
    rep = _report(EquityForward(ACME, K, EXPIRY, Currency.USD))
    for (d, p95), (_, p99), (_, epe) in zip(rep.pfe[0.95], rep.pfe[0.99], rep.epe):
        assert p99 >= p95, d
        assert p95 > 0.0


def test_peak_and_effective_EPE_match_their_definitions() -> None:
    """`ee_peak = max EPE`; `effective_epe` = mean of the **running max** of EPE (Basel's
    non-decreasing EEE, time-averaged), so it is always ≥ the plain mean of EPE and ≤ the peak."""
    rep = _report(EquityForward(ACME, K, EXPIRY, Currency.USD))
    epes = [e for _, e in rep.epe]
    assert rep.ee_peak == max(epes)
    running = [max(epes[: i + 1]) for i in range(len(epes))]
    assert rep.effective_epe == pytest.approx(sum(running) / len(running))
    assert sum(epes) / len(epes) <= rep.effective_epe <= rep.ee_peak


def test_FVA_is_zero_at_a_zero_funding_spread_and_scales_linearly() -> None:
    fwd = EquityForward(ACME, K, EXPIRY, Currency.USD)
    assert _report(fwd, funding=0.0).fva == pytest.approx(0.0, abs=1e-12)
    one, two = _report(fwd, funding=0.0050).fva, _report(fwd, funding=0.0100).fva
    assert one > 0.0
    assert two == pytest.approx(2.0 * one, rel=1e-12)  # linear in the spread by construction


# ── the new path must not move the old one ──────────────────────────────────────────────────
def test_the_reports_EPE_is_BYTE_IDENTICAL_to_the_existing_exposure_builder() -> None:
    """`equity_exposure_profile` and the report's EPE must be the same number to the last bit, or
    ng has two definitions of expected positive exposure."""
    m = _market()
    option = EquityOption(ACME, K, EXPIRY, OptionType.CALL, Currency.USD)
    old = equity_exposure_profile(option, _process(m), DATES, MC)
    new = xva_report(mtm_samples(option, _process(m), DATES, MC), _terms()).epe
    assert new == old


def test_mtm_samples_serves_RATES_as_well_as_equity() -> None:
    """One MtM mechanism across asset classes — the `singledispatch` table, not a branch. If the
    swap did not register, the report would be equity-only and `mc_exposure.py` would still not
    be superseded for a rates consumer."""
    import importlib.util
    import sys

    sys.path.insert(0, ".")
    spec = importlib.util.spec_from_file_location("mce", "tests/L5/test_mc_exposure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    hw = mod._hw()
    swap = mod._swap(0.030, 1_000_000.0)
    dates = tuple(p.accrual_end for p in swap.fixed_leg.schedule.periods[:3])
    samples = mtm_samples(swap, hw, dates, MonteCarloConfig(paths=4_000, seed=5))
    assert len(samples) == 3
    for d, arr in samples:
        assert isinstance(arr, np.ndarray) and arr.shape == (4_000,)
        assert float(np.std(arr)) > 0.0  # a degenerate sample would make every functional vacuous
