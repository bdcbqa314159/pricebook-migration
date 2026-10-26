"""ReferenceEntity — the credit identity (L0).

The one L0 object credit adds (§3c corollary: an asset class adds roughly *one* L0 object — its
identity, as a sibling under `Underlying`; wanting to add more is a smell). Survival curves are
keyed by it, a CDS references it, and credit risk bumps by it — a multi-layer identity, which is
exactly §3c step 5.

**It carries no hazard and no recovery.** Those are market state that risk bumps, so they live in
the L1 snapshot (§3c step 2). Nor does it carry seniority, restructuring clause or credit-event
definitions — those are contract description, so L2 product data (§3c step 3). What is left is the
identity itself, and `name` is the whole of it.

`underlying.py` records why this file is only arriving now: the speculative `ReferenceEntity`
sibling was cut in Phase 4 for having zero consumers and guessed fields, to return "with *validated*
fields — when its asset class actually ships". This is that return, and `name` is validated.

Provenance:
  quarry: quarry/pricebook/credit/ (the entity was an implicit string key throughout; never a type)
  source: CLAUDE.md §3c worked example (credit); docs/19 §2 closed shapes × open keys
  oracle: satisfies the `Underlying` protocol; keys a survival curve by value, not object identity
  slice:  credit-survival-bootstrap (B6 slice 1)
"""

from __future__ import annotations

from dataclasses import dataclass

from pricebook.foundation.underlying import AssetClass


@dataclass(frozen=True)
class ReferenceEntity:
    """The credit reference entity, by `name`. Frozen and hashable so it can key a curve by
    VALUE — two `ReferenceEntity("ACME")` are the same key, which is what a snapshot needs."""

    name: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("ReferenceEntity needs a non-empty name")

    @property
    def asset_class(self) -> AssetClass:
        return AssetClass.CREDIT
