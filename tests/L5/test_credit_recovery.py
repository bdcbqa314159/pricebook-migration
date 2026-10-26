"""Credit slice 4 — recovery as L1 market state, and `rec01` (`spec_credit_slice4_recovery.md`).

**Why recovery moved.** §3c: *"Hazard/survival curve and recovery → L1 (risk bumps them)"*. Slices
2-3 kept it in **two** places — on the L2 product and on the bootstrap spec — which is a latent §3d
divergence, not a tidiness point. Measured before the move: with the curve bootstrapped at R=0.40
and the CDS marked at R=0.30, a **par** quote priced to **+96,431** on 10mm (≈96bp of notional),
silently. That is the day-count bug's twin, and the first test below makes it unrepresentable.
"""

import math
from datetime import date

import pytest

from pricebook.calibration.calibrate import CalibrationFailure, SolveConfig
from pricebook.calibration.credit import CdsParQuote, CreditBootstrapSpec, bootstrap_survival_curve
from pricebook.engine import price
from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    IntegrationConfig,
    Money,
    PricingFailure,
    PricingResult,
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
from pricebook.models.discounting_model import DiscountingModel
from pricebook.products.credit import CDS, PremiumLeg
from pricebook.risk.credit import rec01
from pricebook.risk.priceable import priceable

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
DC360 = DayCountConvention.ACT_360
VAL = date(2026, 1, 15)
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(15, Y)
ACME = ReferenceEntity("ACME")
EUR = currency("EUR")
NOTIONAL = 10_000_000.0
NUMERICS = IntegrationConfig(steps_per_year=12)
BP = 1e-4


def _disc(r: float = 0.03) -> DiscountCurve:
    return DiscountCurve.flat(TM, r, until=FAR)


def _snap(recovery: float, surv, r: float = 0.03) -> MarketSnapshot:
    curves = CurveSet(
        {CurveKey(CurveRole.DISCOUNT, EUR): _disc(r), CurveKey(CurveRole.SURVIVAL, ACME): surv}
    )
    return MarketSnapshot(VAL, curves, scalars={RecoveryKey(ACME): recovery})


def _cds(spread: float, years: int = 5) -> CDS:
    sched = build_schedule(
        VAL, VAL + Tenor(years, Y),
        ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)),
    )
    return CDS(ACME, PremiumLeg(sched, DC360, spread), Money(NOTIONAL, EUR))


def _bootstrapped(market: MarketSnapshot, spreads: dict[int, float]):
    quotes = tuple(CdsParQuote(VAL + Tenor(y, Y), s) for y, s in sorted(spreads.items()))
    out = bootstrap_survival_curve(
        CreditBootstrapSpec(ACME, EUR, quotes, market, SolveConfig(tolerance=1e-14))
    )
    assert not isinstance(out, CalibrationFailure), out
    return out[0]


# ── THE POINT OF THE SLICE: one source, so the divergence cannot be written ────────────────
def test_the_product_cannot_carry_a_recovery_that_differs_from_the_curve_s() -> None:
    """Before this slice a CDS took its own `recovery`, so a mark could use a different R from the
    one its curve was bootstrapped under — a par quote then priced to ~96bp of notional. The field
    is gone: there is one R, in the snapshot, and both stages read it."""
    assert "recovery" not in CDS.__dataclass_fields__
    assert "recovery" not in CreditBootstrapSpec.__dataclass_fields__


def test_every_par_quote_marks_to_zero_because_one_R_feeds_both_stages() -> None:
    """The one-source par-to-zero: bootstrap and mark now read the SAME `scalars[RecoveryKey]`, so
    the two-R divergence is not merely absent — it is unrepresentable."""
    spreads = {1: 0.0080, 3: 0.0105, 5: 0.0130, 7: 0.0150, 10: 0.0165}
    for recovery in (0.20, 0.40, 0.60):
        base = _snap(recovery, DiscountCurve.flat(TM, 0.03, until=FAR))
        curve = _bootstrapped(base, spreads)
        market = _snap(recovery, curve)
        for years, spread in sorted(spreads.items()):
            out = price(_cds(spread, years), DiscountingModel(market), NUMERICS)
            assert isinstance(out, PricingResult), (recovery, years, out)
            assert abs(out.pv.amount) < 1e-6 * NOTIONAL, (recovery, years, out.pv.amount)


def test_a_missing_recovery_is_a_failure_not_an_assumed_forty_percent() -> None:
    """R=0.40 is the market convention, which is exactly why assuming it silently would be the
    hidden default invariant 5 forbids — it would look right in every standard case."""
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, EUR): _disc(),
            CurveKey(CurveRole.SURVIVAL, ACME): DiscountCurve.flat(TM, 0.03, until=FAR),
        }
    )
    out = price(_cds(0.0180), DiscountingModel(MarketSnapshot(VAL, curves)), NUMERICS)
    assert isinstance(out, PricingFailure), out
    assert "recovery" in out.reason.lower()


def test_recovery_is_validated_at_the_snapshot_boundary() -> None:
    surv = DiscountCurve.flat(TM, 0.03, until=FAR)
    for bad in (1.0, 1.5, -0.1):
        with pytest.raises(ValueError):
            MarketSnapshot(
                VAL,
                CurveSet({CurveKey(CurveRole.DISCOUNT, EUR): _disc()}),
                scalars={RecoveryKey(ACME): bad},
            )


# ── rec01: analytic ∂PV/∂R vs the bump-reprice ─────────────────────────────────────────────
def test_rec01_matches_the_analytic_derivative_in_recovery() -> None:
    """The protection leg is **linear in (1−R)** and the premium leg does not involve R at all, so
    `∂PV/∂R = −protection/(1−R)` exactly. An FD that disagreed would mean the bump is not reaching
    the same R the mark uses."""
    lam, r, years, R = 0.03, 0.03, 5, 0.40
    market = _snap(R, DiscountCurve.flat(TM, 0.03, until=FAR).__class__.flat(TM, 0.03, until=FAR))
    from pricebook.market.survival_curve import SurvivalCurve

    market = _snap(R, SurvivalCurve.flat_hazard(TM, lam, until=FAR), r)
    for spread in (0.0050, 0.0180, 0.0300):
        k = r + lam
        T = TM.year_fraction(VAL + Tenor(years, Y))
        protection = (1.0 - R) * lam / k * (1.0 - math.exp(-k * T))
        expected = -NOTIONAL * protection / (1.0 - R) * BP     # per 1bp of recovery
        got = rec01(priceable(_cds(spread, years), DiscountingModel, NUMERICS), market, ACME)
        assert not isinstance(got, PricingFailure), got
        assert abs(got - expected) < 0.02 * abs(expected), (spread, got, expected)


def test_rec01_is_independent_of_the_spread_because_only_protection_carries_R() -> None:
    """A structural fact, not a number: the premium leg has no R, so `∂PV/∂R` is the same for every
    spread on the same curve. If rec01 varied with the spread, R would be leaking into the annuity."""
    from pricebook.market.survival_curve import SurvivalCurve

    market = _snap(0.40, SurvivalCurve.flat_hazard(TM, 0.03, until=FAR))
    values = [
        rec01(priceable(_cds(s), DiscountingModel, NUMERICS), market, ACME)
        for s in (0.0050, 0.0180, 0.0300)
    ]
    assert all(not isinstance(v, PricingFailure) for v in values)
    assert max(values) - min(values) < 1e-9


def test_rec01_is_negative_for_bought_protection() -> None:
    """Higher recovery means less is paid out on default, so bought protection is worth less."""
    from pricebook.market.survival_curve import SurvivalCurve

    market = _snap(0.40, SurvivalCurve.flat_hazard(TM, 0.03, until=FAR))
    got = rec01(priceable(_cds(0.0180), DiscountingModel, NUMERICS), market, ACME)
    assert not isinstance(got, PricingFailure)
    assert got < 0.0


def test_rec01_without_a_recovery_scalar_is_a_failure_value() -> None:
    from pricebook.market.survival_curve import SurvivalCurve

    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, EUR): _disc(),
            CurveKey(CurveRole.SURVIVAL, ACME): SurvivalCurve.flat_hazard(TM, 0.03, until=FAR),
        }
    )
    out = rec01(
        priceable(_cds(0.0180), DiscountingModel, NUMERICS), MarketSnapshot(VAL, curves), ACME
    )
    assert isinstance(out, PricingFailure), out
