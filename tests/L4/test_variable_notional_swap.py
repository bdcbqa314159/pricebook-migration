"""Variable-notional swap — the `weighted_annuity` atom and the strip decomposition.

`weighted_annuity(schedule, notionals, …) = Σ Nᵢ·τᵢ·df(payᵢ)` is `rpv01` generalised with a
per-period notional, and `weighted_float_leg_pv` is the same generalisation of `float_leg_pv`.
Both are built on the SAME per-period `τ·df` derivation the flat atoms use (§3d: an atom is
derived once and weighted two ways, never re-derived), so the flat-vs-weighted identities below
are genuine floating-point assertions rather than tautologies — no implementation short-circuit
makes them true by construction.

The structural oracle is the **strip decomposition** (§6): an amortising swap IS a strip of
constant-notional vanilla swaps, each priced by the EXISTING engine. That tests the composition
against an independent construction instead of re-summing the thing under test.
"""

from dataclasses import replace
from datetime import date

import pytest

from pricebook.calibration.calibrate import (
    CalibrationSpec,
    CurveBuild,
    ParSwapQuote,
    calibrate,
    par_swap,
)
from pricebook.engine.linear import price
from pricebook.foundation import (
    Currency,
    DayCountConvention,
    Frequency,
    PricingResult,
    Tenor,
    TenorUnit,
    get_rate_index,
)
from pricebook.market.building_blocks import (
    float_leg_pv,
    rpv01,
    weighted_annuity,
    weighted_float_leg_pv,
)

VAL = date(2026, 1, 15)
ESTR = get_rate_index("ESTR")
EURIBOR_3M = get_rate_index("EURIBOR_3M")
DC = DayCountConvention.ACT_365_FIXED
OIS = tuple(
    ParSwapQuote(Tenor(y, TenorUnit.YEAR), r) for y, r in [(1, 0.030), (2, 0.032), (3, 0.034), (5, 0.036)]
)
EUR = tuple(
    ParSwapQuote(Tenor(y, TenorUnit.YEAR), r) for y, r in [(1, 0.0312), (2, 0.0332), (3, 0.0352), (5, 0.0372)]
)
DISCOUNT = CurveBuild(index=ESTR, frequency=Frequency.ANNUAL, day_count=DC, quotes=OIS)
PROJECTION = CurveBuild(index=EURIBOR_3M, frequency=Frequency.ANNUAL, day_count=DC, quotes=EUR)
SPEC = CalibrationSpec.single_currency(
    valuation_date=VAL, currency=Currency.EUR, discount=DISCOUNT, projection=PROJECTION
)
K = 0.0352  # the 3Y par rate — the strip and the amortising swap must share ONE fixed rate


def _model():
    model, _ = calibrate(SPEC)
    return model


def _swap(years: int, notional: float = 1_000_000.0):
    s = par_swap(SPEC, PROJECTION, Tenor(years, TenorUnit.YEAR), K)
    return replace(s, notional=notional)


def _amortising(notionals: tuple[float, ...]):
    """A swap whose legs carry a per-period notional schedule, aligned to their own periods."""
    s = _swap(len(notionals), notional=notionals[0])
    return replace(
        s,
        fixed_leg=replace(s.fixed_leg, notionals=notionals),
        float_leg=replace(s.float_leg, notionals=notionals),
    )


# ── the §3d identities: the weighted atom at a FLAT schedule is the flat atom ────────────────
def test_weighted_annuity_at_a_flat_schedule_IS_N_times_rpv01() -> None:
    model = _model()
    curve = model.market.curves.discount(Currency.EUR, None)
    s = _swap(3)
    sched, dc = s.fixed_leg.schedule, s.fixed_leg.day_count
    n = len(sched.periods)
    for notional in (1.0, 1_000_000.0, -250_000.0):
        flat = (notional,) * n
        assert weighted_annuity(sched, flat, dc, curve) == pytest.approx(
            notional * rpv01(sched, dc, curve), abs=1e-12, rel=1e-12
        )


def test_weighted_float_leg_at_a_flat_schedule_IS_N_times_float_leg_pv() -> None:
    model = _model()
    curves = model.market.curves
    disc = curves.discount(Currency.EUR, None)
    proj = curves.projection(EURIBOR_3M)
    s = _swap(3)
    sched, dc = s.float_leg.schedule, s.float_leg.day_count
    flat = (1_000_000.0,) * len(sched.periods)
    assert weighted_float_leg_pv(sched, flat, dc, disc, proj) == pytest.approx(
        1_000_000.0 * float_leg_pv(sched, dc, disc, proj), abs=1e-12, rel=1e-12
    )


# ── the STRUCTURAL oracle: an amortising swap IS a strip of vanilla swaps ────────────────────
def test_an_amortising_swap_EQUALS_a_strip_of_constant_notional_swaps() -> None:
    """`PV(N₁,N₂,N₃) = Σₘ (Nₘ − Nₘ₊₁)·PV(vanilla maturing at m)`, with Nₙ₊₁ = 0.

    With notionals (300k, 200k, 100k) the step amounts are all 100k, so the amortiser is exactly
    a 1Y + 2Y + 3Y strip of 100k vanilla swaps at the same fixed rate — **each priced by the
    existing engine**, so the right-hand side never touches the code under test.
    """
    model = _model()
    amort = _amortising((300_000.0, 200_000.0, 100_000.0))
    got = price(amort, model)
    assert isinstance(got, PricingResult), got

    strip = 0.0
    for years in (1, 2, 3):
        leg = price(_swap(years, notional=100_000.0), model)
        assert isinstance(leg, PricingResult), leg
        strip += leg.pv.amount
    assert got.pv.amount == pytest.approx(strip, abs=1e-8, rel=1e-12)


def test_the_strip_is_a_REAL_decomposition_the_schedules_actually_nest() -> None:
    """Guards the oracle above: it is only a decomposition if the 1Y/2Y/3Y schedules are prefixes
    of one another. If the generator did not nest, the strip identity would be comparing swaps
    with different accrual dates and the agreement above would be luck."""
    periods = [tuple(p.accrual_start for p in _swap(y).fixed_leg.schedule.periods) for y in (1, 2, 3)]
    assert periods[0] == periods[1][:1]
    assert periods[1] == periods[2][:2]
    assert len(periods[2]) == 3


def test_a_FLAT_notional_schedule_prices_exactly_like_the_scalar_swap() -> None:
    model = _model()
    scalar = price(_swap(3, notional=500_000.0), model)
    carried = price(_amortising((500_000.0,) * 3), model)
    assert isinstance(scalar, PricingResult) and isinstance(carried, PricingResult)
    assert carried.pv.amount == pytest.approx(scalar.pv.amount, abs=1e-8, rel=1e-12)


# ── the two consumed readers ─────────────────────────────────────────────────────────────────
def test_the_readers_the_desks_consume() -> None:
    amort = _amortising((300_000.0, 200_000.0, 100_000.0))
    assert amort.notional_schedule() == (300_000.0, 200_000.0, 100_000.0)
    assert amort.average_notional() == pytest.approx(200_000.0)  # arithmetic mean (quarry's definition)
    flat = _swap(3, notional=750_000.0)
    assert flat.notional_schedule() == (750_000.0,) * 3
    assert flat.average_notional() == pytest.approx(750_000.0)


def test_a_notional_schedule_that_does_not_match_its_periods_is_REFUSED() -> None:
    s = _swap(3)
    with pytest.raises(ValueError, match="notional"):
        replace(s.fixed_leg, notionals=(1.0, 2.0))  # 2 notionals, 3 periods


def test_the_dead_constructors_are_NOT_built() -> None:
    """`amortising`/`accreting`/`roller_coaster` have 0 references in the quarry incl. its tests
    (§4 `dead`), so the sugar is shed — only the schedule-carrying shape and its two readers
    cross. Asserted so a later slice does not quietly re-import the quarry's shape."""
    from pricebook.products.swap import VanillaSwap

    for sugar in ("amortising", "accreting", "roller_coaster"):
        assert not hasattr(VanillaSwap, sugar)
