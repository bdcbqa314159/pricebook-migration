"""Vanilla-credit-complete — jump-to-default, and Cowork's bump-consistency gate
(`rulings_CP_credit_vertical.md` §5).

Two new oracle ideas here:

* **JTD against closed form.** Jump-to-default is the *defining* credit risk and it is not a
  derivative: it is the PV change if the entity defaults **right now**, which is a discrete event.
  For bought protection the holder receives `(1−R)·N`, stops paying premium, and owes the premium
  accrued to today — so `JTD = (1−R)·N − accrued − PV`. Closed form, no bump.

* **Bump consistency (the gate Cowork derived from the two-R bug).** *For any market input a model
  both fits and prices with, bumping it at its snapshot home must preserve reprice-to-par.* A second
  home fails this: the bump moves the snapshot copy, the mark reads the other copy, and par breaks.
  It is a third structural face beside count and finer-grid/parity, and it is the gate that would
  have caught the ≈96bp two-R divergence that only a human reading a report caught.
"""

import math
from datetime import date

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
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.models.discounting_model import DiscountingModel
from pricebook.products.credit import CDS, PremiumLeg
from pricebook.risk.credit import jump_to_default
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


def _disc(r: float = 0.03) -> DiscountCurve:
    return DiscountCurve.flat(TM, r, until=FAR)


def _market(surv, recovery: float = RECOVERY, r: float = 0.03) -> MarketSnapshot:
    curves = CurveSet(
        {CurveKey(CurveRole.DISCOUNT, EUR): _disc(r), CurveKey(CurveRole.SURVIVAL, ACME): surv}
    )
    return MarketSnapshot(VAL, curves, scalars={RecoveryKey(ACME): recovery})


def _cds(spread: float, years: int = 5, start: date = VAL) -> CDS:
    sched = build_schedule(
        start, start + Tenor(years, Y),
        ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)),
    )
    return CDS(ACME, PremiumLeg(sched, DC360, spread), Money(NOTIONAL, EUR))


# ── jump-to-default ────────────────────────────────────────────────────────────────────────
def test_jtd_is_the_loss_given_default_less_the_current_mark() -> None:
    """`JTD = (1−R)·N − accrued − PV`, in closed form. For an unseasoned CDS there is no accrued,
    so it reduces to `(1−R)·N − PV`."""
    market = _market(SurvivalCurve.flat_hazard(TM, 0.03, until=FAR))
    for spread in (0.0050, 0.0180, 0.0500):
        cds = _cds(spread)
        pv = price(cds, DiscountingModel(market), NUMERICS)
        assert isinstance(pv, PricingResult), pv
        got = jump_to_default(priceable(cds, DiscountingModel, NUMERICS), market, ACME)
        assert not isinstance(got, PricingFailure), got
        expected = (1.0 - RECOVERY) * NOTIONAL - pv.pv.amount
        assert abs(got - expected) < 1e-6, (spread, got, expected)


def test_jtd_subtracts_the_premium_accrued_on_a_seasoned_cds() -> None:
    """Invariant 6 again: on immediate default the protection buyer owes the premium accrued to
    today, so a seasoned CDS's JTD is lower than an identical unseasoned one's by that accrual."""
    market = _market(SurvivalCurve.flat_hazard(TM, 0.03, until=FAR))
    seasoned = _cds(0.0200, 5, start=date(2025, 6, 15))
    pv = price(seasoned, DiscountingModel(market), NUMERICS)
    assert isinstance(pv, PricingResult) and pv.accrued is not None
    got = jump_to_default(priceable(seasoned, DiscountingModel, NUMERICS), market, ACME)
    assert not isinstance(got, PricingFailure), got
    # accrued is NEGATIVE for bought protection (the buyer owes it), so it subtracts twice over
    expected = (1.0 - RECOVERY) * NOTIONAL + pv.accrued.amount - pv.pv.amount
    assert abs(got - expected) < 1e-6, (got, expected)


def test_jtd_is_the_LGD_less_the_mark_so_an_in_the_money_cds_has_less_left_to_jump() -> None:
    """The structural content of `JTD = (1−R)·N − PV`, stated as a relationship rather than a
    magnitude band: a CDS already marked UP has *less* left to gain on default, and one marked down
    has more. (My first attempt asserted `JTD < LGD`, which is false at a near-par spread: the PV is
    then slightly negative, so JTD sits just above the LGD. The relationship holds at every spread;
    the band did not.)"""
    market = _market(SurvivalCurve.flat_hazard(TM, 0.03, until=FAR))
    lgd = (1.0 - RECOVERY) * NOTIONAL
    rows = []
    for spread in (0.0050, 0.0180, 0.0500):     # tight (ITM) → par → wide (OTM) for the buyer
        cds = _cds(spread)
        pv = price(cds, DiscountingModel(market), NUMERICS)
        jtd = jump_to_default(priceable(cds, DiscountingModel, NUMERICS), market, ACME)
        assert isinstance(pv, PricingResult) and not isinstance(jtd, PricingFailure)
        rows.append((pv.pv.amount, jtd))
        assert jtd > 0.0                                    # bought protection always gains
        assert abs(jtd - (lgd - pv.pv.amount)) < 1e-6       # the identity itself

    # monotone: as the mark falls across the three, the jump rises by exactly the same amount
    (pv0, j0), (pv1, j1), (pv2, j2) = rows
    assert pv0 > pv1 > pv2
    assert j0 < j1 < j2
    assert abs((j2 - j0) - (pv0 - pv2)) < 1e-6


def test_jtd_flips_sign_with_the_notional() -> None:
    market = _market(SurvivalCurve.flat_hazard(TM, 0.03, until=FAR))
    bought = _cds(0.0180)
    sold = CDS(bought.entity, bought.premium, Money(-NOTIONAL, EUR))
    b = jump_to_default(priceable(bought, DiscountingModel, NUMERICS), market, ACME)
    s = jump_to_default(priceable(sold, DiscountingModel, NUMERICS), market, ACME)
    assert not isinstance(b, PricingFailure) and not isinstance(s, PricingFailure)
    assert abs(b + s) < 1e-6


def test_jtd_rises_as_recovery_falls() -> None:
    """Less recovered on default means a bigger jump — the monotonicity a sign check alone misses."""
    values = [
        jump_to_default(
            priceable(_cds(0.0180), DiscountingModel, NUMERICS),
            _market(SurvivalCurve.flat_hazard(TM, 0.03, until=FAR), recovery=R),
            ACME,
        )
        for R in (0.60, 0.40, 0.20)
    ]
    assert all(not isinstance(v, PricingFailure) for v in values)
    assert values == sorted(values)


def test_jtd_without_a_recovery_is_a_failure_value() -> None:
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, EUR): _disc(),
            CurveKey(CurveRole.SURVIVAL, ACME): SurvivalCurve.flat_hazard(TM, 0.03, until=FAR),
        }
    )
    out = jump_to_default(
        priceable(_cds(0.0180), DiscountingModel, NUMERICS), MarketSnapshot(VAL, curves), ACME
    )
    assert isinstance(out, PricingFailure), out


# ── THE BUMP-CONSISTENCY GATE (Cowork's third structural face) ─────────────────────────────
SPREADS = {1: 0.0080, 3: 0.0105, 5: 0.0130, 7: 0.0150, 10: 0.0165}


def _bootstrap(market: MarketSnapshot):
    quotes = tuple(CdsParQuote(VAL + Tenor(y, Y), s) for y, s in sorted(SPREADS.items()))
    out = bootstrap_survival_curve(
        CreditBootstrapSpec(ACME, EUR, quotes, market, SolveConfig(tolerance=1e-14))
    )
    assert not isinstance(out, CalibrationFailure), out
    return out[0]


def test_bumping_recovery_at_its_snapshot_home_PRESERVES_reprice_to_par() -> None:
    """**The gate the two-R bug needed.** Bump the recovery at its snapshot home, re-fit, and every
    par quote must still mark to zero — because the *same* bumped scalar feeds the fit and the mark.

    A second home (the old `CDS.recovery`) fails this by construction: the bump moves the snapshot
    copy, the mark reads the product copy, and par breaks by the ≈96bp the slice-4 measurement found.
    So this test is not "recovery works" — it is *there is one home*, expressed as a number."""
    base = MarketSnapshot(
        VAL, CurveSet({CurveKey(CurveRole.DISCOUNT, EUR): _disc()}),
        scalars={RecoveryKey(ACME): RECOVERY},
    )
    for shift in (-0.10, -0.01, 0.0, 0.01, 0.10):
        bumped_base = MarketSnapshot(
            VAL, base.curves, scalars={RecoveryKey(ACME): RECOVERY + shift}
        )
        curve = _bootstrap(bumped_base)
        market = _market(curve, recovery=RECOVERY + shift)
        for years, spread in sorted(SPREADS.items()):
            out = price(_cds(spread, years), DiscountingModel(market), NUMERICS)
            assert isinstance(out, PricingResult), (shift, years, out)
            assert abs(out.pv.amount) < 1e-6 * NOTIONAL, (shift, years, out.pv.amount)


def test_bumping_the_survival_curve_at_its_home_also_preserves_the_identity() -> None:
    """The same gate on the other shared input: a hazard bump re-fitted reprices to par, because the
    curve the mark reads IS the curve the fit produced — one home, reached through the model."""
    base = MarketSnapshot(
        VAL, CurveSet({CurveKey(CurveRole.DISCOUNT, EUR): _disc()}),
        scalars={RecoveryKey(ACME): RECOVERY},
    )
    curve = _bootstrap(base)
    for shift in (-10e-4, 0.0, 25e-4):
        market = _market(curve.bumped(shift))
        # re-derive the par spread the bumped curve implies, then mark AT it: still zero
        from pricebook.market.building_blocks import protection_leg, risky_annuity
        from pricebook.market.building_blocks import ProtectionWindow

        for years in sorted(SPREADS):
            maturity = VAL + Tenor(years, Y)
            sched = build_schedule(
                VAL, maturity,
                ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)),
            )
            prot = protection_leg(
                ProtectionWindow(VAL, maturity), RECOVERY, _disc(), market.curves.survival(ACME),
                NUMERICS.steps_per_year,
            )
            ann = risky_annuity(sched, DC360, _disc(), market.curves.survival(ACME))
            par = prot / ann
            out = price(_cds(par, years), DiscountingModel(market), NUMERICS)
            assert isinstance(out, PricingResult), (shift, years, out)
            assert abs(out.pv.amount) < 1e-6 * NOTIONAL, (shift, years, out.pv.amount)


# ── the protection_leg signature: the wrong day count must be UNWRITABLE ───────────────────
def test_protection_leg_takes_a_window_not_an_accrual_so_no_day_count_can_be_passed() -> None:
    """Divergence ① was passing the premium's ACT/360 where the curve's ACT/365F belonged — a
    day_count parameter that was only ever an integration basis. `ProtectionWindow` carries just the
    two dates; the basis comes from the survival curve's own measure, so the wrong call cannot be
    written rather than merely being tested against."""
    import inspect

    from pricebook.market.building_blocks import ProtectionWindow, protection_leg

    assert set(ProtectionWindow.__dataclass_fields__) == {"start", "end"}
    params = inspect.signature(protection_leg).parameters
    assert "day_count" not in params
    assert not any("accrual" in name for name in params)
