"""Slice B oracles — the swaption vol-cube calibration (`spec_slice_B_swaption_cube.md`).

Five oracles, in the spec's order:

1. STRUCTURAL — node count / no silent drop (ruling B1). The cube's content IS a grid, so §6's
   first clause makes the oracle a COUNT and its second clause makes it a floor on survivors.
   The quarry's `except Exception: pass` dropped a failed node silently; a reprice-the-ATM-backbone
   test is blind to that, a count is not.
2. S-identity per node on a **NON-CANONICAL** underlying (ruling B4 + the vacuity close). Each
   node is fit at the forward the ENGINE marks (`S = float_leg_pv/rpv01`), not at the index's
   canonical single-period forward. On a canonical underlying the two coincide and the oracle
   passes with every node mis-fit — so the grid here is semi-annual, where they differ.
3. Round-trip per node — recover synthetic SABR params within the 1bp gate.
4. Inverter parity — a node quoted in PRICES inverts (slice 24) to the same params as the same
   node quoted in vols. Slice B is the inverter's first ng consumer.
5. β explicit (audit F8) — no hidden 0.5.
"""

from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, CalibrationResult, SolveConfig
from pricebook.calibration.swaption_cube import (
    SwaptionCubeCalibrationSpec,
    build_swaption_vol_cube,
    swaption_cube,
)
from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    get_rate_index,
)
from pricebook.market.building_blocks import float_leg_pv, rpv01
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.quotes import SmileQuote
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import SabrParams, SabrSurface, SwaptionSurfaceKey, VolLawKind
from pricebook.models.sabr import sabr_vol
from pricebook.models.sabr_model import SABRModel
from pricebook.models.vol_law import vol_law_for

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(30, Y)
NOTIONAL = 1.0
BETA = 0.5
SEED = SabrParams(alpha=0.20, beta=BETA, rho=-0.30, nu=0.40)
EXPIRIES = (VAL + Tenor(1, Y), VAL + Tenor(2, Y))
TENORS = (Tenor(5, Y), Tenor(10, Y))
STRIKE_OFFSETS = (-0.015, -0.007, 0.0, 0.007, 0.015, 0.025)


def _curves() -> CurveSet:
    return CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.030, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, 0.035, until=FAR),
        }
    )


def _swap(expiry: date, tenor: Tenor, freq: Frequency, strike: float):
    from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap

    sched = build_schedule(expiry, expiry + tenor, ScheduleTerms(frequency=freq, roll=RollRule(calendar=None)))
    return VanillaSwap(NOTIONAL, CCY, FixedLeg(sched, DC365, strike), FloatLeg(sched, DC365, INDEX))


def _marked_s(expiry: date, tenor: Tenor, curves: CurveSet, freq: Frequency) -> float:
    """The engine's own S, through the SAME shared atoms `price_swaption` composes (§3d)."""
    swap = _swap(expiry, tenor, freq, 0.0)
    disc, proj = curves.discount(CCY), curves.projection(INDEX)
    annuity = rpv01(swap.fixed_leg.schedule, swap.fixed_leg.day_count, disc)
    return float_leg_pv(swap.float_leg.schedule, swap.float_leg.day_count, disc, proj) / annuity


def _model(curves: CurveSet) -> SABRModel:
    return SABRModel(MarketSnapshot(VAL, curves), vol_law_for(VolLawKind.LOGNORMAL, 0.0))


def _node_quote(expiry: date, tenor: Tenor, curves: CurveSet, freq: Frequency, seed: SabrParams = SEED):
    """A quoted smile at the node, generated FROM the engine's marked S (so oracle 2 can bite)."""
    s = _marked_s(expiry, tenor, curves, freq)
    t = TM.year_fraction(expiry)
    strikes = tuple(s + d for d in STRIKE_OFFSETS)
    vols = tuple(sabr_vol(s, k, t, seed) for k in strikes)
    return SwaptionSurfaceKey(INDEX, tenor), SmileQuote(expiry, strikes, vols, s)


def _grid(curves: CurveSet, freq: Frequency = Frequency.SEMI_ANNUAL):
    """The full 2x2 NON-CANONICAL grid: two expiries x two swap tenors, semi-annual underlying."""
    return tuple(_node_quote(e, tn, curves, freq) for tn in TENORS for e in EXPIRIES)


def _spec(curves: CurveSet, quotes=None, beta: float = BETA) -> SwaptionCubeCalibrationSpec:
    return SwaptionCubeCalibrationSpec(
        _model(curves), quotes if quotes is not None else _grid(curves), beta, SolveConfig(tolerance=1e-12)
    )


# ── ORACLE 1 — STRUCTURAL: the node count, and no silent drop ───────────────────────────────
def test_every_quoted_node_appears_in_the_outcome_map() -> None:
    """§6 first clause: the content is a GRID, so the oracle is a count — 4 quoted, 4 calibrated."""
    curves = _curves()
    quotes = _grid(curves)
    outcomes = build_swaption_vol_cube(_spec(curves, quotes))

    assert len(outcomes) == len(quotes) == 4  # the FLOOR: no node may vanish
    for key, smile in quotes:
        assert (key, smile.expiry) in outcomes  # keyed by the quoted node itself
    assert all(not isinstance(v, CalibrationFailure) for v in outcomes.values())


def test_an_unfittable_node_is_a_COUNTED_FAILURE_not_a_vanished_node() -> None:
    """The quarry wrapped each fit in `except Exception: pass`. A poisoned node must SURFACE."""
    curves = _curves()
    good = _grid(curves)
    key, smile = good[0]
    # alternating vols: scipy converges, but no SABR smile goes through it (the 1bp gate rejects)
    poisoned = (key, SmileQuote(smile.expiry, smile.strikes, (0.20, 0.60, 0.21, 0.62, 0.22, 0.61), smile.forward))
    quotes = (poisoned,) + good[1:]

    outcomes = build_swaption_vol_cube(_spec(curves, quotes))

    assert len(outcomes) == len(quotes) == 4  # still 4 — the failure did not vanish
    failed = outcomes[(key, smile.expiry)]
    assert isinstance(failed, CalibrationFailure), failed
    assert failed.residuals  # it reports HOW far off, in vol units
    # derived, never stored: a stored count can drift from the collection it summarises
    calibrated = sum(1 for v in outcomes.values() if not isinstance(v, CalibrationFailure))
    assert calibrated == 3
    assert len(outcomes) - calibrated == 1
    # and the cube excludes it without hiding it
    cube = swaption_cube(outcomes)
    assert smile.expiry not in cube[key].params


def test_an_empty_quote_grid_is_a_failure_not_an_empty_cube() -> None:
    """Floor-on-population: a build that examined nothing must not report success (§6)."""
    out = build_swaption_vol_cube(_spec(_curves(), ()))
    assert isinstance(out, CalibrationFailure), out


# ── ORACLE 2 — the S-identity per node, on a NON-CANONICAL underlying ──────────────────────
def test_each_node_is_fit_at_the_ENGINE_marked_S_not_the_canonical_forward() -> None:
    """B4's proof, per node. On a SEMI-ANNUAL underlying the engine's S differs from the index's
    canonical single-period forward, so a fit that reconstructed the latter lands its smile
    minimum in the wrong place. The ATM vol read back at S must equal the quoted ATM vol."""
    curves = _curves()
    quotes = _grid(curves, Frequency.SEMI_ANNUAL)
    cube = swaption_cube(build_swaption_vol_cube(_spec(curves, quotes)))

    from pricebook.market.building_blocks import forward as fwd_atom

    for key, smile in quotes:
        s = smile.forward
        canonical = fwd_atom(curves.projection(INDEX), INDEX.canonical_accrual(smile.expiry))
        assert abs(s - canonical) > 1e-4, "the grid must be NON-canonical or this oracle is vacuous"

        params = cube[key].at_expiry(smile.expiry)
        t = TM.year_fraction(smile.expiry)
        atm_i = min(range(len(smile.strikes)), key=lambda i: abs(smile.strikes[i] - s))
        assert abs(sabr_vol(s, smile.strikes[atm_i], t, params) - smile.vols[atm_i]) < 1e-6


# ── ORACLE 3 — round-trip per node ─────────────────────────────────────────────────────────
def test_each_node_round_trips_its_seed_params() -> None:
    curves = _curves()
    quotes = _grid(curves)
    outcomes = build_swaption_vol_cube(_spec(curves, quotes))
    for key, smile in quotes:
        fitted, result = outcomes[(key, smile.expiry)]
        assert isinstance(result, CalibrationResult) and result.converged
        assert abs(fitted.alpha - SEED.alpha) < 1e-6
        assert abs(fitted.rho - SEED.rho) < 1e-5
        assert abs(fitted.nu - SEED.nu) < 1e-5


# ── ORACLE 4 — inverter parity (slice 24's first ng consumer) ──────────────────────────────
def test_a_node_quoted_in_prices_fits_the_same_params_as_one_quoted_in_vols() -> None:
    """Price-quoted nodes invert through slice 24's law-generic `implied_vol` BEFORE the fit."""
    from pricebook.models.implied_vol import implied_vol
    from pricebook.models.vol_law import Lognormal

    curves = _curves()
    key, smile = _node_quote(EXPIRIES[0], TENORS[0], curves, Frequency.SEMI_ANNUAL)
    law, t, s = Lognormal(), TM.year_fraction(smile.expiry), smile.forward
    prices = tuple(law.price(s, k, t, v) for k, v in zip(smile.strikes, smile.vols))
    back = tuple(implied_vol(law, p, s, k, t) for p, k in zip(prices, smile.strikes))

    from_vols = build_swaption_vol_cube(_spec(curves, ((key, smile),)))
    from_prices = build_swaption_vol_cube(
        _spec(curves, ((key, SmileQuote(smile.expiry, smile.strikes, back, s)),))
    )
    a, _ = from_vols[(key, smile.expiry)]
    b, _ = from_prices[(key, smile.expiry)]
    assert abs(a.alpha - b.alpha) < 1e-8
    assert abs(a.rho - b.rho) < 1e-8
    assert abs(a.nu - b.nu) < 1e-8


# ── ORACLE 5 — β is explicit ───────────────────────────────────────────────────────────────
def test_beta_is_an_explicit_input_and_is_the_beta_fitted() -> None:
    curves = _curves()
    for beta in (0.0, 0.5, 1.0):
        quotes = (_node_quote(EXPIRIES[0], TENORS[0], curves, Frequency.SEMI_ANNUAL,
                              SabrParams(0.20, beta, -0.30, 0.40)),)
        outcomes = build_swaption_vol_cube(_spec(curves, quotes, beta))
        fitted, _ = outcomes[(quotes[0][0], quotes[0][1].expiry)]
        assert fitted.beta == beta  # the fixed input, carried through untouched


def test_the_spec_requires_beta_with_no_hidden_default() -> None:
    import inspect

    sig = inspect.signature(SwaptionCubeCalibrationSpec.__init__)
    assert sig.parameters["beta"].default is inspect.Parameter.empty
