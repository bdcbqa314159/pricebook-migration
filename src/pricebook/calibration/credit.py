"""The survival-curve bootstrap from par CDS spreads (L3).

**Pure composition over the credit atoms**, exactly as the discount bootstrap composes `rpv01`:
for each quoted maturity in ascending order, solve the pillar's survival probability so that the
CDS struck at the quoted par spread has zero value —

    residual(Q_pillar) = protection_leg(...) − spread · risky_annuity(...)

and the atoms are `market/building_blocks.py`'s, **the same two the slice-2 CDS engine will price
with** (§3d). That is the point of building them here rather than inline: if the fit rolled its own
credit annuity, the calibrator would make each CDS par while the engine marked it non-zero, and
par-spread-to-zero could not see it — it telescopes, precisely as the par-swap repricing test did
for rates. The structural oracle is therefore a **count** (N quotes → N pillars), not a reprice.

Sequential, not simultaneous: pillar *i* depends only on pillars `< i` because a CDS maturing at
`tᵢ` has no cashflow beyond it, so the Jacobian is triangular and each pillar is a 1-D monotone
solve. (The simultaneous form the rates curves use buys nothing here and would hide that.)

Provenance:
  quarry: quarry/pricebook/credit/cds.py (`bootstrap_credit_curve`, `premium_leg_pv`,
          `protection_leg_pv` — the conventions are mined; the shape is not, per §4)
  source: O'Kane (2008) Ch. 6; ISDA Standard CDS Model (piecewise-flat hazard, par-spread fit)
  oracle: flat-hazard closed form vs the analytic integral; par-spread-to-zero on every quote;
          N quotes → N pillars with a failed pillar as a CalibrationFailure value
  slice:  credit-survival-bootstrap (B6 slice 1)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, CalibrationResult, SolveConfig
from pricebook.foundation import (
    Accrual,
    DayCountConvention,
    Frequency,
    RollRule,
    ScheduleTerms,
    build_schedule,
)
from pricebook.foundation.money import Currency
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.foundation.solvers import invert_increasing
from pricebook.market.building_blocks import ProtectionWindow, protection_leg, risky_annuity
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.survival_curve import SurvivalCurve

#: Market-standard CDS premium conventions. Quarterly ACT/360 is the ISDA standard; they are stated
#: here (not guessed per-call) and travel to the slice-2 product, which will carry its own.
_PREMIUM_FREQUENCY = Frequency.QUARTERLY
_PREMIUM_DAY_COUNT = DayCountConvention.ACT_360
#: Starting upper bracket and declared ceiling for the per-segment hazard solve. 5% is a typical
#: investment-grade hazard (so the bracket usually straddles at once); 500% is the distressed
#: ceiling past which the quote is rejected rather than answered with a mid-bracket value.
_HAZARD_GUESS = 0.05
_HAZARD_CAP = 5.0


@dataclass(frozen=True)
class CdsParQuote:
    """A par CDS quote: the `spread` (annualised, e.g. 0.01 = 100bp) at which a CDS to `maturity`
    has zero value. Upfront-quoted conventions convert to this before calibrating."""

    maturity: date
    spread: float


@dataclass(frozen=True)
class CreditBootstrapSpec:
    """What to fit: the `entity` the curve is keyed by, its par `quotes` (ascending maturities), the
    `currency` the CDS discounts in, the `market` snapshot it calibrates against, and the `solve`
    config.

    **Recovery is read from the market, not passed here** (slice 4): it is L1 state (§3c), and the
    CDS mark reads the same `scalars[RecoveryKey(entity)]`, so the fit and the price cannot use
    different R's. They could before, and a par quote then marked to ≈96bp of notional silently."""

    entity: ReferenceEntity
    currency: Currency
    quotes: tuple[CdsParQuote, ...]
    market: MarketSnapshot
    solve: SolveConfig = field(default_factory=SolveConfig)


def bootstrap_survival_curve(
    spec: CreditBootstrapSpec,
) -> tuple[SurvivalCurve, CalibrationResult] | CalibrationFailure:
    """Fit one survival pillar per par CDS quote, ascending. Returns the curve beside a
    `CalibrationResult` carrying **one residual per quote**, or a `CalibrationFailure` naming the
    pillar that could not be fitted — never a silently shortened curve (§6 floor rule; the
    swaption-cube lesson)."""
    if not spec.quotes:
        return CalibrationFailure("credit bootstrap needs at least one par CDS quote")
    maturities = [q.maturity for q in spec.quotes]
    if any(b <= a for a, b in zip(maturities, maturities[1:])):
        return CalibrationFailure("par CDS quotes must have strictly ascending maturities")

    try:
        recovery = spec.market.recovery(spec.entity)
        discount = spec.market.curves.discount(spec.currency)
    except KeyError as exc:
        return CalibrationFailure(str(exc))
    measure = getattr(discount, "time_measure", None)
    if measure is None:
        return CalibrationFailure("the discount curve does not expose a time measure to share")
    valuation = measure.anchor
    if maturities[0] <= valuation:
        return CalibrationFailure(f"the first CDS maturity {maturities[0]} is not after valuation")

    times: list[float] = [0.0]
    survivals: list[float] = [1.0]
    residuals: list[float] = []

    for q in spec.quotes:
        t = measure.year_fraction(q.maturity)
        schedule = build_schedule(
            valuation, q.maturity,
            ScheduleTerms(frequency=_PREMIUM_FREQUENCY, roll=RollRule(calendar=None)),
        )
        window = ProtectionWindow(valuation, q.maturity)

        def value(q_pillar: float, _t: float = t, _q: CdsParQuote = q, _s=schedule, _w=window) -> float:
            """CDS value at the trial pillar. Increasing in `−log Q`, so the solve is monotone:
            a lower Q means more default probability, so more protection and less premium."""
            trial = SurvivalCurve(measure, (*times, _t), (*survivals, q_pillar))
            prot = protection_leg(_w, recovery, discount, trial)
            prem = _q.spread * risky_annuity(_s, _PREMIUM_DAY_COUNT, discount, trial)
            return prot - prem

        lo = survivals[-1]                       # Q cannot rise: the previous pillar is the ceiling
        try:
            # solve in x = −log(Q/Q_prev) ≥ 0 (the segment's hazard × dt), which is INCREASING in
            # the CDS value — so the shared monotone inverter applies (§7bb, one search definition)
            dt = t - times[-1]
            if dt <= 0.0:
                return CalibrationFailure(f"pillar {q.maturity.isoformat()}: non-positive segment")
            # solve for the segment HAZARD h >= 0: the CDS value is increasing in h (more default
            # probability ⇒ more protection and less premium), so the shared monotone inverter
            # applies — one search definition in the tree (§7bb), with its expanding upper bracket
            x = invert_increasing(
                lambda h, _v=value, _lo=lo, _dt=dt: _v(_lo * math.exp(-h * _dt)),
                0.0,            # target: a par CDS is worth zero
                0.0,            # lo: a non-negative hazard
                _HAZARD_GUESS,  # hi: doubled until it straddles
                _HAZARD_CAP,    # cap: a declared ceiling, never a silent mid-bracket answer
            )
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            return CalibrationFailure(f"pillar {q.maturity.isoformat()}: {exc}")

        q_fitted = lo * math.exp(-x * dt)
        if not 0.0 < q_fitted <= lo:
            return CalibrationFailure(
                f"pillar {q.maturity.isoformat()}: fitted survival {q_fitted} is not in (0, {lo}] "
                "— the quoted spread implies a negative hazard over this segment"
            )
        # the residual is read BEFORE the pillar is appended: `value` builds its trial curve as
        # (*times, t), so appending first would duplicate t and the curve guard would fire
        residuals.append(value(q_fitted))
        times.append(t)
        survivals.append(q_fitted)

    try:
        curve = SurvivalCurve(measure, tuple(times), tuple(survivals))
    except ValueError as exc:
        return CalibrationFailure(f"the bootstrapped curve is not a valid survival curve: {exc}")
    return curve, CalibrationResult(tuple(residuals), converged=True, jacobian=None)

