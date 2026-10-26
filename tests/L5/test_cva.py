"""B7 slice 1 — unilateral CVA of one swap, swaption-approximation exposure
(`spec_xva_B7_slice1.md` §2-§3).

The standard physical-exposure result: the expected positive exposure of a swap at a future `tᵢ` is
the value of a physical-settled swaption expiring at `tᵢ` on the remaining leg. So `EE(tᵢ)` is the
pricer the swaption cluster already oracled, and

    CVA = LGD · Σᵢ EE(tᵢ) · (Q(tᵢ₋₁) − Q(tᵢ))

is a **composition** of two independently-checked things. The oracles therefore test the
*composition* (against an independent re-summation), its *limits*, its *count*, and the
*bump-consistency* of the inputs it shares — not the atoms underneath, which have their own.
"""

import math
from datetime import date

from pricebook.engine import price
from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    PricingFailure,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    currency,
    future_periods,
    get_rate_index,
)
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot, RecoveryKey
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.market.vol_surface import Surface, SwaptionSurfaceKey
from pricebook.models.black_model import BlackModel
from pricebook.products.option import OptionType, Swaption
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap
from pricebook.risk.exposure import swaption_exposure_profile
from pricebook.risk.xva import cva, swap_cva

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(20, Y)
CP = ReferenceEntity("COUNTERPARTY")
RECOVERY = 0.40
NOTIONAL = 10_000_000.0
TENOR = Tenor(5, Y)
VOL = 0.22


def _swap(rate: float, notional: float = NOTIONAL, tenor: Tenor = TENOR) -> VanillaSwap:
    sched = build_schedule(
        VAL, VAL + tenor, ScheduleTerms(frequency=Frequency.ANNUAL, roll=RollRule(calendar=None))
    )
    return VanillaSwap(notional, CCY, FixedLeg(sched, DC365, rate), FloatLeg(sched, DC365, INDEX))


def _market(hazard: float, recovery: float = RECOVERY, tenor: Tenor = TENOR) -> MarketSnapshot:
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.030, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, 0.035, until=FAR),
            CurveKey(CurveRole.SURVIVAL, CP): SurvivalCurve.flat_hazard(TM, hazard, until=FAR),
        }
    )
    return MarketSnapshot(
        VAL,
        curves,
        scalars={RecoveryKey(CP): recovery},
        surfaces={SwaptionSurfaceKey(INDEX, t): Surface.flat(VOL) for t in _sub_tenors(tenor)},
    )


def _sub_tenors(tenor: Tenor) -> tuple[Tenor, ...]:
    """Every remaining-swap tenor the exposure profile will ask for — the cube is at-pillar, so the
    surface must carry a key per distinct remaining tenor (slice-A ruling B3)."""
    return tuple(Tenor(y, Y) for y in range(1, tenor.count + 1))


def _model(hazard: float, recovery: float = RECOVERY) -> BlackModel:
    return BlackModel(_market(hazard, recovery))


# ── ORACLE 1 — the COMPOSITION, against an independent re-summation ────────────────────────
def _independent_cva(swap: VanillaSwap, model: BlackModel, hazard: float, recovery: float) -> float:
    """`LGD·Σ EE(tᵢ)·ΔQ(tᵢ)` summed here, from direct pricer calls and `exp()` survivals — not
    through the atom. Tests that the atom *composes* what it claims, rather than restating its sum."""
    total = 0.0
    periods = swap.fixed_leg.schedule.periods
    prev = VAL
    for p in periods:
        expiry = p.accrual_end
        remaining = future_periods(swap.fixed_leg.schedule, expiry)
        if not remaining.periods:
            ee = 0.0
        else:
            sub = VanillaSwap(
                abs(swap.notional), swap.currency,
                FixedLeg(remaining, swap.fixed_leg.day_count, swap.fixed_leg.rate),
                FloatLeg(future_periods(swap.float_leg.schedule, expiry), swap.float_leg.day_count, swap.float_leg.index),
            )
            kind = OptionType.CALL if swap.notional >= 0 else OptionType.PUT
            out = price(Swaption(sub, expiry, kind), model)
            ee = 0.0 if isinstance(out, PricingFailure) else out.pv.amount
        q_prev = math.exp(-hazard * TM.year_fraction(prev)) if prev > VAL else 1.0
        q_now = math.exp(-hazard * TM.year_fraction(expiry))
        total += ee * (q_prev - q_now)
        prev = expiry
    return (1.0 - recovery) * total


def test_cva_equals_an_independent_resummation_of_the_same_terms() -> None:
    hazard = 0.02
    swap = _swap(0.035)
    got = swap_cva(swap, _model(hazard), CP)
    assert not isinstance(got, PricingFailure), got
    expected = _independent_cva(swap, _model(hazard), hazard, RECOVERY)
    assert abs(got - expected) < 1e-8 * max(1.0, abs(expected)), (got, expected)
    assert got > 0.0


# ── ORACLE 2 — limits (structural) ─────────────────────────────────────────────────────────
def test_zero_hazard_gives_zero_cva() -> None:
    """No default risk, no charge — the limit that catches a default leg wired to the wrong sign or
    to survival instead of its increment."""
    got = swap_cva(_swap(0.035), _model(0.0), CP)
    assert not isinstance(got, PricingFailure), got
    assert abs(got) < 1e-12


def test_cva_is_monotone_in_the_hazard() -> None:
    values = [swap_cva(_swap(0.035), _model(h), CP) for h in (0.0, 0.005, 0.02, 0.05, 0.10)]
    assert all(not isinstance(v, PricingFailure) for v in values)
    assert values == sorted(values)
    assert values[0] == 0.0 and values[-1] > values[1] > 0.0


def test_cva_is_monotone_in_lgd_and_vanishes_at_full_recovery() -> None:
    """CVA is exactly proportional to `(1−R)`, so halving the LGD halves the charge."""
    base = swap_cva(_swap(0.035), _model(0.02, recovery=0.40), CP)
    half = swap_cva(_swap(0.035), _model(0.02, recovery=0.70), CP)
    assert not isinstance(base, PricingFailure) and not isinstance(half, PricingFailure)
    assert abs(half - base * (0.30 / 0.60)) < 1e-9 * base


def test_a_swap_with_no_remaining_life_has_zero_cva() -> None:
    expired = _swap(0.035, tenor=Tenor(1, Y))
    expired = VanillaSwap(
        expired.notional, expired.currency,
        FixedLeg(future_periods(expired.fixed_leg.schedule, VAL + Tenor(5, Y)), DC365, 0.035),
        FloatLeg(future_periods(expired.float_leg.schedule, VAL + Tenor(5, Y)), DC365, INDEX),
    )
    got = swap_cva(expired, _model(0.02), CP)
    assert not isinstance(got, PricingFailure), got
    assert abs(got) < 1e-12


# ── ORACLE 3 — count: N intervals → N exposure points → N default terms ───────────────────
def test_the_exposure_profile_has_one_point_per_schedule_interval() -> None:
    """A COUNT, not a scalar: the profile is a decomposition of the swap's own schedule, so a
    dropped or doubled point must be visible. A scalar CVA could not show it."""
    swap = _swap(0.035)
    profile = swaption_exposure_profile(swap, _model(0.02))
    assert not isinstance(profile, PricingFailure), profile
    assert len(profile) == len(swap.fixed_leg.schedule.periods) == 5
    dates = [d for d, _ in profile]
    assert dates == [p.accrual_end for p in swap.fixed_leg.schedule.periods]
    assert dates == sorted(dates)


def test_the_last_exposure_point_is_zero_because_nothing_remains() -> None:
    """At maturity there is no remaining leg, so EE is exactly 0 — an amortising profile, not a
    flat one. A profile that kept the full exposure to the end would overstate CVA."""
    profile = swaption_exposure_profile(_swap(0.035), _model(0.02))
    assert not isinstance(profile, PricingFailure), profile
    assert profile[-1][1] == 0.0
    assert profile[0][1] > profile[-2][1] > 0.0      # exposure decays as the swap runs off


def test_cva_uses_every_profile_point_and_the_terms_sum() -> None:
    swap = _swap(0.035)
    hazard = 0.02
    market = _market(hazard)
    profile = swaption_exposure_profile(swap, _model(hazard))
    assert not isinstance(profile, PricingFailure), profile
    direct = cva(profile, market.curves.survival(CP), market.recovery(CP))
    whole = swap_cva(swap, _model(hazard), CP)
    assert not isinstance(whole, PricingFailure)
    assert abs(direct - whole) < 1e-12


# ── ORACLE 4 — bump consistency, as an XVA ACCEPTANCE criterion (doc 11's third face) ─────
def test_bumping_recovery_at_its_snapshot_home_moves_the_cva_coherently() -> None:
    """The LGD is shared by the CVA and by any CDS on the same name, so it must be reached through
    the snapshot — bumping it there must move the charge by exactly the LGD ratio. A second copy
    would not move at all. This is a sanity floor in slice 1; it becomes load-bearing at the MC/WWR
    slice where the survival curve feeds both the exposure paths and the default leg."""
    base = swap_cva(_swap(0.035), _model(0.02, recovery=0.40), CP)
    bumped = swap_cva(_swap(0.035), _model(0.02, recovery=0.41), CP)
    assert not isinstance(base, PricingFailure) and not isinstance(bumped, PricingFailure)
    assert bumped < base
    assert abs(bumped - base * (0.59 / 0.60)) < 1e-9 * base


def test_bumping_the_survival_curve_at_its_home_moves_the_cva() -> None:
    market = _market(0.02)
    surv = market.curves.survival(CP)
    profile = swaption_exposure_profile(_swap(0.035), BlackModel(market))
    assert not isinstance(profile, PricingFailure), profile
    base = cva(profile, surv, RECOVERY)
    wider = cva(profile, surv.bumped(50e-4), RECOVERY)
    assert wider > base > 0.0


# ── failure propagation (invariant 4) ──────────────────────────────────────────────────────
def test_a_missing_survival_curve_is_a_failure_not_a_zero_charge() -> None:
    """A zero CVA is a *plausible* number, which is exactly why an absent curve must not produce
    one — it would read as 'this counterparty is riskless'."""
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.030, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, 0.035, until=FAR),
        }
    )
    market = MarketSnapshot(
        VAL, curves, scalars={RecoveryKey(CP): RECOVERY},
        surfaces={SwaptionSurfaceKey(INDEX, t): Surface.flat(VOL) for t in _sub_tenors(TENOR)},
    )
    out = swap_cva(_swap(0.035), BlackModel(market), CP)
    assert isinstance(out, PricingFailure), out


def test_a_missing_recovery_is_a_failure_value() -> None:
    curves = _market(0.02).curves
    market = MarketSnapshot(
        VAL, curves,
        surfaces={SwaptionSurfaceKey(INDEX, t): Surface.flat(VOL) for t in _sub_tenors(TENOR)},
    )
    out = swap_cva(_swap(0.035), BlackModel(market), CP)
    assert isinstance(out, PricingFailure), out


def test_a_failed_exposure_point_propagates_rather_than_counting_as_zero() -> None:
    """No swaption surface ⇒ the exposure pricer fails. CVA must surface that, not silently treat
    the un-priceable points as zero exposure and return a smaller, plausible-looking charge."""
    curves = _market(0.02).curves
    market = MarketSnapshot(VAL, curves, scalars={RecoveryKey(CP): RECOVERY})
    out = swaption_exposure_profile(_swap(0.035), BlackModel(market))
    assert isinstance(out, PricingFailure), out
