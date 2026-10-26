"""Shared pricing atoms — the building blocks the calibrator AND the engine compose (L1).

CLAUDE.md §3d: an atom is defined ONCE; every stage composes it. `rpv01` (the fixed
annuity, discount only), `forward` (the projection forward rate), and `float_leg_pv`
(which COMPOSES `forward`) live here, below both the L3 calibrator and the L4 engine, so
neither re-derives a discount/annuity/forward loop. Both take the SAME `Schedule` from
the one L2 product, closing the accrual-date-identity axis.

`float_leg_pv` is dual-curve: it discounts on `discount` and projects forwards on
`projection`. Single-curve is the degenerate case — with `projection is discount` and no
pay lag the per-period sum equals the telescoping identity `df(start₀) − df(endₙ)` (to
rounding). There is no separate telescoping code path (that would be a §3d exception).

Provenance:
  quarry: quarry/pricebook/fixed_income/swap.py (annuity / swap PV / forwards)
  source: CLAUDE.md §3d (shared atoms); multicurve leg PV = Σ df_disc·τ·L_proj
  oracle: EURIBOR swap → zero NPV dual-curve; float leg degenerates to df0 − dfN
  slice:  dual-curve-euribor-estr (T1 slice 2)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from pricebook.foundation import (
    Accrual,
    CouponPeriod,
    DayCountConvention,
    Schedule,
    SchedulePeriod,
    icma_coupon_period,
)
from pricebook.market.curve import CurveHandle
from pricebook.market.survival_curve import SurvivalHandle

# A day count that needs convention context beyond the two dates: ICMA needs the coupon frequency,
# BUS/252 needs the calendar. Both are read FROM THE SCHEDULE'S `terms` (§3d — context travels with
# the data), so the calibrator and engine cannot pass mismatched conventions for the same schedule.


def _coupon_context(schedule: Schedule, period: SchedulePeriod, day_count: DayCountConvention, is_first: bool):
    """The `(coupon_period, calendar)` a period needs under `day_count`, from the schedule's own
    `terms`. ICMA builds a `CouponPeriod` (its consumer for `is_stub`); every other convention gets
    `None` — INERT, so a non-ICMA leg is byte-identical (and `per_year()` is never called on a
    non-integer frequency). The calendar comes from the schedule's roll for BOTH legs (one source)."""
    coupon_period: CouponPeriod | None = None
    if day_count is DayCountConvention.ACT_ACT_ICMA:
        coupon_period = icma_coupon_period(
            period.accrual_start,
            period.accrual_end,
            front_stub=period.is_stub and is_first,
            frequency=schedule.terms.frequency.per_year(),
        )
    return coupon_period, schedule.terms.roll.calendar


def rpv01(schedule: Schedule, day_count: DayCountConvention, curve: CurveHandle) -> float:
    """The fixed annuity — RPV01 = Σ τᵢ·df(payᵢ), discount curve only. THIS is the single
    definition of the annuity: the calibrator's `par_rate` and the engine's swap PV both
    call it (§3d), so they cannot disagree on day count or discounting. Each τ reads its
    convention context (ICMA frequency, BUS/252 calendar) from the schedule (§3d)."""
    total = 0.0
    for i, p in enumerate(schedule.periods):
        cp, cal = _coupon_context(schedule, p, day_count, is_first=i == 0)
        tau = Accrual(p.accrual_start, p.accrual_end, day_count).year_fraction(
            coupon_period=cp, calendar=cal
        )
        total += tau * curve.df(p.payment_date)
    return total


def deposit_df(rate: float, accrual: Accrual) -> float:
    """The simple-compounding discount factor over `accrual`: `1/(1 + rate·τ)`. The single
    definition — both the L3 `DepositInstrument.residual` and the L4 deposit pricer compose
    it (§3d), so they cannot disagree."""
    return 1.0 / (1.0 + rate * accrual.year_fraction())


def forward(
    projection: CurveHandle,
    accrual: Accrual,
    *,
    coupon_period: CouponPeriod | None = None,
    calendar=None,
) -> float:
    """The simple forward rate over `accrual`, off the projection curve —
    `(df(start)/df(end) − 1) / τ`. The single definition of the projection atom; the
    float-leg calibrator and the engine both reach it through the same `projection`
    curve. `coupon_period`/`calendar` thread the ICMA/BUS252 context into `τ` (inert for
    other conventions) — the FRA/future calibrators pass none (their accruals are simple)."""
    return (projection.df(accrual.start) / projection.df(accrual.end) - 1.0) / accrual.year_fraction(
        coupon_period=coupon_period, calendar=calendar
    )


def float_leg_pv(
    schedule: Schedule,
    day_count: DayCountConvention,
    discount: CurveHandle,
    projection: CurveHandle,
) -> float:
    """Floating-leg PV (unit notional): Σ df_disc(payᵢ)·τᵢ·forward(proj, accrualᵢ). Composes
    `forward` (never inlines the df ratio, §3d). Degenerate single-curve case
    (`projection is discount`, no lag) equals `df(start₀) − df(endₙ)`."""
    total = 0.0
    for i, p in enumerate(schedule.periods):
        cp, cal = _coupon_context(schedule, p, day_count, is_first=i == 0)
        accrual = Accrual(p.accrual_start, p.accrual_end, day_count)
        tau = accrual.year_fraction(coupon_period=cp, calendar=cal)
        total += discount.df(p.payment_date) * tau * forward(
            projection, accrual, coupon_period=cp, calendar=cal
        )
    return total

# ── credit atoms (B6 slice 1) — the credit `rpv01`, defined ONCE ────────────────────────────
def risky_annuity(
    schedule: Schedule, day_count: DayCountConvention, discount: CurveHandle, survival: SurvivalHandle
) -> float:
    """The **survival-weighted** premium annuity — the credit sibling of `rpv01`, and THE single
    definition of it. The bootstrap composes it to fit (`s = protection / risky_annuity`) and the
    CDS engine composes the same one to price, so they cannot disagree (§3d). This is the annuity
    lesson applied to credit *before* it can bite: if the fit and the price rolled separate credit
    annuities, the calibrator would make each CDS par while the engine marked it non-zero, and a
    par-spread-to-zero oracle would be blind to it (it telescopes, exactly as par swaps do).

        A = Σᵢ τᵢ·df(payᵢ)·Q(payᵢ)                         (premium paid only if still alive)
          + Σᵢ (τᵢ/2)·df(midᵢ)·(Q(startᵢ) − Q(endᵢ))        (accrual on default)

    **The accrual-on-default convention is explicit, not incidental** (the spec requires it stated):
    on default mid-period the protection seller is owed the premium accrued to the default date, and
    this uses the standard **half-period** approximation — default is taken at the period midpoint,
    so the expected accrual is `τ/2` discounted at the midpoint. It is the ISDA Standard CDS Model's
    approximation and the quarry's; a finer within-period integration is deferred to its first
    consumer (a same-day/short-stub CDS, where the half-period assumption is coarsest)."""
    total = 0.0
    for i, p in enumerate(schedule.periods):
        cp, cal = _coupon_context(schedule, p, day_count, is_first=i == 0)
        tau = Accrual(p.accrual_start, p.accrual_end, day_count).year_fraction(
            coupon_period=cp, calendar=cal
        )
        total += tau * discount.df(p.payment_date) * survival.survival(p.payment_date)
        mid = _midpoint(p.accrual_start, p.accrual_end)
        q_default = survival.survival(p.accrual_start) - survival.survival(p.accrual_end)
        total += (tau / 2.0) * discount.df(mid) * q_default
    return total


@dataclass(frozen=True)
class ProtectionWindow:
    """The period a credit protection leg covers — **two dates and nothing else.**

    Deliberately not an `Accrual`: an `Accrual` carries a `day_count`, and for this leg a day count
    is never an accrual convention, only the basis the integral is discretised on. Passing the
    premium leg's ACT/360 where the survival curve's ACT/365F belonged changed the step count and
    made the bootstrap's own par CDS mark non-zero (slice 2, divergence ①). The basis now comes from
    the curve being integrated against (`SurvivalHandle.time_basis`), so the wrong call is
    unwritable rather than merely tested against."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"a protection window must be ordered; got {self.start}..{self.end}")


def protection_leg(
    window: ProtectionWindow,
    recovery: float,
    discount: CurveHandle,
    survival: SurvivalHandle,
    steps_per_year: int = 12,
) -> float:
    """The protection leg per unit notional — THE single definition, composed by both the bootstrap
    and the CDS engine (§3d).

        P = (1−R) · ∫ df(t)·(−dQ(t))  ≈  (1−R) · Σ df(midⱼ)·(Q(tⱼ) − Q(tⱼ₊₁))

    discretised on a uniform grid of `steps_per_year`, with each step's loss discounted at the step
    **midpoint** — default is taken as uniformly distributed within the step, so the midpoint is its
    expected timing. `(Q(tⱼ) − Q(tⱼ₊₁))` is the exact probability of defaulting inside the step, so
    the only approximation is *when* within the step, never *whether*: the sum of the increments is
    `Q(0) − Q(T)` by construction regardless of the grid, which is why refining the grid converges
    rather than rescaling. Under a flat hazard and flat rate it converges to the analytic
    `(1−R)·λ/(r+λ)·(1−e^{−(r+λ)T})`, which is this atom's oracle.

    **`steps_per_year=12` is chosen on measurement, not convention.** Against the analytic integral
    (r=3%, λ=5%, R=40%, T=5Y, value 0.1236851) the absolute error is: n=1 → 1.6e-5, **n=12 → 2.1e-6**,
    n=52 → 4.9e-6, n=365 → 5.1e-6. Refining past ~monthly makes it *worse* and then plateaus, because
    `CurveHandle.df` takes a **date**: at daily steps the midpoint of a one-day step floors to that
    step's start, so `df` is read half a day early at every step — a systematic bias that refinement
    cannot remove, only accumulate. The midpoint rule's own quadratic convergence wins until it meets
    that day-granularity floor, which is at roughly monthly steps. (The quarry defaulted to 12 too;
    the measurement says it was right.) A sub-day-accurate protection leg needs a `df(t: float)`
    capability, deferred to a consumer that can justify widening the protocol.

    `recovery` is explicit, never defaulted: a guessed R silently rescales every credit number
    (invariant 5)."""
    if not 0.0 <= recovery < 1.0:
        raise ValueError(f"recovery must be in [0, 1); got {recovery}")
    if steps_per_year < 1:
        raise ValueError(f"steps_per_year must be positive; got {steps_per_year}")
    # the basis is the CURVE's, never the caller's (see ProtectionWindow)
    years = Accrual(window.start, window.end, survival.time_basis).year_fraction()
    if years <= 0.0:
        return 0.0
    n = max(1, int(round(years * steps_per_year)))
    span = (window.end - window.start).days
    total = 0.0
    for j in range(n):
        d0 = window.start + timedelta(days=int(span * j / n))
        d1 = window.end if j == n - 1 else window.start + timedelta(days=int(span * (j + 1) / n))
        if d1 <= d0:
            continue
        mid = _midpoint(d0, d1)
        total += discount.df(mid) * (survival.survival(d0) - survival.survival(d1))
    return (1.0 - recovery) * total


def _midpoint(start: date, end: date) -> date:
    """The period midpoint — shared by both credit atoms so they cannot disagree on it."""
    return date.fromordinal((start.toordinal() + end.toordinal()) // 2)
