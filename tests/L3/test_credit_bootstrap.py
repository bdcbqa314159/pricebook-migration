"""Credit slice 1 — the shared credit atoms and the survival bootstrap
(`spec_credit_B6_slice1.md` §3). Four oracles, highest rung first:

1. **Closed form (rung 1).** Flat hazard λ, flat continuously-compounded rate r, recovery R: the
   protection leg has the exact value `(1−R)·λ/(r+λ)·(1−e^{−(r+λ)T})` and the continuous risky
   annuity `(1−e^{−(r+λ)T})/(r+λ)`, so the par spread tends to `λ(1−R)`. This is a SECOND method —
   an analytic integral, not the discretised sum the atoms compute — so it tests the atoms rather
   than restating them.
2. **Par-spread-to-zero (self-consistency).** Bootstrap a term structure from par quotes; each
   quoted CDS reprices to zero through the SAME atoms the bootstrap fitted with (§3d).
3. **Structural count (§6 floor rule).** N par quotes → N survival pillars. A pillar that cannot be
   fitted is a `CalibrationFailure` value, never a silently dropped node (the cube's lesson).
4. **Convergence.** The discretised protection leg converges to the analytic integral as the
   integration grid refines — the finer-grid cross-check §6's first clause asks for.
"""

import math
from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, SolveConfig
from pricebook.calibration.credit import (
    CdsParQuote,
    CreditBootstrapSpec,
    bootstrap_survival_curve,
)
from pricebook.foundation import (
    Accrual,
    DayCountConvention,
    Frequency,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
)
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.building_blocks import protection_leg, risky_annuity
from pricebook.market.curve import DiscountCurve
from pricebook.market.survival_curve import SurvivalCurve

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
DC360 = DayCountConvention.ACT_360
VAL = date(2026, 1, 15)
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(15, Y)
ACME = ReferenceEntity("ACME")
RECOVERY = 0.40


def _disc(r: float = 0.03) -> DiscountCurve:
    return DiscountCurve.flat(TM, r, until=FAR)


def _surv(lam: float) -> SurvivalCurve:
    return SurvivalCurve.flat_hazard(TM, lam, until=FAR)


def _cds_schedule(years: int):
    end = VAL + Tenor(years, Y)
    return build_schedule(VAL, end, ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)))


# ── ORACLE 1 — closed form, by a SECOND method (analytic integral) ─────────────────────────
def test_protection_leg_matches_the_analytic_flat_hazard_integral() -> None:
    r, lam, years = 0.03, 0.02, 5
    end = VAL + Tenor(years, Y)
    T = TM.year_fraction(end)
    analytic = (1.0 - RECOVERY) * lam / (r + lam) * (1.0 - math.exp(-(r + lam) * T))
    numeric = protection_leg(Accrual(VAL, end, DC365), RECOVERY, _disc(r), _surv(lam), 12)
    assert abs(numeric - analytic) < 5e-6, (numeric, analytic)


def test_the_continuous_par_spread_tends_to_lambda_times_lgd() -> None:
    """s = protection / annuity → λ(1−R) in the continuous limit. The classic credit identity."""
    r, lam, years = 0.02, 0.03, 5
    end = VAL + Tenor(years, Y)
    T = TM.year_fraction(end)
    disc, surv = _disc(r), _surv(lam)
    prot = protection_leg(Accrual(VAL, end, DC365), RECOVERY, disc, surv, 12)
    cont_annuity = (1.0 - math.exp(-(r + lam) * T)) / (r + lam)
    assert abs(prot / cont_annuity - lam * (1.0 - RECOVERY)) < 1e-4


def test_risky_annuity_is_survival_weighted_and_below_the_riskless_one() -> None:
    from pricebook.market.building_blocks import rpv01

    sched = _cds_schedule(5)
    disc = _disc(0.03)
    risky = risky_annuity(sched, DC360, disc, _surv(0.03))
    riskless = rpv01(sched, DC360, disc)
    assert 0.0 < risky < riskless           # survival weighting strictly reduces it
    flat_zero = risky_annuity(sched, DC360, disc, _surv(0.0))
    assert abs(flat_zero - riskless) < 1e-12  # λ=0 ⇒ the credit annuity IS rpv01


# ── ORACLE 4 — the discretisation's accuracy, and its day-granularity FLOOR ───────────────
def test_protection_leg_is_accurate_across_grids_and_best_near_monthly() -> None:
    """The midpoint rule converges quadratically until it meets a floor that refinement cannot
    remove: `CurveHandle.df` takes a **date**, so at daily steps the midpoint of a one-day step
    floors to that step's start and `df` is read half a day early at every step. Measured against
    the analytic integral, error is 1.6e-5 at n=1, 2.1e-6 at n=12, then *rises* to 5.1e-6 by n=365.
    So the oracle asserts (a) every grid is accurate to 2e-5, (b) the default n=12 beats both the
    coarsest and the finest — which is why 12 is the default, on measurement not convention."""
    r, lam, years = 0.03, 0.05, 5
    end = VAL + Tenor(years, Y)
    T = TM.year_fraction(end)
    analytic = (1.0 - RECOVERY) * lam / (r + lam) * (1.0 - math.exp(-(r + lam) * T))
    acc, disc, surv = Accrual(VAL, end, DC365), _disc(r), _surv(lam)
    err = {n: abs(protection_leg(acc, RECOVERY, disc, surv, n) - analytic) for n in (1, 12, 365)}
    assert max(err.values()) < 2e-5, err
    assert err[12] < err[1] and err[12] < err[365], err   # the floor, asserted not assumed
    assert err[12] < 5e-6, err


# ── ORACLE 2 — par-spread-to-zero through the SAME atoms (§3d) ─────────────────────────────
def _quotes(spreads: dict[int, float]) -> tuple[CdsParQuote, ...]:
    return tuple(CdsParQuote(VAL + Tenor(y, Y), s) for y, s in sorted(spreads.items()))


def _spec(spreads: dict[int, float], r: float = 0.03) -> CreditBootstrapSpec:
    return CreditBootstrapSpec(ACME, _quotes(spreads), _disc(r), RECOVERY, SolveConfig(tolerance=1e-14))


def test_every_quoted_cds_reprices_to_zero_on_the_bootstrapped_curve() -> None:
    spec = _spec({1: 0.0080, 3: 0.0105, 5: 0.0130, 7: 0.0150, 10: 0.0165})
    out = bootstrap_survival_curve(spec)
    assert not isinstance(out, CalibrationFailure), out
    curve, _result = out
    for q in spec.quotes:
        sched = build_schedule(VAL, q.maturity, ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)))
        prot = protection_leg(Accrual(VAL, q.maturity, DC365), spec.recovery, spec.discount, curve)
        prem = q.spread * risky_annuity(sched, DC360, spec.discount, curve)
        assert abs(prot - prem) < 1e-9, (q.maturity, prot, prem)


def test_a_flat_spread_curve_bootstraps_to_a_near_flat_hazard() -> None:
    """Sanity with a known shape: s(t) flat ⇒ λ(t) flat to within the LGD scaling."""
    out = bootstrap_survival_curve(_spec({1: 0.012, 3: 0.012, 5: 0.012, 10: 0.012}))
    assert not isinstance(out, CalibrationFailure), out
    curve, _ = out
    hazards = [curve.hazard(VAL + Tenor(y, Y)) for y in (1, 3, 5, 10)]
    assert max(hazards) - min(hazards) < 5e-4
    assert abs(sum(hazards) / len(hazards) - 0.012 / (1 - RECOVERY)) < 2e-3


# ── ORACLE 3 — STRUCTURAL: N quotes → N pillars, no silent drop ────────────────────────────
def test_n_par_quotes_yield_n_survival_pillars() -> None:
    spreads = {1: 0.008, 2: 0.009, 3: 0.0105, 5: 0.013, 7: 0.015, 10: 0.0165}
    out = bootstrap_survival_curve(_spec(spreads))
    assert not isinstance(out, CalibrationFailure), out
    curve, result = out
    assert len(curve.times) == len(spreads) + 1      # +1 for the t=0 anchor Q=1
    assert len(result.residuals) == len(spreads)     # one residual per quote, floored
    assert curve.times[0] == 0.0


def test_an_unfittable_pillar_is_a_failure_VALUE_not_a_dropped_node() -> None:
    """An inverted spread curve steep enough to need negative hazard cannot be fitted — it must
    come back as a CalibrationFailure naming the pillar, never a short curve."""
    out = bootstrap_survival_curve(_spec({1: 0.030, 3: 0.0005}))
    assert isinstance(out, CalibrationFailure), out
    assert "3" in out.reason or "2029" in out.reason


def test_an_empty_quote_set_is_a_failure_not_an_empty_curve() -> None:
    out = bootstrap_survival_curve(_spec({}))
    assert isinstance(out, CalibrationFailure), out


def test_unsorted_or_duplicate_maturities_are_a_failure() -> None:
    dup = (CdsParQuote(VAL + Tenor(3, Y), 0.01), CdsParQuote(VAL + Tenor(3, Y), 0.012))
    out = bootstrap_survival_curve(
        CreditBootstrapSpec(ACME, dup, _disc(), RECOVERY, SolveConfig(tolerance=1e-14))
    )
    assert isinstance(out, CalibrationFailure), out


def test_a_recovery_outside_zero_one_is_a_failure() -> None:
    bad = CreditBootstrapSpec(ACME, _quotes({5: 0.01}), _disc(), 1.5, SolveConfig())
    assert isinstance(bootstrap_survival_curve(bad), CalibrationFailure)
