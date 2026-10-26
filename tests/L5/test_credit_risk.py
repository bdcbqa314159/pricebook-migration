"""Credit slice 3 — L5 credit risk on the CDS (`spec_credit_slice3_risk.md` §3).

Two oracle families, as ruled:

1. **Analytic vs finite-difference (rung 1, the slice-0 pattern).** For a flat-hazard CDS the PV is
   closed form, so `∂PV/∂λ` is differentiable analytically and compared with the bump-reprice
   `cs01`. An FD-only test would only prove the bump is self-consistent.
2. **Structural (§6).** Bucketed CS01 is a **decomposition**: the per-pillar bumps partition the
   curve's hazard segments, so they must **sum to** the parallel CS01 (to cross-convexity), and
   **N pillars → N buckets** is a count. A scalar off the decomposition cannot see a dropped bucket.
"""

import math
from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, SolveConfig
from pricebook.calibration.credit import CdsParQuote, CreditBootstrapSpec, bootstrap_survival_curve
from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    IntegrationConfig,
    Money,
    PricingFailure,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    currency,
)
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot, RecoveryKey
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.models.discounting_model import DiscountingModel
from pricebook.products.credit import CDS, PremiumLeg
from pricebook.risk.credit import bucketed_cs01, cs01
from pricebook.risk.priceable import priceable

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
DC360 = DayCountConvention.ACT_360
VAL = date(2026, 1, 15)
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(15, Y)
ACME = ReferenceEntity("ACME")
EUR = currency("EUR")
RECOVERY = 0.40
NOTIONAL = 10_000_000.0
NUMERICS = IntegrationConfig(steps_per_year=12)
SURV_KEY = CurveKey(CurveRole.SURVIVAL, ACME)
BP = 1e-4


def _snap(surv: SurvivalCurve, r: float = 0.03) -> MarketSnapshot:
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, EUR): DiscountCurve.flat(TM, r, until=FAR),
            SURV_KEY: surv,
        }
    )
    # recovery is L1 since slice 4 — the single source the bootstrap and the mark both read
    return MarketSnapshot(VAL, curves, scalars={RecoveryKey(ACME): RECOVERY})


def _cds(spread: float, years: int = 5) -> CDS:
    sched = build_schedule(
        VAL, VAL + Tenor(years, Y),
        ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)),
    )
    return CDS(ACME, PremiumLeg(sched, DC360, spread), Money(NOTIONAL, EUR))


def _p(cds: CDS):
    return priceable(cds, DiscountingModel, NUMERICS)


# ── ORACLE 1 — analytic ∂PV/∂λ vs the bump-reprice CS01 ────────────────────────────────────
def _analytic_dpv_dlambda(spread: float, lam: float, r: float, years: int) -> float:
    """`∂PV/∂λ` for the continuous flat-hazard CDS, differentiated in closed form.

        protection(λ) = (1−R)·λ/k·(1 − e^{−kT}),  annuity(λ) = (1 − e^{−kT})/k,   k = r + λ

        ∂protection/∂λ = (1−R)·[ (1 − e^{−kT})·r/k² + λ·T·e^{−kT}/k ]
        ∂annuity/∂λ    = −(1 − e^{−kT})/k² + T·e^{−kT}/k

    so `∂PV/∂λ = N·(∂protection/∂λ − s·∂annuity/∂λ)`. Derived, not fitted."""
    k = r + lam
    T = TM.year_fraction(VAL + Tenor(years, Y))
    e = math.exp(-k * T)
    d_prot = (1.0 - RECOVERY) * ((1.0 - e) * r / k**2 + lam * T * e / k)
    d_ann = -(1.0 - e) / k**2 + T * e / k
    return NOTIONAL * (d_prot - spread * d_ann)


def test_cs01_matches_the_analytic_derivative_of_the_flat_hazard_pv() -> None:
    lam, r, years = 0.03, 0.03, 5
    for spread in (0.0050, 0.0180, 0.0300):
        market = _snap(SurvivalCurve.flat_hazard(TM, lam, until=FAR), r)
        got = cs01(_p(_cds(spread, years)), market, SURV_KEY)
        assert not isinstance(got, PricingFailure), got
        # cs01 is reported per 1bp of hazard, so the analytic derivative scales by 1bp
        expected = _analytic_dpv_dlambda(spread, lam, r, years) * BP
        assert abs(got - expected) < 0.02 * abs(expected) + 1.0, (spread, got, expected)


def test_cs01_is_positive_for_bought_protection_and_flips_with_the_notional() -> None:
    """Widening spreads make bought protection more valuable — a sign check the FD alone would pass
    whatever the convention, so it is asserted explicitly."""
    market = _snap(SurvivalCurve.flat_hazard(TM, 0.03, until=FAR))
    bought = cs01(_p(_cds(0.0180)), market, SURV_KEY)
    sold = _cds(0.0180)
    sold = CDS(sold.entity, sold.premium, Money(-NOTIONAL, EUR))
    assert not isinstance(bought, PricingFailure)
    sold_cs01 = cs01(_p(sold), market, SURV_KEY)
    assert not isinstance(sold_cs01, PricingFailure)
    assert bought > 0.0
    assert abs(bought + sold_cs01) < 1e-9


# ── ORACLE 2 — STRUCTURAL: the bucketed decomposition ──────────────────────────────────────
def _bootstrapped(spreads: dict[int, float], r: float = 0.03):
    disc = DiscountCurve.flat(TM, r, until=FAR)
    quotes = tuple(CdsParQuote(VAL + Tenor(y, Y), s) for y, s in sorted(spreads.items()))
    base = MarketSnapshot(
        VAL, CurveSet({CurveKey(CurveRole.DISCOUNT, EUR): disc}),
        scalars={RecoveryKey(ACME): RECOVERY},
    )
    out = bootstrap_survival_curve(
        CreditBootstrapSpec(ACME, EUR, quotes, base, SolveConfig(tolerance=1e-14))
    )
    assert not isinstance(out, CalibrationFailure), out
    return out[0]


def test_bucketed_cs01_has_one_bucket_per_hazard_segment() -> None:
    """A COUNT, not a scalar: N par quotes bootstrap N hazard segments, so N buckets. A dropped
    bucket must be impossible to represent, not merely unlikely."""
    spreads = {1: 0.0080, 3: 0.0105, 5: 0.0130, 7: 0.0150, 10: 0.0165}
    curve = _bootstrapped(spreads)
    buckets = bucketed_cs01(_p(_cds(0.0130, 10)), _snap(curve), SURV_KEY)
    assert not isinstance(buckets, PricingFailure), buckets
    assert len(buckets) == len(spreads) == len(curve.times) - 1
    assert all(isinstance(b, float) for b in buckets)


def test_bucketed_cs01_sums_to_the_parallel_cs01() -> None:
    """The decomposition identity: the per-pillar bumps partition the curve's hazard segments, so
    their sum is the parallel bump up to cross-convexity. This is what a scalar CS01 cannot check."""
    spreads = {1: 0.0080, 3: 0.0105, 5: 0.0130, 7: 0.0150, 10: 0.0165}
    market = _snap(_bootstrapped(spreads))
    p = _p(_cds(0.0130, 10))
    parallel = cs01(p, market, SURV_KEY)
    buckets = bucketed_cs01(p, market, SURV_KEY)
    assert not isinstance(parallel, PricingFailure) and not isinstance(buckets, PricingFailure)
    assert abs(sum(buckets) - parallel) < 1e-4 * abs(parallel) + 1e-9, (sum(buckets), parallel)


def test_only_buckets_up_to_maturity_carry_risk() -> None:
    """A 3Y CDS on a 10Y curve: the segments beyond its maturity cannot affect its PV, so their
    buckets are zero. A bucketed number that smeared risk past maturity would be wrong and a
    parallel CS01 could not reveal it."""
    spreads = {1: 0.0080, 3: 0.0105, 5: 0.0130, 7: 0.0150, 10: 0.0165}
    market = _snap(_bootstrapped(spreads))
    buckets = bucketed_cs01(_p(_cds(0.0105, 3)), market, SURV_KEY)
    assert not isinstance(buckets, PricingFailure), buckets
    assert len(buckets) == 5
    assert abs(buckets[0]) > 0.0 and abs(buckets[1]) > 0.0     # 1Y and 3Y segments bite
    for i in (2, 3, 4):                                        # 5Y, 7Y, 10Y segments do not
        assert abs(buckets[i]) < 1e-9, (i, buckets[i])


# ── failure propagation (invariant 4) ──────────────────────────────────────────────────────
def test_cs01_without_a_survival_curve_is_a_failure_value() -> None:
    curves = CurveSet({CurveKey(CurveRole.DISCOUNT, EUR): DiscountCurve.flat(TM, 0.03, until=FAR)})
    out = cs01(
        _p(_cds(0.0180)),
        MarketSnapshot(VAL, curves, scalars={RecoveryKey(ACME): RECOVERY}),
        SURV_KEY,
    )
    assert isinstance(out, PricingFailure), out


def test_cs01_without_an_integration_config_is_a_failure_value() -> None:
    """The bumped reprice must use the same grid as the base; absent, the engine fails as a value
    and risk propagates it rather than inventing one (invariant 5 + invariant 4)."""
    market = _snap(SurvivalCurve.flat_hazard(TM, 0.03, until=FAR))
    out = cs01(priceable(_cds(0.0180), DiscountingModel), market, SURV_KEY)
    assert isinstance(out, PricingFailure), out


# ── the single-pillar bump itself ──────────────────────────────────────────────────────────
def test_bumped_at_moves_one_segment_and_leaves_earlier_pillars_untouched() -> None:
    curve = _bootstrapped({1: 0.0080, 3: 0.0105, 5: 0.0130})
    bumped = curve.bumped_at(1, 10 * BP)
    assert abs(bumped.survivals[1] - curve.survivals[1]) < 1e-15   # before the segment: untouched
    assert bumped.survivals[2] < curve.survivals[2]                # the bumped segment
    assert bumped.survivals[3] < curve.survivals[3]                # and everything after it
    # the hazard of the bumped segment moved by exactly the shift
    h0 = curve.hazard(VAL + Tenor(2, Y))
    h1 = bumped.hazard(VAL + Tenor(2, Y))
    assert abs((h1 - h0) - 10 * BP) < 1e-12


def test_bumped_at_rejects_a_pillar_outside_the_curve() -> None:
    import pytest

    curve = _bootstrapped({1: 0.0080, 3: 0.0105})
    with pytest.raises(ValueError):
        curve.bumped_at(2, BP)
