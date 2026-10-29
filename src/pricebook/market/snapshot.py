"""MarketSnapshot — the immutable market state a model carries (L1).

The valuation date, the `CurveSet`, and (this slice) the `scalars` shape — the first non-curve
shape of doc 19's closed-shapes × open-keys design. `scalars` holds FX spots keyed by pair, in
their DECLARED canonical quote order; `fx_rate(base, quote)` asserts the pair is declared,
inverts internally, and RAISES on an undeclared cross — never a bare pair-scalar (doc 19 §2.1).
`surfaces` (vol) lands this slice — its first consumer is the Black caplet (C2). Series · schedules
still arrive with theirs. Frozen (A1, invariant 3).

Provenance:
  quarry: quarry/pricebook/pricing/market_data_provider.py
  source: docs/19 §1-§3 (snapshot shapes; CurveSet) · §2.1 (FX directional); CLAUDE.md §2 (A1)
  oracle: fx_rate(A,B)·fx_rate(B,A) == 1; an undeclared cross raises
  slice:  fx-spot (T1 slice 6a)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Mapping

from pricebook.foundation import Currency, CurrencyPair, FixingHistory, FixingSource, fx_pair
from pricebook.foundation.equity import EquityUnderlying
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve_set import CurveSet
from pricebook.market.vol_surface import SurfaceKeyType, SabrSurface, Surface, SurfaceKey, SwaptionSurfaceKey


@dataclass(frozen=True)
class ScalarKey:
    """A key into the snapshot's `scalars` shape. This slice: an FX spot, keyed by its pair
    (a new asset adds keys, not fields). Carries the pair only — rule of two."""

    pair: CurrencyPair


@dataclass(frozen=True)
class RecoveryKey:
    """A key into `scalars` for a reference entity's **recovery rate** — the fraction of notional
    recovered on default. A sibling of `ScalarKey`, not a field on it: a new asset class adds
    **keys, not fields** (§3c), the same way `surfaces` takes `SurfaceKey | SwaptionSurfaceKey`.

    **Recovery is market state, not contract data** (§3c: *"Hazard/survival curve and recovery → L1
    (risk bumps them)"*). It lived on the L2 `CDS` and on the bootstrap spec until slice 4, which is
    two sources for one number: with the curve bootstrapped at R=0.40 and the CDS marked at R=0.30,
    a **par** quote priced to ≈96bp of notional, silently. One home makes that unrepresentable."""

    entity: ReferenceEntity


@dataclass(frozen=True)
class EquitySpotKey:
    """A key into `scalars` for an equity's **spot price**. A sibling of `ScalarKey`/`RecoveryKey`:
    the equity asset class adds **keys, not fields** (§3c), so `scalars` gains a key type and the
    snapshot's shape is unchanged."""

    underlying: EquityUnderlying


@dataclass(frozen=True)
class DividendYieldKey:
    """A key into `scalars` for an equity's **continuous dividend yield** `q`.

    Its own key rather than a field on `EquitySpotKey`, because spot and dividend yield are two
    independently-bumped market numbers: `bump_spot` must move one without the other, and a
    combined key would make a dividend bump indistinguishable from a spot bump at the snapshot.
    Flat `q` for now — a dividend *curve* and discrete dividends arrive with their consumer."""

    underlying: EquityUnderlying


#: Every key type the `scalars` shape accepts. Named, because this union grows by one entry per
#: asset class (keys, not fields — §3c) and a `Mapping` key is INVARIANT: without the alias every
#: producer of a scalars dict has to restate the full union, and each new asset class breaks them
#: all at once. Widen here; producers annotate with the alias.
ScalarKeyType = ScalarKey | RecoveryKey | EquitySpotKey | DividendYieldKey


@dataclass(frozen=True)
class MarketSnapshot:
    """The market state a model was calibrated to (A1). `valuation_date` is 'today';
    `curves` is the keyed `CurveSet`; `scalars` holds FX spots (and future single-number
    market data), reached through typed accessors — never as bare values."""

    valuation_date: date
    curves: CurveSet
    scalars: Mapping[ScalarKeyType, float] = field(default_factory=dict)
    surfaces: Mapping[SurfaceKeyType, Surface | SabrSurface] = field(default_factory=dict)
    fixings: FixingSource = field(default_factory=lambda: FixingHistory({}))  # the "series" shape (doc 19 §2)

    def __post_init__(self) -> None:
        for key, value in self.scalars.items():
            if isinstance(key, RecoveryKey) and not 0.0 <= value < 1.0:
                raise ValueError(
                    f"recovery for {key.entity.name} must be in [0, 1); got {value}"
                )

    def recovery(self, entity: ReferenceEntity) -> float:
        """The entity's recovery rate. **The single source** both the survival bootstrap and the CDS
        mark read, so they cannot disagree (§3d). Raises on an absent entity rather than assuming
        the 0.40 market convention — that convention is exactly why a silent default would be
        dangerous: it would look right in every standard case and wrong in the ones that matter."""
        try:
            return self.scalars[RecoveryKey(entity)]
        except KeyError:
            raise KeyError(f"no recovery rate for {entity.name} in the snapshot") from None

    def fx_rate(self, base: Currency, quote: Currency) -> float:
        """One unit of `base` in units of `quote`. Resolves the declared canonical pair
        (raising on an undeclared cross), reads the stored spot, and inverts if `base/quote`
        is the reverse of the declared direction — the rate is never ambiguous (doc 19 §2.1)."""
        canonical = fx_pair(base, quote)
        spot = self.scalars[ScalarKey(canonical)]
        if canonical.base == base and canonical.quote == quote:
            return spot
        return 1.0 / spot
