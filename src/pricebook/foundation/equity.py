"""Equity underlying identity (L0).

§3c corollary: an asset class adds **one** L0 object — its identity — as a sibling under
`Underlying`, never asset-specific machinery. Spot, dividend yield and vol are **market state
that risk bumps**, so they live in the L1 snapshot keyed by this identity (§3c step 2); the
option contract is L2; the pricing is L4. This file is the whole of equity's L0 footprint.

Provenance:
  quarry: — (the quarry has no equity identity type; its equity modules key on bare `str`
          tickers, which is the un-bundled-vocabulary smell §3b names)
  source: CLAUDE.md §3c (asset-class onboarding) + its credit worked example; docs/19 §2
          closed shapes × open keys
  oracle: satisfies the `Underlying` protocol; keys spot/dividend/vol by VALUE (test_equity_vanilla)
  slice:  equity-vanilla ((c) slice 1)
"""

from __future__ import annotations

from dataclasses import dataclass

from pricebook.foundation.underlying import AssetClass


@dataclass(frozen=True)
class EquityUnderlying:
    """An equity underlying, by `name` (the ticker or issue identifier). Frozen and hashable so
    it keys the snapshot by VALUE — two `EquityUnderlying("ACME")` are one key, which is what a
    snapshot and a bump need. Carries **no** price, vol or dividend: those are market state that
    risk bumps, and putting them here would give each of them two homes (the mistake `RecoveryKey`
    was created to undo)."""

    name: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("EquityUnderlying needs a non-empty name")

    @property
    def asset_class(self) -> AssetClass:
        return AssetClass.EQUITY
