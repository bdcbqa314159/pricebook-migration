"""Credit slice 2 — the CDS product (L2) and its engine mark (L4) (`spec_credit_slice2.md` §2).

**Oracle 1 is the mandatory one: an OFF-PAR closed-form flat-hazard mark.** A *par* CDS is worth
zero, so a par-only oracle telescopes — exactly as par swaps did for rates and as the cap strip did
for audit #10 — and a divergent premium annuity would be invisible. Off par, `PV ≠ 0` and the
annuity appears with full weight, so the closed form bites.

Under a flat hazard λ, flat continuously-compounded rate r and recovery R, over `[0, T]`:

    protection = (1−R)·λ/(r+λ)·(1 − e^{−(r+λ)T})
    annuity    = (1 − e^{−(r+λ)T})/(r+λ)                (continuous premium limit)
    PV(bought) = protection − s·annuity                 (= 0 only when s = λ(1−R))

The engine's discrete annuity is quarterly with accrual-on-default, so the comparison is to a
tolerance sized by the discretisation — not `==` (§7c).
"""

import math
from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, SolveConfig
from pricebook.calibration.credit import (
    CdsParQuote,
    CreditBootstrapSpec,
    bootstrap_survival_curve,
)
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
)
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.models.discounting_model import DiscountingModel
from pricebook.products.credit import CDS, PremiumLeg

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
DC360 = DayCountConvention.ACT_360
VAL = date(2026, 1, 15)
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(15, Y)
ACME = ReferenceEntity("ACME")
CCY = None  # filled from Money below
RECOVERY = 0.40
NOTIONAL = 10_000_000.0
NUMERICS = IntegrationConfig(steps_per_year=12)


def _ccy():
    from pricebook.foundation import get_currency

    return get_currency("EUR")


def _model(lam: float, r: float = 0.03) -> DiscountingModel:
    disc = DiscountCurve.flat(TM, r, until=FAR)
    surv = SurvivalCurve.flat_hazard(TM, lam, until=FAR)
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, _ccy()): disc,
            CurveKey(CurveRole.SURVIVAL, ACME): surv,
        }
    )
    return DiscountingModel(MarketSnapshot(VAL, curves))


def _cds(spread: float, years: int = 5, start: date = VAL) -> CDS:
    sched = build_schedule(
        start, start + Tenor(years, Y),
        ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)),
    )
    return CDS(ACME, PremiumLeg(sched, DC360, spread), RECOVERY, Money(NOTIONAL, _ccy()))


def _analytic_pv(spread: float, lam: float, r: float, years: int) -> float:
    T = TM.year_fraction(VAL + Tenor(years, Y))
    k = r + lam
    protection = (1.0 - RECOVERY) * lam / k * (1.0 - math.exp(-k * T))
    annuity = (1.0 - math.exp(-k * T)) / k
    return NOTIONAL * (protection - spread * annuity)


# ── ORACLE 1 — OFF-PAR closed form (the mandatory non-telescoping oracle) ──────────────────
def test_off_par_cds_mark_matches_the_analytic_flat_hazard_pv() -> None:
    lam, r, years = 0.03, 0.03, 5
    par = lam * (1.0 - RECOVERY)          # ≈ 180bp
    for spread in (0.0050, 0.0100, par, 0.0300, 0.0500):
        out = price(_cds(spread, years), _model(lam, r), NUMERICS)
        assert isinstance(out, PricingResult), out
        expected = _analytic_pv(spread, lam, r, years)
        assert abs(out.pv.amount - expected) < 0.004 * NOTIONAL / 100, (spread, out.pv.amount, expected)


def test_the_mark_is_non_zero_off_par_so_the_oracle_cannot_telescope() -> None:
    """The point of oracle 1: a par CDS is worth zero, so only off par does the annuity carry
    weight. Assert the PVs actually differ and bracket zero."""
    lam = 0.03
    par = lam * (1.0 - RECOVERY)
    tight = price(_cds(par - 0.0100), _model(lam), NUMERICS)
    wide = price(_cds(par + 0.0100), _model(lam), NUMERICS)
    assert isinstance(tight, PricingResult) and isinstance(wide, PricingResult)
    assert tight.pv.amount > 0.01 * NOTIONAL / 100   # bought protection cheap ⇒ positive
    assert wide.pv.amount < -0.01 * NOTIONAL / 100   # overpaying ⇒ negative
    assert tight.pv.amount > 0.0 > wide.pv.amount


def test_a_cds_struck_at_the_continuous_par_spread_is_near_zero() -> None:
    lam = 0.03
    out = price(_cds(lam * (1.0 - RECOVERY)), _model(lam), NUMERICS)
    assert isinstance(out, PricingResult), out
    assert abs(out.pv.amount) < 0.03 * NOTIONAL / 100   # within ~3bp of notional


# ── ORACLE 3 — the §3d identity: the engine's par spread IS the bootstrap's input ──────────
def test_the_engine_prices_every_bootstrapped_pillar_to_zero() -> None:
    """Calibrate and price are one fact, because both compose the SAME two atoms (§3d). If the
    engine rolled its own annuity, each quote would calibrate and then mark non-zero."""
    spreads = {1: 0.0080, 3: 0.0105, 5: 0.0130, 7: 0.0150, 10: 0.0165}
    disc = DiscountCurve.flat(TM, 0.03, until=FAR)
    quotes = tuple(CdsParQuote(VAL + Tenor(y, Y), s) for y, s in sorted(spreads.items()))
    out = bootstrap_survival_curve(
        CreditBootstrapSpec(ACME, quotes, disc, RECOVERY, SolveConfig(tolerance=1e-14))
    )
    assert not isinstance(out, CalibrationFailure), out
    curve, _ = out
    curves = CurveSet(
        {CurveKey(CurveRole.DISCOUNT, _ccy()): disc, CurveKey(CurveRole.SURVIVAL, ACME): curve}
    )
    model = DiscountingModel(MarketSnapshot(VAL, curves))
    for years, spread in sorted(spreads.items()):
        res = price(_cds(spread, years), model, NUMERICS)
        assert isinstance(res, PricingResult), (years, res)
        assert abs(res.pv.amount) < 1e-6 * NOTIONAL, (years, res.pv.amount)


# ── ORACLE 4 — invariant 6: the seasoned decomposition ─────────────────────────────────────
def test_a_seasoned_cds_carries_accrued_and_excludes_historical_premium() -> None:
    """A CDS whose premium period is in progress: `pv` is dirty, `accrued` is the earned-but-unpaid
    premium, `clean = pv − accrued`, and periods that already paid are excluded (invariant 6)."""
    lam, spread = 0.03, 0.0200
    started = VAL - Tenor(7, TenorUnit.MONTH)          # two quarters already paid, one in progress
    out = price(_cds(spread, 5, start=started), _model(lam), NUMERICS)
    assert isinstance(out, PricingResult), out
    assert out.accrued is not None
    assert out.accrued.amount < 0.0                    # the protection BUYER owes premium
    assert abs(out.clean.amount - (out.pv.amount - out.accrued.amount)) < 1e-9


def test_an_unseasoned_cds_has_no_accrued() -> None:
    out = price(_cds(0.0200), _model(0.03), NUMERICS)
    assert isinstance(out, PricingResult), out
    assert out.accrued is None or abs(out.accrued.amount) < 1e-9


# ── invariant 5: the integration config is explicit, never a hidden default ────────────────
def test_pricing_a_cds_without_an_integration_config_is_a_failure_value() -> None:
    """A guessed grid is a hidden reproducibility knob (invariant 5). Absent ⇒ failure, not 12."""
    out = price(_cds(0.0200), _model(0.03))
    assert isinstance(out, PricingFailure), out
    assert "integration" in out.reason.lower()


def test_the_grid_is_the_knob_the_config_says_it_is() -> None:
    coarse = price(_cds(0.0200), _model(0.03), IntegrationConfig(steps_per_year=1))
    fine = price(_cds(0.0200), _model(0.03), IntegrationConfig(steps_per_year=12))
    assert isinstance(coarse, PricingResult) and isinstance(fine, PricingResult)
    assert coarse.pv.amount != fine.pv.amount          # the knob is live, not ignored


# ── failure values, never silent wrongness ─────────────────────────────────────────────────
def test_a_missing_survival_curve_is_a_failure_not_a_risk_free_mark() -> None:
    disc = DiscountCurve.flat(TM, 0.03, until=FAR)
    model = DiscountingModel(
        MarketSnapshot(VAL, CurveSet({CurveKey(CurveRole.DISCOUNT, _ccy()): disc}))
    )
    out = price(_cds(0.0200), model, NUMERICS)
    assert isinstance(out, PricingFailure), out


def test_an_expired_cds_has_no_remaining_value() -> None:
    expired = _cds(0.0200, 1, start=VAL - Tenor(3, Y))
    out = price(expired, _model(0.03), NUMERICS)
    assert isinstance(out, PricingResult), out
    assert abs(out.pv.amount) < 1e-9


def test_cds_validates_its_shape() -> None:
    import pytest

    sched = build_schedule(
        VAL, VAL + Tenor(5, Y),
        ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)),
    )
    with pytest.raises(ValueError):
        CDS(ACME, PremiumLeg(sched, DC360, 0.01), 1.5, Money(NOTIONAL, _ccy()))   # recovery ≥ 1
    with pytest.raises(ValueError):
        CDS(ACME, PremiumLeg(sched, DC360, -0.01), 0.4, Money(NOTIONAL, _ccy()))  # negative spread


# ── default_prob + the conditional reads forward-linked from slice 1 (needed-now here) ─────
def test_default_prob_is_one_minus_survival() -> None:
    curve = SurvivalCurve.flat_hazard(TM, 0.03, until=FAR)
    d = VAL + Tenor(5, Y)
    assert abs(curve.default_prob(d) - (1.0 - curve.survival(d))) < 1e-15


def test_conditional_survival_chains_multiplicatively() -> None:
    """Q(t2|t1) = Q(t2)/Q(t1) — the Markov property the protection leg's increments rely on."""
    curve = SurvivalCurve.flat_hazard(TM, 0.03, until=FAR)
    d1, d2 = VAL + Tenor(2, Y), VAL + Tenor(7, Y)
    cond = curve.conditional_survival(d1, d2)
    assert abs(cond - curve.survival(d2) / curve.survival(d1)) < 1e-14
    assert abs(curve.survival(d1) * cond - curve.survival(d2)) < 1e-14
