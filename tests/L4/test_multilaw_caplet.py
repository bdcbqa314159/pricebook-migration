"""L4 oracles — a caplet under EVERY vol law, through the unchanged engine (T1 slice 22).

What these prove:
1. **Audit #15 discharged** — a NEGATIVE forward, which the lognormal-only engine could only refuse,
   now prices under the shifted and normal laws, and *still* fails under the lognormal one. The
   engine does not know which: `vol_law.defined` is the law's own domain (no law switch).
2. **ML-D1 closed (slice 25)** — a non-canonical (stub / odd-day-count) optionlet now PRICES, at its
   own forward. The slice-23 guard that refused it existed only because the vol capability
   reconstructed F; the engine now passes the F it marked, so the identity is structural and the
   whole refused class is delivered instead.
3. **Structural** — no `isinstance`/law branch in the pricer module; the only tag→law dispatch is
   the construction-time factory.
"""

import ast
from datetime import date
from pathlib import Path

from pricebook.engine import price
from pricebook.foundation import (
    Accrual,
    DayCountConvention,
    PricingFailure,
    PricingResult,
    Tenor,
    TenorUnit,
    TimeMeasure,
    get_rate_index,
)
from pricebook.market.building_blocks import forward
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import SabrParams, SabrSurface, SurfaceKey, VolLawKind
from pricebook.models.bachelier import bachelier
from pricebook.models.black import black
from pricebook.models.sabr import sabr_normal_vol, sabr_vol
from pricebook.models.sabr_model import SABRModel
from pricebook.products.option import Caplet, OptionType

VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
DC365, DC360 = DayCountConvention.ACT_365_FIXED, DayCountConvention.ACT_360
TM = TimeMeasure(VAL, DC365)
EXPIRY = VAL + Tenor(1, TenorUnit.YEAR)
ACCRUAL = INDEX.canonical_accrual(EXPIRY)
NOTIONAL = 1_000_000.0
SHIFT = 0.030
NEG_RATE = -0.005  # a flat NEGATIVE projection curve ⇒ a negative forward


def _curves(proj_rate: float) -> CurveSet:
    return CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.010, until=ACCRUAL.end),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, proj_rate, until=ACCRUAL.end),
        }
    )


def _model(proj_rate: float, params: SabrParams, kind: VolLawKind, shift: float = 0.0) -> SABRModel:
    curves = _curves(proj_rate)
    snap = MarketSnapshot(
        VAL, curves, surfaces={SurfaceKey(INDEX): SabrSurface({EXPIRY: params}, kind, shift)}
    )
    return SABRModel.for_index(snap, INDEX)  # the ONE tag→law mapping


def _engine_inputs(model: SABRModel) -> tuple[float, float, float, float]:
    curves = model.market.curves
    fwd = forward(curves.projection(INDEX), ACCRUAL)
    return fwd, curves.discount(CCY).df(ACCRUAL.end), ACCRUAL.year_fraction(), TM.year_fraction(EXPIRY)


# ── audit #15: a negative forward prices under the shifted and normal laws ─────────────────
def test_negative_forward_caplet_prices_under_the_shifted_law() -> None:
    params = SabrParams(alpha=0.20, beta=0.5, rho=-0.3, nu=0.4)
    model = _model(NEG_RATE, params, VolLawKind.SHIFTED_LOGNORMAL, SHIFT)
    fwd, df, tau, t = _engine_inputs(model)
    assert fwd < 0.0  # the premise
    strike = 0.002
    result = price(Caplet(INDEX, ACCRUAL, strike, NOTIONAL), model)
    assert isinstance(result, PricingResult), result
    vol = sabr_vol(fwd + SHIFT, strike + SHIFT, t, params)  # the expansion on the SHIFTED pair
    expected = df * NOTIONAL * tau * black(fwd + SHIFT, strike + SHIFT, vol, t, OptionType.CALL)
    assert abs(result.pv.amount - expected) < 1e-10


def test_negative_forward_caplet_prices_under_the_normal_law() -> None:
    params = SabrParams(alpha=0.0060, beta=0.0, rho=-0.3, nu=0.4)  # β=0, α in absolute rate units
    model = _model(NEG_RATE, params, VolLawKind.NORMAL)
    fwd, df, tau, t = _engine_inputs(model)
    assert fwd < 0.0
    for strike in (-0.010, 0.0, 0.002, 0.015):
        result = price(Caplet(INDEX, ACCRUAL, strike, NOTIONAL), model)
        assert isinstance(result, PricingResult), result
        vol = sabr_normal_vol(fwd, strike, t, params)
        expected = df * NOTIONAL * tau * bachelier(fwd, strike, vol, t, OptionType.CALL)
        assert abs(result.pv.amount - expected) < 1e-10


def test_negative_forward_caplet_still_fails_under_the_lognormal_law() -> None:
    # the law's DOMAIN, not a hard-coded engine guard: same product, same curves, different law
    model = _model(NEG_RATE, SabrParams(0.20, 0.5, -0.3, 0.4), VolLawKind.LOGNORMAL)
    result = price(Caplet(INDEX, ACCRUAL, 0.002, NOTIONAL), model)
    assert isinstance(result, PricingFailure)
    assert "Lognormal" in result.reason


def test_normal_law_caplet_has_positive_time_value_at_a_deep_otm_strike() -> None:
    # a negative-rate sanity check the lognormal law cannot express: a strike ABOVE the forward
    # still has value under the normal law (the forward can diffuse up through zero)
    model = _model(NEG_RATE, SabrParams(0.0060, 0.0, -0.3, 0.4), VolLawKind.NORMAL)
    result = price(Caplet(INDEX, ACCRUAL, 0.010, NOTIONAL), model)
    assert isinstance(result, PricingResult)
    assert result.pv.amount > 0.0


# ── ruling 2: the F-identity guard ─────────────────────────────────────────────────────────
def test_canonical_accrual_caplet_prices_the_positive_control() -> None:
    model = _model(0.035, SabrParams(0.20, 0.5, -0.3, 0.4), VolLawKind.LOGNORMAL)
    assert isinstance(price(Caplet(INDEX, ACCRUAL, 0.035, NOTIONAL), model), PricingResult)


def test_stub_caplet_now_prices_at_its_OWN_forward() -> None:
    # ML-D1 CLOSED (slice 25, ruling A). A SHORT stub's accrual ends before expiry+tenor, so its
    # forward differs from the index's canonical one. Slice 23 had to REFUSE it, because the vol
    # capability reconstructed F from the canonical accrual and would have read the smile at the
    # wrong forward. The engine now PASSES the F it marked, so the stub prices — and prices at the
    # stub's own forward, which this asserts against an independent composition.
    params = SabrParams(0.20, 0.5, -0.3, 0.4)
    model = _model(0.035, params, VolLawKind.LOGNORMAL)
    stub = Accrual(EXPIRY, EXPIRY + Tenor(1, TenorUnit.MONTH), DC360)
    result = price(Caplet(INDEX, stub, 0.035, NOTIONAL), model)
    assert isinstance(result, PricingResult), result
    curves = _curves(0.035)
    stub_fwd = forward(curves.projection(INDEX), stub)
    canonical_fwd = forward(curves.projection(INDEX), INDEX.canonical_accrual(EXPIRY))
    assert abs(stub_fwd - canonical_fwd) > 1e-6  # the premise: the two forwards really differ
    t = TM.year_fraction(EXPIRY)
    vol = sabr_vol(stub_fwd, 0.035, t, params)  # the smile at the STUB's forward, not the index's
    expected = (
        curves.discount(CCY).df(stub.end)
        * NOTIONAL
        * stub.year_fraction()
        * black(stub_fwd, 0.035, vol, t, OptionType.CALL)
    )
    assert abs(result.pv.amount - expected) < 1e-10
    # and the old behaviour would have been wrong, not merely refused: pricing the stub with the
    # canonical forward's vol gives a materially different number
    wrong = (
        curves.discount(CCY).df(stub.end)
        * NOTIONAL
        * stub.year_fraction()
        * black(stub_fwd, 0.035, sabr_vol(canonical_fwd, 0.035, t, params), t, OptionType.CALL)
    )
    assert abs(wrong - expected) > 1e-10


def test_odd_day_count_caplet_now_prices_too() -> None:
    # same dates, a DIFFERENT day count — ACT/365F against the index's ACT/360, so τ and therefore F
    # genuinely differ (30/360 would NOT differ here: Jan-15 → Apr-15 is 90 days on both counts, a
    # coincidence worth not building a test on). Priced now, at its own forward: the whole class the
    # slice-23 guard refused is delivered rather than blocked.
    params = SabrParams(0.20, 0.5, -0.3, 0.4)
    model = _model(0.035, params, VolLawKind.LOGNORMAL)
    odd = Accrual(ACCRUAL.start, ACCRUAL.end, DC365)
    result = price(Caplet(INDEX, odd, 0.035, NOTIONAL), model)
    assert isinstance(result, PricingResult), result
    curves = _curves(0.035)
    odd_fwd = forward(curves.projection(INDEX), odd)
    assert abs(odd_fwd - forward(curves.projection(INDEX), ACCRUAL)) > 1e-6  # the premise
    t = TM.year_fraction(EXPIRY)
    expected = (
        curves.discount(CCY).df(odd.end)
        * NOTIONAL
        * odd.year_fraction()
        * black(odd_fwd, 0.035, sabr_vol(odd_fwd, 0.035, t, params), t, OptionType.CALL)
    )
    assert abs(result.pv.amount - expected) < 1e-10


# ── structural: the engine never branches on the law ───────────────────────────────────────
def test_pricer_has_no_law_switch() -> None:
    # the AST, not the prose: the pricer may DESCRIBE the laws in its docstring, but it must not
    # import one, name one, or branch on one. The only tag→law dispatch is `vol_law_for`, called at
    # model construction.
    src = (
        Path(__file__).resolve().parents[2]
        / "src" / "pricebook" / "engine" / "vanilla_option.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any("vol_law" in m for m in imports), "the pricer imports a law module"
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert names.isdisjoint({"Lognormal", "ShiftedLognormal", "Normal", "VolLawKind", "vol_law_for"})
    for line in src.splitlines():
        if "isinstance(" in line:  # the CALL, not the word in prose
            # capability protocols + invariant #4. `SwaptionPrice` joins as of the capability
            # slice: it IS a capability (a protocol on what the model can DO), so it belongs
            # here — the law this test guards is "no branching on a concrete model or a law",
            # not "no isinstance".
            allowed = ("ImpliedVol", "SwaptionVol", "SwaptionPrice", "PricingFailure")
            assert any(a in line for a in allowed), f"non-capability isinstance: {line.strip()}"
