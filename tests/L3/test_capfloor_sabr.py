"""L3 oracle — SABR calibration to a cap/floor surface (T1 slice 23, STEP B).

End-to-end KNOWN-ANSWER round trip, through every stage the slice built:

    seed SabrParams per expiry
      → SABR caplet vols per (expiry, strike)        [the slice-20 expansion]
      → cap FLAT vols per (maturity, strike)         [inverted here, in the test, independently]
      → stripped caplet vols                         [the #10-fixed ladder strip]
      → a SmileQuote per expiry
      → fitted SabrParams                            [the slice-21 bounded fit + 1bp gate]
      → the seed back

Nothing in that chain is the identity: the test inverts the cap quote itself with its own inline
Black and Brent, so the flat vols handed to the calibration are produced by a code path the
calibration does not share. The quote grid is deliberately set EQUAL to the caplet grid (one new
caplet per quote), which is what makes the strip's marginal exactly the seed's caplet vol and the
recovery exact rather than approximate.
"""

import math
from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, SolveConfig
from pricebook.calibration.sabr_calibrate import (
    CapSabrCalibrationSpec,
    calibrate_capfloor_sabr,
)
from pricebook.engine import price
from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    PricingResult,
    RollRule,
    ScheduleTerms,
    StubType,
    Tenor,
    TenorUnit,
    TimeMeasure,
    brent,
    build_schedule,
    get_rate_index,
)
from pricebook.market.building_blocks import forward
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.quotes import CapQuote
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import SabrParams, SabrSurface, Surface, SurfaceKey
from pricebook.models.black_model import BlackModel
from pricebook.models.sabr import sabr_vol
from pricebook.models.sabr_model import SABRModel
from pricebook.products.option import CapFloor, OptionType, cap_ladder

VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
TM = TimeMeasure(VAL, DayCountConvention.ACT_365_FIXED)
M, Y = TenorUnit.MONTH, TenorUnit.YEAR
HORIZON = VAL + Tenor(3, Y)
BETA = 0.5
SEED = SabrParams(alpha=0.20, beta=BETA, rho=-0.30, nu=0.40)
TERMS = ScheduleTerms(Frequency(INDEX.id.tenor), RollRule(calendar=None), StubType.SHORT_BACK)
# quote grid == caplet grid: each successive maturity adds EXACTLY one caplet
MATURITIES = tuple(VAL + Tenor(m, M) for m in (6, 9, 12, 15))
STRIKES = (0.025, 0.030, 0.035, 0.040, 0.045)


def _curves() -> CurveSet:
    return CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.030, until=HORIZON),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, 0.035, until=HORIZON),
        }
    )


def _model() -> BlackModel:
    # a lognormal model carrying the curves: the strip reads them, the smile fit reads its law
    return BlackModel(MarketSnapshot(VAL, _curves()))


def _cap(maturity: date, strike: float) -> CapFloor:
    return CapFloor(INDEX, build_schedule(VAL, maturity, TERMS), strike, 1.0, OptionType.CALL)


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _ref_caplet_pv(caplet, vol: float) -> float:
    """An INDEPENDENT undiscounted-Black caplet PV (inline erf), df·τ·Black — the code path the
    calibration does not share, used to invert the cap quote."""
    curves = _curves()
    accrual = caplet.accrual
    f = forward(curves.projection(INDEX), accrual)
    df = curves.discount(CCY).df(accrual.end)
    tau = accrual.year_fraction()
    t = TM.year_fraction(accrual.start)
    if vol <= 0.0 or t <= 0.0:
        return df * tau * max(f - caplet.strike, 0.0)
    s = vol * math.sqrt(t)
    d1 = (math.log(f / caplet.strike) + 0.5 * s * s) / s
    return df * tau * (f * _phi(d1) - caplet.strike * _phi(d1 - s))


def _seed_vol(caplet) -> float:
    """The seed SABR caplet vol at this caplet's own forward (the generating model)."""
    curves = _curves()
    f = forward(curves.projection(INDEX), caplet.accrual)
    return sabr_vol(f, caplet.strike, TM.year_fraction(caplet.accrual.start), SEED)


def _cap_flat_quote(maturity: date, strike: float) -> CapQuote:
    """Invert the cap: the ONE flat vol whose cap PV equals the cap priced caplet-by-caplet at the
    seed SABR vols. This is how a market quotes a cap, and it is solved here with the test's own
    Black + Brent — so the flat vols the calibration consumes are not its own output."""
    ladder = cap_ladder(_cap(maturity, strike))
    target = sum(_ref_caplet_pv(c, _seed_vol(c)) for c in ladder)
    flat = brent(lambda v: sum(_ref_caplet_pv(c, v) for c in ladder) - target, 1e-6, 3.0)
    return CapQuote(maturity, strike, flat)


def _quotes() -> tuple[CapQuote, ...]:
    return tuple(_cap_flat_quote(m, k) for m in MATURITIES for k in STRIKES)


def _spec(quotes=None) -> CapSabrCalibrationSpec:
    return CapSabrCalibrationSpec(
        _model(), INDEX, quotes if quotes is not None else _quotes(), BETA, SolveConfig()
    )


# ── the round trip ─────────────────────────────────────────────────────────────────────────
def test_cap_surface_round_trip_recovers_the_seed_per_expiry() -> None:
    out = calibrate_capfloor_sabr(_spec())
    assert not isinstance(out, CalibrationFailure), out
    surface, result = out
    assert isinstance(surface, SabrSurface)
    assert result.converged
    expected_expiries = tuple(c.accrual.start for c in cap_ladder(_cap(MATURITIES[-1], STRIKES[0])))
    assert tuple(sorted(surface.params)) == expected_expiries  # one fit per LADDER expiry
    for expiry, params in surface.params.items():
        assert abs(params.alpha - SEED.alpha) < 1e-6, expiry
        assert abs(params.rho - SEED.rho) < 1e-6, expiry
        assert abs(params.nu - SEED.nu) < 1e-6, expiry
        assert params.beta == BETA  # β is fixed, never fitted


def test_the_calibrated_surface_reprices_the_caps() -> None:
    # the loop closes: the fitted SabrSurface, read back by SABRModel through the L4 engine,
    # reprices each quoted cap to the PV its own flat vol implies
    out = calibrate_capfloor_sabr(_spec())
    assert not isinstance(out, CalibrationFailure), out
    surface, _ = out
    curves = _curves()
    sabr_snap = MarketSnapshot(VAL, curves, surfaces={SurfaceKey(INDEX): surface})
    model = SABRModel.for_index(sabr_snap, INDEX)
    for q in _quotes():
        cap = _cap(q.maturity, q.strike)
        on_sabr = price(cap, model)
        flat_snap = MarketSnapshot(
            VAL, curves, surfaces={SurfaceKey(INDEX): Surface.flat(q.flat_vol)}
        )
        at_quote = price(cap, BlackModel(flat_snap))
        assert isinstance(on_sabr, PricingResult) and isinstance(at_quote, PricingResult)
        assert abs(on_sabr.pv.amount - at_quote.pv.amount) < 1e-6 * max(at_quote.pv.amount, 1e-9)


def test_one_cap_ladder_across_every_stage() -> None:
    # §3d: the ladder the strip builds, the ladder the pricer composes and the ladder the cap-SABR
    # calibration fits expiries on are ONE atom — so the fitted surface's expiries are exactly the
    # expiries price_capfloor will ask it for, with nothing to interpolate or miss
    out = calibrate_capfloor_sabr(_spec())
    assert not isinstance(out, CalibrationFailure), out
    surface, _ = out
    for m in MATURITIES:
        for caplet in cap_ladder(_cap(m, STRIKES[0])):
            assert caplet.accrual.start in surface.params


# ── failure as a value ─────────────────────────────────────────────────────────────────────
def test_a_contradictory_cap_smile_is_a_calibration_failure() -> None:
    # alternating flat vols across strikes strip to a sawtooth smile no SABR fits; the slice-21
    # 1bp acceptance gate (ruling 1) rejects it rather than returning a converged-but-wrong fit
    quotes = tuple(
        CapQuote(m, k, v)
        for m in MATURITIES
        for k, v in zip(STRIKES, (0.20, 0.60, 0.21, 0.62, 0.22))
    )
    out = calibrate_capfloor_sabr(_spec(quotes))
    assert isinstance(out, CalibrationFailure)


def test_a_strike_with_too_few_points_is_a_calibration_failure() -> None:
    # a 3-parameter fit needs ≥3 strikes per expiry — refuse, never fit a 2-point smile
    quotes = tuple(_cap_flat_quote(m, k) for m in MATURITIES for k in STRIKES[:2])
    out = calibrate_capfloor_sabr(_spec(quotes))
    assert isinstance(out, CalibrationFailure)


def test_ragged_strike_maturity_grid_is_a_calibration_failure() -> None:
    # every strike must be quoted on the SAME maturity set, or the per-strike strips produce
    # different expiry grids and a "smile at an expiry" is not well defined
    quotes = list(_quotes())
    quotes = [q for q in quotes if not (q.maturity == MATURITIES[-1] and q.strike == STRIKES[0])]
    out = calibrate_capfloor_sabr(_spec(tuple(quotes)))
    assert isinstance(out, CalibrationFailure)
    assert "maturit" in out.reason
