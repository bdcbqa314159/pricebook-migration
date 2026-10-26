"""Credit slice 1 — the L0 identity and the L1 survival curve (`spec_credit_B6_slice1.md` §3).

Oracle 1 is **closed form (rung 1)**: under a flat hazard λ the survival curve is `Q(t) = exp(−λt)`
exactly, and the hazard read back is λ at every t. No self-consistency anywhere in this file.
"""

import dataclasses
import math
from datetime import date

import pytest

from pricebook.foundation import (
    AssetClass,
    DayCountConvention,
    TimeMeasure,
    Tenor,
    TenorUnit,
)
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.foundation.underlying import Underlying
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.survival_curve import SurvivalCurve

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
VAL = date(2026, 1, 15)
TM = TimeMeasure(VAL, DC365)
ACME = ReferenceEntity("ACME")


def _flat(lam: float, years: int = 10) -> SurvivalCurve:
    return SurvivalCurve.flat_hazard(TM, lam, until=VAL + Tenor(years, Y))


# ── the L0 identity ─────────────────────────────────────────────────────────────────────────
def test_reference_entity_satisfies_the_underlying_protocol() -> None:
    assert isinstance(ACME, Underlying)
    assert ACME.name == "ACME"
    assert ACME.asset_class is AssetClass.CREDIT


def test_reference_entity_is_frozen_and_hashable_so_it_can_key_a_curve() -> None:
    # `setattr` rather than a direct attribute assignment: the direct form needs a type-checker
    # suppression, and §5 says a suppression is ledgered or does not exist — a frozenness assertion
    # should not owe debt. (Do not spell the suppression out in prose here either: `verify.py debt`
    # matches the literal text per line, so even a comment ABOUT one counts as one.)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(ACME, "name", "OTHER")
    assert {ACME: 1}[ReferenceEntity("ACME")] == 1  # value identity, not object identity


def test_an_empty_entity_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        ReferenceEntity("")


# ── ORACLE 1 — closed form: Q(t) = exp(−λt) ────────────────────────────────────────────────
def test_flat_hazard_survival_is_exp_minus_lambda_t() -> None:
    lam = 0.02
    curve = _flat(lam)
    for years in (0.5, 1.0, 2.5, 5.0, 9.0):
        d = VAL + Tenor(int(years * 12), TenorUnit.MONTH)
        t = TM.year_fraction(d)
        assert abs(curve.survival(d) - math.exp(-lam * t)) < 1e-12


def test_flat_hazard_reads_back_lambda_at_every_pillar() -> None:
    lam = 0.035
    curve = _flat(lam)
    for months in (6, 18, 36, 84):
        assert abs(curve.hazard(VAL + Tenor(months, TenorUnit.MONTH)) - lam) < 1e-9


def test_survival_is_one_at_the_valuation_date_and_monotone_decreasing() -> None:
    curve = _flat(0.02)
    assert abs(curve.survival(VAL) - 1.0) < 1e-15
    prev = 1.0
    for months in range(3, 120, 3):
        q = curve.survival(VAL + Tenor(months, TenorUnit.MONTH))
        assert 0.0 < q <= prev
        prev = q


def test_piecewise_constant_hazard_between_pillars_is_log_linear_in_Q() -> None:
    """Two pillars with different hazards: log Q is linear in t within each segment."""
    t1, t2 = 2.0, 5.0
    lam1, lam2 = 0.01, 0.04
    q1 = math.exp(-lam1 * t1)
    q2 = q1 * math.exp(-lam2 * (t2 - t1))
    curve = SurvivalCurve(TM, (0.0, t1, t2), (1.0, q1, q2))
    mid = 3.5  # inside the second segment
    d = VAL + Tenor(int(mid * 12), TenorUnit.MONTH)
    expected = q1 * math.exp(-lam2 * (TM.year_fraction(d) - t1))
    assert abs(curve.survival(d) - expected) < 1e-10
    assert abs(curve.hazard(d) - lam2) < 1e-8


def test_a_survival_probability_outside_zero_one_is_rejected() -> None:
    with pytest.raises(ValueError):
        SurvivalCurve(TM, (0.0, 1.0), (1.0, 1.5))
    with pytest.raises(ValueError):
        SurvivalCurve(TM, (0.0, 1.0), (1.0, 0.0))


def test_a_non_monotone_survival_curve_is_rejected() -> None:
    """Q must be non-increasing — a rising Q is negative hazard, i.e. un-defaulting."""
    with pytest.raises(ValueError):
        SurvivalCurve(TM, (0.0, 1.0, 2.0), (1.0, 0.95, 0.97))


def test_bumping_shifts_the_hazard_and_leaves_the_curve_frozen() -> None:
    lam, shift = 0.02, 0.0010
    base = _flat(lam)
    bumped = base.bumped(shift)
    d = VAL + Tenor(5, Y)
    t = TM.year_fraction(d)
    assert abs(bumped.survival(d) - math.exp(-(lam + shift) * t)) < 1e-10
    assert abs(base.survival(d) - math.exp(-lam * t)) < 1e-12  # original untouched


# ── the CurveSet accessor that was deferred until this asset class ─────────────────────────
def test_curve_set_survival_accessor_is_keyed_by_the_entity() -> None:
    curve = _flat(0.02)
    curves = CurveSet({CurveKey(CurveRole.SURVIVAL, ACME): curve})
    assert curves.survival(ACME) is curve


def test_an_unknown_entity_raises_rather_than_returning_a_default() -> None:
    curves = CurveSet({CurveKey(CurveRole.SURVIVAL, ACME): _flat(0.02)})
    with pytest.raises(KeyError):
        curves.survival(ReferenceEntity("OTHER"))


def test_a_survival_curve_does_not_masquerade_as_a_discount_curve() -> None:
    """Distinct capability, distinct key — a survival curve has no `df`."""
    assert not hasattr(_flat(0.02), "df")


# ── O1 follow-up: the interpolation oracle existed since slice 1 (above); these STRENGTHEN it ──
def test_log_linear_interpolation_holds_in_the_FIRST_segment_too() -> None:
    """The slice-1 oracle probed the second segment. A scheme that interpolated across the whole
    curve rather than per-segment would match there but not here, so the first segment is a
    genuinely distinct case."""
    t1, t2 = 2.0, 5.0
    lam1, lam2 = 0.01, 0.04
    q1 = math.exp(-lam1 * t1)
    q2 = q1 * math.exp(-lam2 * (t2 - t1))
    curve = SurvivalCurve(TM, (0.0, t1, t2), (1.0, q1, q2))
    d = VAL + Tenor(12, TenorUnit.MONTH)  # t ≈ 1.0, inside the FIRST segment
    t = TM.year_fraction(d)
    assert abs(curve.survival(d) - math.exp(-lam1 * t)) < 1e-12
    assert abs(curve.hazard(d) - lam1) < 1e-9


def test_a_three_segment_curve_interpolates_PER_SEGMENT_not_across_the_curve() -> None:
    """Three hazards, probed in the middle one. A whole-curve interpolation (log-linear from the
    first pillar to the last) would give a different number here — which is what makes this an
    oracle rather than a restatement of the construction."""
    ts = (1.0, 3.0, 7.0)
    lams = (0.005, 0.030, 0.012)
    qs = [1.0]
    prev_t = 0.0
    for t, lam in zip(ts, lams):
        qs.append(qs[-1] * math.exp(-lam * (t - prev_t)))
        prev_t = t
    curve = SurvivalCurve(TM, (0.0, *ts), tuple(qs))

    d = VAL + Tenor(24, TenorUnit.MONTH)  # t ≈ 2.0, inside the SECOND segment
    t = TM.year_fraction(d)
    expected = qs[1] * math.exp(-lams[1] * (t - ts[0]))
    whole_curve = math.exp(math.log(1.0) + (math.log(qs[-1]) - math.log(1.0)) * t / ts[-1])
    assert abs(expected - whole_curve) > 1e-3, "the two schemes must differ or this proves nothing"
    assert abs(curve.survival(d) - expected) < 1e-12
    assert abs(curve.hazard(d) - lams[1]) < 1e-9
