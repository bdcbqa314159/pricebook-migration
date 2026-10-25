"""L3 oracle — caplet-vol stripping (C2 slice 3), the first solved surface.

Sequential 1-D Brent strip: given ascending flat cap vols, strip each maturity's marginal caplet
vol so the caps reprice. Oracles: flat round-trip (closed-form anchor), reprice-to-quote,
reprice-through-the-L4-engine backstop (§3d shared atoms), and invariant-4 on an infeasible input.

Slice 23 discharges **audit #10**: the strip now builds each quote's full caplet LADDER from the
cap's own schedule (`cap_ladder`, the one atom the pricer composes) and solves ONE marginal vol per
quote interval, shared by every new caplet in it. The count oracle below is what the old
flat-round-trip could not see — a flat vol in gives a flat vol out whatever the ladder's shape.
"""

import math
from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure
from pricebook.calibration.vol_strip import VolCalibrationSpec, strip_caplet_vols
from pricebook.engine import price
from pricebook.foundation import (
    Accrual,
    DayCountConvention,
    Frequency,
    PricingResult,
    RollRule,
    ScheduleTerms,
    StubType,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    get_rate_index,
)
from pricebook.market.building_blocks import forward
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.quotes import CapQuote
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import Surface, SurfaceKey
from pricebook.models.black_model import BlackModel
from pricebook.models.discounting_model import DiscountingModel
from pricebook.products.option import CapFloor, Caplet, cap_ladder

VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
DC = INDEX.accrual.day_count  # ACT/360 — the caplet accrual convention
Y = TenorUnit.YEAR
TM365 = TimeMeasure(VAL, DayCountConvention.ACT_365_FIXED)
STRIKE = 0.035
MATS = tuple(VAL + Tenor(y, Y) for y in (1, 2, 3, 5))
_END = VAL + Tenor(6, Y)
# the cap schedule the strip builds per quote: the index tenor, anchored FORWARD on the valuation
# date, so each maturity's ladder extends the previous one's (what the sequential strip needs)
CAP_TERMS = ScheduleTerms(Frequency(INDEX.id.tenor), RollRule(calendar=None), StubType.SHORT_BACK)


def _curves() -> CurveSet:
    disc = DiscountCurve.flat(TimeMeasure(VAL, DC), 0.030, until=_END)
    proj = DiscountCurve.flat(TimeMeasure(VAL, DC), 0.035, until=_END)
    return CurveSet({CurveKey(CurveRole.DISCOUNT, CCY): disc, CurveKey(CurveRole.PROJECTION, INDEX): proj})


def _spec(vols) -> VolCalibrationSpec:
    curves = _curves()
    model = DiscountingModel(MarketSnapshot(VAL, curves))
    quotes = tuple(CapQuote(m, STRIKE, v) for m, v in zip(MATS, vols))
    return VolCalibrationSpec(model, INDEX, quotes)


def test_flat_roundtrip_is_exact() -> None:
    # closed-form anchor: strip a flat cap → every stripped caplet vol == the flat vol
    flat = 0.22
    out = strip_caplet_vols(_spec((flat,) * len(MATS)))
    assert not isinstance(out, CalibrationFailure), out
    surface, result = out
    assert result.converged
    for v in surface.vols:
        assert abs(v - flat) < 1e-12


def test_backstop_caplet_reprices_through_engine() -> None:
    # §3d: a caplet priced through the L4 engine off the stripped surface matches an independent
    # Black on the same forward/df — proves the strip and engine share the law/forward/df.
    # Evaluated at every LADDER expiry (19 of them), which is where the fixed strip has pillars:
    # a quote's `maturity` is the cap's END date, so the last caplet of a 5Y cap fixes at 4Y9M —
    # reading a vol AT 5Y is the #10 confusion (maturity-as-fixing) the old grid encoded.
    out = strip_caplet_vols(_spec((0.24, 0.22, 0.20, 0.19)))
    assert not isinstance(out, CalibrationFailure), out
    surface, _ = out
    curves = _curves()
    snap = MarketSnapshot(VAL, curves, surfaces={SurfaceKey(INDEX): surface})
    for caplet in cap_ladder(_cap_for(MATS[-1])):
        mat = caplet.accrual.start
        vol = surface.at(mat, STRIKE, TM365)
        accrual = caplet.accrual
        result = price(Caplet(INDEX, accrual, STRIKE, 1.0), BlackModel(snap))
        assert isinstance(result, PricingResult)
        fwd = forward(curves.projection(INDEX), accrual)
        pay_df = curves.discount(CCY).df(accrual.end)
        t = TM365.year_fraction(mat)
        s = vol * math.sqrt(t)
        d1 = (math.log(fwd / STRIKE) + 0.5 * s * s) / s
        d2 = d1 - s
        phi = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
        expected = pay_df * accrual.year_fraction() * (fwd * phi(d1) - STRIKE * phi(d2))
        assert abs(result.pv.amount - expected) < 1e-12


def test_stripped_surface_reprices_quotes() -> None:
    out = strip_caplet_vols(_spec((0.24, 0.22, 0.20, 0.19)))
    assert not isinstance(out, CalibrationFailure), out
    _, result = out
    assert result.converged
    assert max(abs(r) for r in result.residuals) < 1e-9


def test_infeasible_input_returns_failure() -> None:
    # a later cap quoted far BELOW the earlier ones → the marginal caplet PV is negative, no
    # positive vol reproduces it → CalibrationFailure (invariant 4), not a garbage vol.
    out = strip_caplet_vols(_spec((0.60, 0.01, 0.01, 0.01)))
    assert isinstance(out, CalibrationFailure)


# ── slice 23: audit #10 — the ladder, not the quote grid ───────────────────────────────────
def _cap_for(maturity: date, strike: float = STRIKE) -> CapFloor:
    return CapFloor(INDEX, build_schedule(VAL, maturity, CAP_TERMS), strike, 1.0)


def test_strip_builds_the_cap_ladder_not_one_caplet_per_quote() -> None:
    # audit #10: the surface must carry a pillar per CAPLET (20 for quotes out to 5Y on a 3M
    # index), not one per QUOTE (4). The old strip returned 4 — and its flat round-trip passed
    # anyway, which is why the fix needs a count oracle.
    out = strip_caplet_vols(_spec((0.24, 0.22, 0.20, 0.19)))
    assert not isinstance(out, CalibrationFailure), out
    surface, _ = out
    expected = len(cap_ladder(_cap_for(MATS[-1])))
    assert expected == 19  # 5Y quarterly = 20 periods, first excluded
    assert len(surface.vols) == expected
    assert len(surface.expiries) == expected
    assert surface.expiries == tuple(c.accrual.start for c in cap_ladder(_cap_for(MATS[-1])))


def test_strip_uses_the_same_ladder_the_pricer_uses() -> None:
    # §3d: ONE cap_ladder. The strip's pillars ARE the caplet expiries the L4 pricer composes,
    # so a stripped surface cannot be indexed on a grid the pricer does not ask for.
    out = strip_caplet_vols(_spec((0.24, 0.22, 0.20, 0.19)))
    assert not isinstance(out, CalibrationFailure), out
    surface, _ = out
    for mat in MATS:
        for caplet in cap_ladder(_cap_for(mat)):
            assert caplet.accrual.start in surface.expiries


def test_each_cap_reprices_to_its_flat_quote_on_a_finer_caplet_grid() -> None:
    # the #10 case the old strip could not express: 4 quotes, 19 caplets. Each cap priced off the
    # STRIPPED surface must match the same cap priced at its own flat quote — through the L4 engine
    # on both sides, so the identity is end-to-end and not internal to the calibrator.
    quote_vols = (0.24, 0.22, 0.20, 0.19)
    out = strip_caplet_vols(_spec(quote_vols))
    assert not isinstance(out, CalibrationFailure), out
    surface, result = out
    assert result.converged
    curves = _curves()
    stripped_snap = MarketSnapshot(VAL, curves, surfaces={SurfaceKey(INDEX): surface})
    for mat, flat in zip(MATS, quote_vols):
        cap = _cap_for(mat)
        on_surface = price(cap, BlackModel(stripped_snap))
        flat_snap = MarketSnapshot(VAL, curves, surfaces={SurfaceKey(INDEX): Surface.flat(flat)})
        at_quote = price(cap, BlackModel(flat_snap))
        assert isinstance(on_surface, PricingResult) and isinstance(at_quote, PricingResult)
        assert abs(on_surface.pv.amount - at_quote.pv.amount) < 1e-10


def test_flat_cap_vols_still_strip_to_a_flat_caplet_curve() -> None:
    # the C2 anchor, preserved: a flat quote curve strips flat — now across the FULL ladder
    flat = 0.22
    out = strip_caplet_vols(_spec((flat,) * len(MATS)))
    assert not isinstance(out, CalibrationFailure), out
    surface, _ = out
    assert len(surface.vols) == 19
    for v in surface.vols:
        assert abs(v - flat) < 1e-10


def test_mixed_strike_quotes_are_a_calibration_failure() -> None:
    # a Surface has no strike axis, so stripping quotes at DIFFERENT strikes into one surface is
    # the same class of silent error as #10 — refuse it as a value
    curves = _curves()
    model = DiscountingModel(MarketSnapshot(VAL, curves))
    quotes = (CapQuote(MATS[0], 0.030, 0.24), CapQuote(MATS[1], 0.035, 0.22))
    out = strip_caplet_vols(VolCalibrationSpec(model, INDEX, quotes))
    assert isinstance(out, CalibrationFailure)
    assert "strike" in out.reason


def test_duplicate_maturity_quotes_are_a_calibration_failure() -> None:
    # two quotes on the SAME maturity add no new caplet between them, so both claim the same
    # marginal vol — over-determined. The quarry silently skipped the second; we refuse (invariant 4)
    curves = _curves()
    model = DiscountingModel(MarketSnapshot(VAL, curves))
    m = VAL + Tenor(1, Y)
    quotes = (CapQuote(m, STRIKE, 0.24), CapQuote(m, STRIKE, 0.22))
    out = strip_caplet_vols(VolCalibrationSpec(model, INDEX, quotes))
    assert isinstance(out, CalibrationFailure)
    assert "no new caplet" in out.reason


def test_off_grid_maturity_is_a_calibration_failure() -> None:
    # a 13M cap on a 3M index ends with a 1-MONTH stub period, whose accrual is not the index's
    # canonical one — the L4 pricer would refuse that caplet (ruling 2), so stripping a surface for
    # it would produce vols nothing can price. Refuse at the strip, where the grid is chosen.
    curves = _curves()
    model = DiscountingModel(MarketSnapshot(VAL, curves))
    quotes = (CapQuote(VAL + Tenor(13, TenorUnit.MONTH), STRIKE, 0.22),)
    out = strip_caplet_vols(VolCalibrationSpec(model, INDEX, quotes))
    assert isinstance(out, CalibrationFailure)
    assert "canonical" in out.reason
