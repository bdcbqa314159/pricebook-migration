"""SurvivalCurve — the credit term structure (L1).

`Q(t)` = probability the entity has not defaulted by `t`. Stored as survival probabilities at
pillar times and interpolated **log-linearly**, which is exactly piecewise-constant hazard between
pillars: `Q(t) = Q(tᵢ)·exp(−λᵢ·(t−tᵢ))`. So "log-linear in Q" and "piecewise-flat hazard" are the
same statement, and the curve can answer both `survival` and `hazard` from one representation.

**It is market state, so it lives in the snapshot and risk bumps it** (§3c step 2) — `bumped(shift)`
shifts the HAZARD, not Q, because a hazard shift is the credit-spread bump risk actually applies and
it keeps `Q` monotone by construction. Never mutated in place.

**It is a distinct capability from discounting, so it gets a distinct protocol** (`SurvivalHandle`,
not `CurveHandle`): a survival curve has no `df` and a discount curve has no `survival`, and
widening one protocol to cover both would force every discount curve to answer a credit question.
Same reasoning as `ImpliedVol`/`SwaptionVol` being two model capabilities rather than one.

Provenance:
  quarry: quarry/pricebook/core/survival_curve.py (log-linear Q, piecewise-constant hazard — the
          representation is mined; the class shape is not, per §4 mine-for-content)
  source: O'Kane (2008) "Modelling Single-name and Multi-name Credit Derivatives" Ch. 6; ISDA
          Standard CDS Model (piecewise-flat hazard)
  oracle: flat hazard ⇒ Q(t) = exp(−λt) to 1e-12, and hazard reads back λ; monotone-Q guard
  slice:  credit-survival-bootstrap (B6 slice 1)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from pricebook.foundation.time_measure import TimeMeasure


@runtime_checkable
class SurvivalHandle(Protocol):
    """The survival capability — `Q(d)` and the hazard at a date, plus a bumped copy for risk.
    Depend on this, not the concrete curve (docs/19 §3); credit risk (L5) bumps through it."""

    def survival(self, d: date) -> float: ...

    def hazard(self, d: date) -> float: ...

    def bumped(self, shift: float) -> SurvivalHandle: ...


@dataclass(frozen=True)
class SurvivalCurve:
    """Survival probabilities `survivals` at pillar `times` (ascending, `times[0] == 0.0`,
    `survivals[0] == 1.0`, non-increasing), log-linearly interpolated. `measure` is the single
    `date → t` map the curve and its consumers share (§3d), so the curve's axis and the priced
    time cannot drift apart. A date past the last pillar raises, which the engine turns into a
    `PricingFailure`."""

    measure: TimeMeasure
    times: tuple[float, ...]
    survivals: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.times) != len(self.survivals):
            raise ValueError("SurvivalCurve: times and survivals must have equal length")
        if len(self.times) < 2:
            raise ValueError("SurvivalCurve: needs the t=0 anchor plus at least one pillar")
        if self.times[0] != 0.0 or self.survivals[0] != 1.0:
            raise ValueError(
                f"SurvivalCurve: must be anchored at t=0 with Q=1; got "
                f"t={self.times[0]!r}, Q={self.survivals[0]!r}"
            )
        if any(b <= a for a, b in zip(self.times, self.times[1:])):
            raise ValueError("SurvivalCurve: times must be strictly ascending")
        for q in self.survivals:
            if not 0.0 < q <= 1.0:
                raise ValueError(f"SurvivalCurve: survival probabilities must be in (0, 1]; got {q}")
        if any(b > a for a, b in zip(self.survivals, self.survivals[1:])):
            # a rising Q is a negative hazard — the entity un-defaulting
            raise ValueError("SurvivalCurve: survivals must be non-increasing (Q rising ⇒ negative hazard)")

    @classmethod
    def flat_hazard(cls, measure: TimeMeasure, hazard: float, until: date) -> SurvivalCurve:
        """The degenerate curve credit slices start from: one constant hazard to `until`."""
        if hazard < 0.0:
            raise ValueError(f"a flat hazard must be non-negative; got {hazard}")
        t = measure.year_fraction(until)
        return cls(measure, (0.0, t), (1.0, math.exp(-hazard * t)))

    def survival(self, d: date) -> float:
        """`Q(d)`, log-linear in Q between pillars (= piecewise-constant hazard)."""
        t = self.measure.year_fraction(d)
        if t < 0.0:
            raise ValueError(f"survival before the valuation date is undefined; t={t}")
        if t == 0.0:
            return 1.0
        if t > self.times[-1]:
            raise ValueError(
                f"t={t} is past the last survival pillar {self.times[-1]} "
                "(no extrapolation — the caller fails as a value)"
            )
        i = self._segment(t)
        t0, t1 = self.times[i], self.times[i + 1]
        log0, log1 = math.log(self.survivals[i]), math.log(self.survivals[i + 1])
        return math.exp(log0 + (log1 - log0) * (t - t0) / (t1 - t0))

    def hazard(self, d: date) -> float:
        """The piecewise-constant hazard `λᵢ = −(log Qᵢ₊₁ − log Qᵢ)/(tᵢ₊₁ − tᵢ)` covering `d`."""
        t = self.measure.year_fraction(d)
        if t < 0.0 or t > self.times[-1]:
            raise ValueError(f"t={t} is outside the survival curve's pillars")
        i = self._segment(max(t, 0.0))
        dt = self.times[i + 1] - self.times[i]
        return -(math.log(self.survivals[i + 1]) - math.log(self.survivals[i])) / dt

    def bumped(self, shift: float) -> SurvivalCurve:
        """Shift the HAZARD by `shift` at every pillar — the credit-spread bump. Shifting Q
        directly would not stay monotone and has no units; a hazard shift does both."""
        out = [1.0]
        for i in range(len(self.times) - 1):
            dt = self.times[i + 1] - self.times[i]
            lam = -(math.log(self.survivals[i + 1]) - math.log(self.survivals[i])) / dt
            out.append(out[-1] * math.exp(-max(lam + shift, 0.0) * dt))
        return SurvivalCurve(self.measure, self.times, tuple(out))

    def with_pillar(self, t: float, q: float) -> SurvivalCurve:
        """A copy with one pillar appended — how the bootstrap grows the curve, never in place."""
        return SurvivalCurve(self.measure, (*self.times, t), (*self.survivals, q))

    def _segment(self, t: float) -> int:
        """Index `i` with `times[i] <= t <= times[i+1]`."""
        lo, hi = 0, len(self.times) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self.times[mid] <= t:
                lo = mid
            else:
                hi = mid
        return lo
