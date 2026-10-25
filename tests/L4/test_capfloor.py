"""L4 oracles — the cap/floor ladder and its pricing (T1 slice 23).

The load-bearing one is the **ladder count** (audit #10): a 2Y cap on 3M EURIBOR is SEVEN caplets
(eight periods, the first excluded because its rate is already set) — not one. The old `vol_strip`
modelled a cap as a single caplet per quote, and neither its flat-round-trip nor its reprice oracle
could see that: a flat vol in gives a flat vol out whatever the ladder's shape. So the oracle here
is a COUNT and an independent-composition PARITY, not a tighter tolerance.

Parity is the strongest check available without a second implementation: `cap − floor` must equal
`Σ df·N·τ·(F − K)` over the ladder — a value composed from the `forward` and `df` atoms ALONE, with
no option formula anywhere near it, and it holds exactly because put-call parity holds in every law.
"""

from datetime import date

from pricebook.engine import price
from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    PricingFailure,
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
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import (
    SabrParams,
    SabrSurface,
    Surface,
    SurfaceKey,
    VolLawKind,
)
from pricebook.models.black_model import BlackModel
from pricebook.models.discounting_model import DiscountingModel
from pricebook.models.sabr_model import SABRModel
from pricebook.products.option import CapFloor, OptionType, cap_ladder

VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
DC365 = DayCountConvention.ACT_365_FIXED
TM = TimeMeasure(VAL, DC365)
Y, M = TenorUnit.YEAR, TenorUnit.MONTH
END = VAL + Tenor(2, Y)
HORIZON = VAL + Tenor(3, Y)
STRIKE = 0.035
NOTIONAL = 1_000_000.0
VOL = 0.22

# the cap's own schedule: quarterly (= the index tenor), anchored FORWARD on the start date, so the
# boundaries are start + n·3M and every shorter cap's ladder is a prefix of every longer one's
TERMS = ScheduleTerms(Frequency(INDEX.id.tenor), RollRule(calendar=None), StubType.SHORT_BACK)


def _curves(proj_rate: float = 0.035) -> CurveSet:
    return CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.030, until=HORIZON),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, proj_rate, until=HORIZON),
        }
    )


def _cap(option_type: OptionType = OptionType.CALL, end: date = END) -> CapFloor:
    return CapFloor(INDEX, build_schedule(VAL, end, TERMS), STRIKE, NOTIONAL, option_type)


def _black_model(proj_rate: float = 0.035, vol: float = VOL) -> BlackModel:
    snap = MarketSnapshot(VAL, _curves(proj_rate), surfaces={SurfaceKey(INDEX): Surface.flat(vol)})
    return BlackModel(snap)


# ── audit #10: the ladder is the cap's own schedule, not the quote grid ────────────────────
def test_two_year_cap_has_seven_caplets_first_excluded() -> None:
    cap = _cap()
    assert len(cap.schedule.periods) == 8  # 2Y quarterly
    ladder = cap_ladder(cap)
    assert len(ladder) == 7  # ← audit #10: SEVEN, not one-per-quote and not eight
    # the excluded one is the FIRST period (its rate is set at the cap's start)
    assert ladder[0].accrual.start == cap.schedule.periods[1].accrual_start
    assert ladder[-1].accrual.end == cap.schedule.periods[-1].accrual_end


def test_every_ladder_caplet_carries_the_canonical_accrual() -> None:
    # the ruling-2 F-identity, per caplet and BY CONSTRUCTION: each caplet's accrual is exactly the
    # index's own canonical accrual from its fixing date, so the engine's guard passes for all of them
    for caplet in cap_ladder(_cap()):
        assert caplet.accrual == INDEX.canonical_accrual(caplet.accrual.start)
        assert caplet.index == INDEX
        assert caplet.strike == STRIKE
        assert caplet.notional == NOTIONAL


def test_ladders_of_different_maturities_are_prefixes() -> None:
    # what the sequential strip depends on: a longer cap's ladder EXTENDS a shorter one's
    short = [c.accrual for c in cap_ladder(_cap(end=VAL + Tenor(1, Y)))]
    long = [c.accrual for c in cap_ladder(_cap(end=END))]
    assert long[: len(short)] == short


def test_floor_ladder_is_put_optionlets() -> None:
    assert all(c.option_type is OptionType.PUT for c in cap_ladder(_cap(OptionType.PUT)))
    assert all(c.option_type is OptionType.CALL for c in cap_ladder(_cap(OptionType.CALL)))


# ── pricing ────────────────────────────────────────────────────────────────────────────────
def test_cap_is_the_sum_of_its_caplets() -> None:
    model = _black_model()
    cap = _cap()
    whole = price(cap, model)
    assert isinstance(whole, PricingResult), whole
    parts = [price(c, model) for c in cap_ladder(cap)]
    assert all(isinstance(p, PricingResult) for p in parts)
    total = sum(p.pv.amount for p in parts if isinstance(p, PricingResult))
    assert abs(whole.pv.amount - total) < 1e-12
    assert whole.pv.currency == CCY


def test_cap_minus_floor_is_the_forward_start_swap() -> None:
    # put-call parity, composed from the `forward`/`df` atoms ONLY — no option formula in the
    # expected value, so this cannot agree with the pricer by sharing its code path
    model = _black_model()
    cap, floor = _cap(OptionType.CALL), _cap(OptionType.PUT)
    c, f = price(cap, model), price(floor, model)
    assert isinstance(c, PricingResult) and isinstance(f, PricingResult)
    curves = _curves()
    swap = 0.0
    for caplet in cap_ladder(cap):
        fwd = forward(curves.projection(INDEX), caplet.accrual)
        df = curves.discount(CCY).df(caplet.accrual.end)
        swap += df * NOTIONAL * caplet.accrual.year_fraction() * (fwd - STRIKE)
    assert abs((c.pv.amount - f.pv.amount) - swap) < 1e-9


def test_cap_needs_the_implied_vol_capability() -> None:
    out = price(_cap(), DiscountingModel(MarketSnapshot(VAL, _curves())))
    assert isinstance(out, PricingFailure)


def test_normal_law_cap_prices_at_a_negative_forward() -> None:
    # inherited from slice 22: the cap is law-polymorphic because it composes price_caplet, which
    # composes model.vol_law. A negative forward is ordinary under the normal law…
    params = SabrParams(alpha=0.0060, beta=0.0, rho=-0.3, nu=0.4)
    snap = MarketSnapshot(
        VAL,
        _curves(proj_rate=-0.005),
        surfaces={SurfaceKey(INDEX): SabrSurface(
            {c.accrual.start: params for c in cap_ladder(_cap())}, VolLawKind.NORMAL, 0.0
        )},
    )
    out = price(_cap(), SABRModel.for_index(snap, INDEX))
    assert isinstance(out, PricingResult), out
    assert out.pv.amount > 0.0


def test_lognormal_law_cap_refuses_a_negative_forward() -> None:
    # …and still a failure under the lognormal one, surfaced as a value through the whole ladder
    snap = MarketSnapshot(
        VAL, _curves(proj_rate=-0.005), surfaces={SurfaceKey(INDEX): Surface.flat(VOL)}
    )
    out = price(_cap(), BlackModel(snap))
    assert isinstance(out, PricingFailure)
    assert "Lognormal" in out.reason


def test_non_canonical_cap_schedule_now_prices_per_period() -> None:
    # ML-D1 CLOSED (slice 25): a SEMI-ANNUAL schedule on a 3M index has periods of twice the index
    # tenor, so no ladder caplet is the index's canonical accrual. Slice 23 refused it; the engine
    # now marks each caplet's F over its OWN accrual and passes it to the vol, so the cap prices —
    # and it is still exactly the sum of its own ladder, which is the property that matters.
    semi = build_schedule(VAL, END, ScheduleTerms(Frequency.SEMI_ANNUAL, RollRule(calendar=None)))
    cap = CapFloor(INDEX, semi, STRIKE, NOTIONAL)
    model = _black_model()
    out = price(cap, model)
    assert isinstance(out, PricingResult), out
    ladder = cap_ladder(cap)
    assert len(ladder) == 3  # 4 semi-annual periods over 2Y, first excluded
    parts = [price(c, model) for c in ladder]
    assert all(isinstance(p, PricingResult) for p in parts)
    total = sum(p.pv.amount for p in parts if isinstance(p, PricingResult))
    assert abs(out.pv.amount - total) < 1e-12


def test_capfloor_validates_its_shape() -> None:
    import pytest

    with pytest.raises(ValueError):  # a non-positive notional
        CapFloor(INDEX, build_schedule(VAL, END, TERMS), STRIKE, 0.0)
    with pytest.raises(ValueError):  # one period ⇒ an EMPTY ladder once the first is excluded
        CapFloor(INDEX, build_schedule(VAL, VAL + Tenor(3, M), TERMS), STRIKE, NOTIONAL)
