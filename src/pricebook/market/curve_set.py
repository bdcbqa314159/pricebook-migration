"""CurveSet — the keyed store of curves a snapshot carries (L1).

Doc 19 §2-§3: closed shapes × open keys. The shape is `CurveSet`; the keys are open.
Typed accessors — `discount(currency, collateral=None)` and `projection(index)` — over
ONE backing store keyed by `CurveKey`, so a new asset adds keys, not fields. This slice
populates one EUR discount key and two projection keys (the OIS index projects off its
own discount curve — the degenerate config; the IBOR index off a distinct curve). The
`collateral` argument is the ratified signature (so it is not re-broken later) but its
machinery is deferred: a non-None collateral raises. `survival`/`inflation` accessors and
a `{index → curve}` map for multiple projections arrive with their asset class / 2nd curve.

Provenance:
  quarry: quarry/pricebook/curves/ncurve_solver.py (curves-keyed-by-name concept)
  source: docs/19 §2-§3 (closed shapes × open keys; typed CurveSet accessors)
  oracle: OIS projection is the discount curve; a EURIBOR swap prices to zero dual-curve
  slice:  dual-curve-euribor-estr (T1 slice 2)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from enum import Enum
from typing import Mapping

from pricebook.foundation import Currency, RateIndex
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve import CurveHandle
from pricebook.market.survival_curve import SurvivalHandle


class CurveRole(Enum):
    DISCOUNT = "discount"
    PROJECTION = "projection"
    SURVIVAL = "survival"   # credit (B6 slice 1) — keyed by ReferenceEntity


@dataclass(frozen=True)
class CurveKey:
    """Identifies a curve in the set: its role, the asset dimension it is keyed by (a
    `Currency` for discount, a `RateIndex` for projection), and — for discount — the CSA
    `collateral` currency (`None` = own-currency/OIS). Doc 19's fuller asset keying arrives with
    each asset class: `ReferenceEntity` landed with credit (B6 slice 1); underlying and pair follow
    with equity and FX. A new asset class adds **keys, not fields** (§3c)."""

    role: CurveRole
    id: Currency | RateIndex | ReferenceEntity
    collateral: Currency | None = None


@dataclass(frozen=True)
class CurveSet:
    """One backing store of curves, reached through typed accessors (doc 19 §3)."""

    curves: Mapping[CurveKey, CurveHandle]

    def discount(self, currency: Currency, collateral: Currency | None = None) -> CurveHandle:
        """The discount curve for `currency` under a `collateral` CSA. Own-currency collateral
        (`None` or `== currency`) normalizes to the domestic OIS curve; a foreign collateral
        selects its collateral-keyed curve (the xccy-basis curve, slice 6c)."""
        keyed = None if collateral in (None, currency) else collateral
        return self.curves[CurveKey(CurveRole.DISCOUNT, currency, keyed)]

    def projection(self, index: RateIndex) -> CurveHandle:
        """The forward-projection curve for `index`. Single-curve is the degenerate
        config: an OIS index's projection curve IS its discount curve (same object)."""
        return self.curves[CurveKey(CurveRole.PROJECTION, index)]

    def survival(self, entity: ReferenceEntity) -> SurvivalHandle:
        """The entity's survival curve. Distinct capability, distinct key (docs/19 §2) — it returns
        a `SurvivalHandle`, not a `CurveHandle`, because `Q` and `df` are different questions and a
        survival curve has no `df`. Raises on an unknown entity rather than defaulting to a
        risk-free one: a silently risk-free credit curve prices every CDS to zero protection."""
        key = CurveKey(CurveRole.SURVIVAL, entity)
        try:
            curve = self.curves[key]
        except KeyError:
            raise KeyError(f"no survival curve for {entity.name} in the curve set") from None
        return cast("SurvivalHandle", curve)

    def with_curve(self, key: CurveKey, curve: CurveHandle) -> CurveSet:
        """A new `CurveSet` with the curve at `key` replaced (the base is never mutated —
        invariant 3). Risk (L5) uses this to build a bumped market."""
        return CurveSet({**self.curves, key: curve})
