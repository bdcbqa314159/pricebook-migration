"""Credit risk — CS01, bucketed CS01 (L5).

The L5 pattern unchanged: a `Priceable` reprices at a bumped `MarketSnapshot` and `central_diff`
takes the difference. The only credit-specific parts are the two `Bump`s (`SurvivalBump`,
`SurvivalPillarBump`), so there is **no `isinstance` on the instrument** anywhere here (§1) — a CDS,
a credit-linked note or a basket all route through the same code because they all satisfy
`Priceable`.

**The bump is on the HAZARD, not on Q** (slice-1 ruling): Q has no units and a Q shift does not stay
monotone, whereas a hazard shift does both and is the credit-spread move a desk quotes.

**Bucketed CS01 is a DECOMPOSITION, not a vector of unrelated numbers.** The per-pillar bumps
partition the curve's hazard segments — segment `i` appears in bucket `i` and nowhere else — so the
buckets **sum to** the parallel CS01 up to cross-convexity. That identity is the slice's structural
oracle (§6): a scalar CS01 cannot reveal a dropped or double-counted bucket, and a count cannot
reveal risk smeared past maturity, so both are asserted.

Provenance:
  quarry: quarry/pricebook/credit/credit_risk.py; quarry/pricebook/credit/cds.py (`cs01`,
          `bucket_cs01` — the analytics are mined for content, the shape is ng's L5: bump the
          snapshot, reprice through the engine, never a method on the product)
  source: O'Kane (2008) Ch. 8 (CDS risk); CLAUDE.md §1 (risk@L5 via Priceable, no isinstance)
  oracle: analytic ∂PV/∂λ for the flat-hazard CDS vs the bump-reprice; bucketed sums to parallel;
          N hazard segments → N buckets; buckets beyond maturity are zero
  slice:  credit-cs01-rec01 (B6 slice 3)
"""

from __future__ import annotations

from typing import cast

from pricebook.foundation.results import PricingFailure
from pricebook.market.curve_set import CurveKey
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.survival_curve import SurvivalHandle
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.risk.bump import RecoveryBump, SurvivalBump, SurvivalPillarBump
from pricebook.risk.greeks import central_diff
from pricebook.risk.priceable import Priceable

#: One basis point of hazard — the unit CS01 is quoted in.
_BP = 1e-4


def cs01(
    p: Priceable, market: MarketSnapshot, key: CurveKey, shift: float = _BP
) -> float | PricingFailure:
    """Parallel credit spread sensitivity: the PV change for a `shift` (default 1bp) parallel move in
    the survival curve's hazard. Positive for bought protection — widening spreads make protection
    more valuable.

    Reported **per `shift`**, i.e. as a 1bp CS01 rather than a per-unit derivative, which is how a
    desk quotes it; the analytic oracle scales its derivative by the same `shift` to compare."""
    out = central_diff(p, market, SurvivalBump(key), shift)
    if isinstance(out, PricingFailure):
        return out
    return out * shift


def bucketed_cs01(
    p: Priceable, market: MarketSnapshot, key: CurveKey, shift: float = _BP
) -> tuple[float, ...] | PricingFailure:
    """Key-rate credit risk: one CS01 per hazard segment of the survival curve at `key`.

    Returns **one bucket per segment, always** — a segment that cannot be bumped propagates as a
    `PricingFailure` rather than being dropped from the tuple, because a short vector silently
    rebalances the whole decomposition (the §6 floor rule: the population is asserted, not hoped
    for). Buckets beyond the instrument's maturity come out zero, which is a fact about the
    instrument rather than a special case in this code."""
    try:
        curve = cast("SurvivalHandle", market.curves.curves[key])
        segments = curve.hazard_segments
    except (KeyError, AttributeError):
        return PricingFailure(f"no survival curve to bucket at key {key}")
    if segments < 1:
        return PricingFailure(f"the curve at {key} has no hazard segments to bucket")

    buckets: list[float] = []
    for pillar in range(segments):
        out = central_diff(p, market, SurvivalPillarBump(key, pillar), shift)
        if isinstance(out, PricingFailure):
            return out
        buckets.append(out * shift)
    return tuple(buckets)


def rec01(
    p: Priceable, market: MarketSnapshot, entity: ReferenceEntity, shift: float = _BP
) -> float | PricingFailure:
    """Recovery sensitivity: the PV change for a `shift` (default 1bp) move in the entity's recovery
    rate. **Negative for bought protection** — a higher recovery means less is paid out on default.

    The protection leg is linear in `(1−R)` and the premium leg does not involve R at all, so the
    analytic derivative is exactly `−protection/(1−R)` and rec01 is **independent of the contract
    spread**. That independence is itself an oracle: if rec01 varied with the spread, R would be
    leaking into the annuity."""
    out = central_diff(p, market, RecoveryBump(entity), shift)
    if isinstance(out, PricingFailure):
        return out
    return out * shift


def jump_to_default(
    p: Priceable, market: MarketSnapshot, entity: ReferenceEntity
) -> float | PricingFailure:
    """Jump-to-default: the PV change if `entity` defaults **right now**.

    **Not a derivative** — default is a discrete event, so there is no bump and no finite difference.
    For bought protection the holder receives `(1−R)·N`, stops paying premium, and owes the premium
    accrued to today, so

        JTD = (1−R)·N − accrued_owed − PV

    and the `accrued` the mark already reports is the owed amount (negative for bought protection,
    invariant 6), which is why it ADDS here. This is the defining credit risk: CS01 measures a
    re-pricing, JTD measures the event itself, and a book can be CS01-flat while carrying a large
    jump.

    It is computed from the instrument's own notional-and-recovery state via one reprice, so it stays
    instrument-type-blind like the rest of L5 — no `isinstance` (§1)."""
    base = p.price_at(market)
    if isinstance(base, PricingFailure):
        return base
    try:
        recovery = market.recovery(entity)
    except KeyError as exc:
        return PricingFailure(str(exc))
    notional = _notional_of(p)
    if notional is None:
        return PricingFailure("jump-to-default needs the instrument's notional")
    accrued = 0.0 if base.accrued is None else base.accrued.amount
    return (1.0 - recovery) * notional + accrued - base.pv.amount


def _notional_of(p: Priceable) -> float | None:
    """The signed notional the protection is written on. Reached through the `Priceable`'s closed-over
    instrument rather than by type-switching on it: JTD is the one credit measure that is not a
    reprice difference, so it needs the face amount, and this keeps that the only coupling."""
    instrument = getattr(p, "instrument", None)
    notional = getattr(instrument, "notional", None)
    return getattr(notional, "amount", None)
