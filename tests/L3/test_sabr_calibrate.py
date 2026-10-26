"""L3 oracle — SABR smile calibration (T1 slice 21).

Known-value oracle (stronger than self-consistency):
1. ROUND-TRIP — a smile generated from a KNOWN seed `SabrParams` at the model-derived forward is
   calibrated back to that seed to tol. Recovers a known answer AND verifies the §3d F-identity by
   construction (the fit's F is the one `SABRModel.implied_vol` reads).
2. REPRICE — the fitted params, written to a `SabrSurface`, make `SABRModel.implied_vol` reproduce each
   target market vol: calibrate-to-quote == price-to-smile, one fact (§3d).
3. FAILURE-AS-VALUE — a smile outside the law's domain (a non-positive strike under the lognormal
   law) returns `CalibrationFailure`, never a raise or a silent bad fit.

Slice 22 adds the ACCEPTANCE GATE (ruling 1 — a converged-but-unacceptable fit is a failure, not a
result with big residuals) and the same two oracles under the NORMAL and SHIFTED laws: the
calibrator composes `model.vol_law.sabr_vol`, so one code path fits every law in its own units.
"""

from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, CalibrationResult, SolveConfig
from pricebook.calibration.sabr_calibrate import SabrCalibrationSpec, calibrate_sabr_smile
from pricebook.foundation import (
    Accrual,
    DayCountConvention,
    Tenor,
    TenorUnit,
    TimeMeasure,
    get_rate_index,
)
from pricebook.market.building_blocks import forward
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.quotes import SmileQuote
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import SabrParams, SabrSurface, SurfaceKey, VolLawKind
from pricebook.models.sabr import sabr_normal_vol, sabr_vol
from pricebook.models.sabr_model import SABRModel

VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
DC365 = DayCountConvention.ACT_365_FIXED
TM = TimeMeasure(VAL, DC365)
EXPIRY = VAL + Tenor(1, TenorUnit.YEAR)
BETA = 0.5
SEED = SabrParams(alpha=0.20, beta=BETA, rho=-0.30, nu=0.40)


def _model() -> SABRModel:
    disc = DiscountCurve.flat(TM, 0.030, until=EXPIRY + Tenor(6, TenorUnit.MONTH))
    proj = DiscountCurve.flat(TM, 0.035, until=EXPIRY + Tenor(6, TenorUnit.MONTH))
    curves = CurveSet(
        {CurveKey(CurveRole.DISCOUNT, CCY): disc, CurveKey(CurveRole.PROJECTION, INDEX): proj}
    )
    return SABRModel(MarketSnapshot(VAL, curves))


def _forward(model: SABRModel) -> float:
    accrual = Accrual(EXPIRY, EXPIRY + INDEX.id.tenor, INDEX.accrual.day_count)
    return forward(model.market.curves.projection(INDEX), accrual)


def _seed_smile(model: SABRModel) -> SmileQuote:
    fwd = _forward(model)
    t = TM.year_fraction(EXPIRY)
    strikes = tuple(fwd + d for d in (-0.015, -0.007, 0.0, 0.007, 0.015, 0.025))
    vols = tuple(sabr_vol(fwd, k, t, SEED) for k in strikes)
    return SmileQuote(EXPIRY, strikes, vols, fwd)


def test_sabr_calibration_round_trip_recovers_seed() -> None:
    model = _model()
    spec = SabrCalibrationSpec(model, _seed_smile(model), BETA, SolveConfig(tolerance=1e-12))
    out = calibrate_sabr_smile(spec)
    assert not isinstance(out, CalibrationFailure)
    params, result = out
    assert isinstance(result, CalibrationResult) and result.converged
    assert abs(params.alpha - SEED.alpha) < 1e-6
    assert abs(params.rho - SEED.rho) < 1e-6
    assert abs(params.nu - SEED.nu) < 1e-6
    assert params.beta == BETA  # β is fixed, not fitted
    assert all(abs(r) < 1e-8 for r in result.residuals)


def test_the_fit_produces_one_residual_PER_QUOTED_STRIKE() -> None:
    """Floor-on-population on the fit's own collection (CLAUDE.md §6 second clause; found as O1 in
    `CP_swaption_cluster.md`). The acceptance gate takes `max(abs(r) for r in residuals)` — a short
    residual list would pass the gate on a subset while the remaining strikes went unfitted. The
    length is guaranteed today by `SmileQuote`'s own strikes/vols invariant, so this asserts a
    property the type already holds: the cube took the same posture deliberately (the type makes a
    drop unrepresentable AND the oracle asserts it), and this closes the one cluster gate that
    relied on the invariant alone."""
    model = _model()
    smile = _seed_smile(model)
    out = calibrate_sabr_smile(SabrCalibrationSpec(model, smile, BETA))
    assert not isinstance(out, CalibrationFailure), out
    _params, result = out
    assert len(result.residuals) == len(smile.strikes) == 6


def test_sabr_calibration_reprice_identity_through_model() -> None:
    # the fitted params, read back by SABRModel, reproduce the target smile at the SAME forward (§3d)
    model = _model()
    smile = _seed_smile(model)
    out = calibrate_sabr_smile(SabrCalibrationSpec(model, smile, BETA))
    assert not isinstance(out, CalibrationFailure)
    params, _ = out
    fitted = SABRModel(
        MarketSnapshot(VAL, model.market.curves, surfaces={SurfaceKey(INDEX): SabrSurface({EXPIRY: params})})
    )
    for strike, target in zip(smile.strikes, smile.vols):
        assert abs(fitted.implied_vol(INDEX, EXPIRY, strike, _forward(fitted)) - target) < 1e-6


def test_sabr_calibration_degenerate_smile_is_a_failure_value() -> None:
    # a non-positive strike makes the lognormal SABR vol undefined → CalibrationFailure, not a raise
    model = _model()
    fwd = _forward(model)
    t = TM.year_fraction(EXPIRY)
    strikes = (-0.005, 0.0, fwd, fwd + 0.01)  # ascending, but two non-positive strikes
    vols = tuple(0.2 for _ in strikes)
    spec = SabrCalibrationSpec(model, SmileQuote(EXPIRY, strikes, vols, fwd), BETA)
    assert isinstance(calibrate_sabr_smile(spec), CalibrationFailure)


def test_smile_quote_validates_its_shape() -> None:
    import pytest

    with pytest.raises(ValueError):
        SmileQuote(EXPIRY, (0.02, 0.03), (0.2, 0.2), 0.03)  # <3 points
    with pytest.raises(ValueError):
        SmileQuote(EXPIRY, (0.02, 0.03, 0.04), (0.2, 0.2), 0.03)  # length mismatch
    with pytest.raises(ValueError):
        SmileQuote(EXPIRY, (0.04, 0.03, 0.02), (0.2, 0.2, 0.2), 0.03)  # not ascending


# ── slice 22: the acceptance gate (ruling 1) and the per-law fits ──────────────────────────
def _laws_model(kind: VolLawKind, shift: float, params: SabrParams) -> SABRModel:
    base = _model()
    snap = MarketSnapshot(
        VAL,
        base.market.curves,
        surfaces={SurfaceKey(INDEX): SabrSurface({EXPIRY: params}, kind, shift)},
    )
    return SABRModel.for_index(snap, INDEX)


def _negative_model(kind: VolLawKind, shift: float, params: SabrParams) -> SABRModel:
    # a flat NEGATIVE projection curve: the case the lognormal law cannot express at all
    until = EXPIRY + Tenor(6, TenorUnit.MONTH)
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.010, until=until),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, -0.005, until=until),
        }
    )
    snap = MarketSnapshot(VAL, curves, surfaces={SurfaceKey(INDEX): SabrSurface({EXPIRY: params}, kind, shift)})
    return SABRModel.for_index(snap, INDEX)


def test_contradictory_smile_is_a_calibration_failure() -> None:
    # RULING 1: scipy TRF genuinely CONVERGES on a smile no SABR can fit (a V with a vol spike),
    # so "converged" cannot be the contract. A converged-but-unacceptable fit is a FAILURE value
    # carrying its residuals — never a result the caller must remember to inspect (invariant 4).
    model = _model()
    fwd = _forward(model)
    strikes = tuple(fwd + d for d in (-0.015, -0.007, 0.0, 0.007, 0.015, 0.025))
    vols = (0.20, 0.60, 0.21, 0.62, 0.22, 0.61)  # alternating — no smooth smile goes through it
    out = calibrate_sabr_smile(SabrCalibrationSpec(model, SmileQuote(EXPIRY, strikes, vols, fwd), BETA))
    assert isinstance(out, CalibrationFailure), out
    assert out.residuals  # the gate REPORTS why it rejected, in vol units
    assert max(abs(r) for r in out.residuals) > 1e-4


def test_an_acceptable_fit_is_not_rejected_by_the_gate() -> None:
    # the control: a smile that IS a SABR smile passes the same gate (no false positive)
    model = _model()
    out = calibrate_sabr_smile(SabrCalibrationSpec(model, _seed_smile(model), BETA))
    assert not isinstance(out, CalibrationFailure), out


def test_round_trip_under_the_normal_law() -> None:
    # the SAME known-answer oracle, in NORMAL vol units: the fit composes the model's own law,
    # so nothing in the calibrator knows which law it is fitting (§3d)
    seed = SabrParams(alpha=0.0060, beta=0.0, rho=-0.30, nu=0.40)
    model = _laws_model(VolLawKind.NORMAL, 0.0, seed)
    fwd, t = _forward(model), TM.year_fraction(EXPIRY)
    strikes = tuple(fwd + d for d in (-0.015, -0.007, 0.0, 0.007, 0.015, 0.025))
    smile = SmileQuote(EXPIRY, strikes, tuple(sabr_normal_vol(fwd, k, t, seed) for k in strikes), fwd)
    out = calibrate_sabr_smile(SabrCalibrationSpec(model, smile, 0.0))
    assert not isinstance(out, CalibrationFailure), out
    params, result = out
    assert abs(params.alpha - seed.alpha) < 1e-8
    assert abs(params.rho - seed.rho) < 1e-6
    assert abs(params.nu - seed.nu) < 1e-6
    assert result.converged
    # reprice identity: the fitted params, read back through the model, reproduce the smile
    fitted = _laws_model(VolLawKind.NORMAL, 0.0, params)
    for strike, target in zip(smile.strikes, smile.vols):
        assert abs(fitted.implied_vol(INDEX, EXPIRY, strike, _forward(fitted)) - target) < 1e-8


def test_round_trip_under_the_shifted_law_with_a_negative_forward() -> None:
    # the case shifted SABR exists for: a NEGATIVE forward, which the lognormal law cannot fit at all
    seed = SabrParams(alpha=0.20, beta=0.5, rho=-0.30, nu=0.40)
    shift = 0.030
    model = _negative_model(VolLawKind.SHIFTED_LOGNORMAL, shift, seed)
    fwd, t = _forward(model), TM.year_fraction(EXPIRY)
    assert fwd < 0.0
    strikes = tuple(fwd + d for d in (0.002, 0.008, 0.016, 0.024, 0.032))
    smile = SmileQuote(EXPIRY, strikes, tuple(sabr_vol(fwd + shift, k + shift, t, seed) for k in strikes), fwd)
    out = calibrate_sabr_smile(SabrCalibrationSpec(model, smile, 0.5))
    assert not isinstance(out, CalibrationFailure), out
    params, _ = out
    assert abs(params.alpha - seed.alpha) < 1e-6
    assert abs(params.rho - seed.rho) < 1e-6
    assert abs(params.nu - seed.nu) < 1e-6
    fitted = _negative_model(VolLawKind.SHIFTED_LOGNORMAL, shift, params)
    for strike, target in zip(smile.strikes, smile.vols):
        assert abs(fitted.implied_vol(INDEX, EXPIRY, strike, _forward(fitted)) - target) < 1e-6


def test_negative_forward_smile_fails_under_the_lognormal_law() -> None:
    # the law's domain decides, in the calibrator exactly as in the engine (one definition)
    seed = SabrParams(alpha=0.20, beta=0.5, rho=-0.30, nu=0.40)
    model = _negative_model(VolLawKind.LOGNORMAL, 0.0, seed)
    strikes = (0.002, 0.008, 0.016)
    smile = SmileQuote(EXPIRY, strikes, (0.3, 0.25, 0.22), _forward(model))
    out = calibrate_sabr_smile(SabrCalibrationSpec(model, smile, 0.5))
    assert isinstance(out, CalibrationFailure)
    assert "Lognormal" in out.reason
