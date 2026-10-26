"""Bump strategies — the per-shape market perturbation risk applies (L5).

The ONLY shape-aware part of the risk layer: a `Bump` knows how to perturb ONE snapshot shape
(a curve, a surface) and return a NEW `MarketSnapshot` (invariant 3 — the base is never mutated).
The finite-difference core is key-TYPE-BLIND; the curve-vs-surface split lives HERE, in polymorphic
`apply`, never as an `isinstance`/`if-elif` in the core (§1 no-isinstance; §3d no type-switch). A
third key kind (FX-spot `ScalarBump`) arrives with its first consumer — a new strategy, not a core edit.

Provenance:
  quarry: quarry/pricebook/risk/ (curve_bumper — design reference only, built on the superseded shape)
  source: CLAUDE.md §1 (no-isinstance) · §2 (invariant 3, no mutation); docs/19 §2 (per-shape keys)
  oracle: bumped market reprices; base snapshot/curve/surface unchanged after the bump
  slice:  risk-greeks (C3 opening)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast
from typing import Protocol, runtime_checkable

from pricebook.market.curve_set import CurveKey, CurveSet
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.snapshot import MarketSnapshot, RecoveryKey
from pricebook.market.survival_curve import SurvivalHandle
from pricebook.market.vol_surface import SurfaceKey, flat_surface


@runtime_checkable
class Bump(Protocol):
    """Perturb one snapshot shape by `shift`, returning a new snapshot (never mutates the base)."""

    def apply(self, market: MarketSnapshot, shift: float) -> MarketSnapshot: ...


@dataclass(frozen=True)
class CurveIdentityBump:
    """Parallel bump by curve IDENTITY (the DEFAULT for `ir_delta`/`book_dv01`). Resolves the curve at
    `key`, bumps it ONCE, and replaces EVERY `CurveSet` entry whose value `is` that curve with the same
    bumped object — so an OIS curve aliased under both `(DISCOUNT, ccy)` and `(PROJECTION, ois_index)`
    moves in BOTH roles at once (bump-once-share). This is the documented parallel interest-rate delta;
    the old single-key bump broke the alias, mis-stating OIS DV01 ~750× (#1). No isinstance/type branch."""

    key: CurveKey

    def apply(self, market: MarketSnapshot, shift: float) -> MarketSnapshot:
        target = market.curves.curves[self.key]
        bumped = target.bumped(shift)  # bump ONCE
        curves = {k: (bumped if v is target else v) for k, v in market.curves.curves.items()}
        return replace(market, curves=CurveSet(curves))


@dataclass(frozen=True)
class CurveBasisBump:
    """Single-key PARTIAL (basis) bump: replace ONLY the entry at `key`, leaving any aliased role
    unmoved — a genuine basis move for a dual-curve swap (discount vs a distinct projection). Reached
    through `ir_basis_delta`, never the default; for an OIS-aliased curve this is a partial derivative,
    not the parallel DV01 (`CurveIdentityBump` is)."""

    key: CurveKey

    def apply(self, market: MarketSnapshot, shift: float) -> MarketSnapshot:
        bumped = market.curves.curves[self.key].bumped(shift)
        return replace(market, curves=market.curves.with_curve(self.key, bumped))


@dataclass(frozen=True)
class SurfaceBump:
    """Parallel-bumps the vol surface at `key` (a flat vega): replace it with `.bumped(shift)`,
    rebuild the snapshot."""

    key: SurfaceKey

    def apply(self, market: MarketSnapshot, shift: float) -> MarketSnapshot:
        # flat vega only; SABR vega (bump α/ρ/ν) is a distinct greek, deferred to its consumer
        bumped = flat_surface(market.surfaces[self.key]).bumped(shift)
        return replace(market, surfaces={**market.surfaces, self.key: bumped})

@dataclass(frozen=True)
class SurvivalBump:
    """Parallel-bumps the survival curve at `key` — every hazard segment moves by `shift`, which is
    the credit-spread bump `cs01` reports. Bumping the HAZARD rather than Q is the slice-1 ruling:
    Q has no units and a Q shift does not stay monotone, whereas a hazard shift does both."""

    key: CurveKey

    def apply(self, market: MarketSnapshot, shift: float) -> MarketSnapshot:
        bumped = market.curves.curves[self.key].bumped(shift)
        return replace(market, curves=market.curves.with_curve(self.key, bumped))


@dataclass(frozen=True)
class SurvivalPillarBump:
    """Bumps ONE hazard segment of the survival curve at `key` — the credit key-rate bump. The
    per-pillar bumps partition the curve's segments, so they sum to `SurvivalBump` up to
    cross-convexity: that identity is the structural oracle for bucketed CS01, not a scalar match."""

    key: CurveKey
    pillar: int

    def apply(self, market: MarketSnapshot, shift: float) -> MarketSnapshot:
        # the key's SURVIVAL role is what guarantees the capability — the same narrowing
        # `CurveSet.survival` performs, kept here rather than inspecting the object (§1)
        curve = cast("SurvivalHandle", market.curves.curves[self.key])
        return replace(market, curves=market.curves.with_curve(self.key, curve.bumped_at(self.pillar, shift)))


@dataclass(frozen=True)
class RecoveryBump:
    """Bumps the recovery rate of one entity in the snapshot's `scalars`.

    This is an ordinary snapshot bump precisely because slice 4 moved recovery to L1 (§3c). While it
    lived on the L2 product there was no way to express it here — risk would have needed a second,
    instrument-mutating bump mechanism beside this one, and a type-switch to choose between them,
    which is what §1 forbids. One home, one mechanism."""

    entity: ReferenceEntity

    def apply(self, market: MarketSnapshot, shift: float) -> MarketSnapshot:
        key = RecoveryKey(self.entity)
        scalars = {**market.scalars, key: market.scalars[key] + shift}
        return replace(market, scalars=scalars)
