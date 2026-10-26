"""Credit products — the vanilla single-name CDS (L2).

Pure data: it *describes* the contract and does not price itself (§2 — pricing lives in L4).

**Vanilla only, deliberately.** §3c step 3 places credit-event definitions, restructuring clause and
seniority in L2 product data — but §6b forbids building that convention surface before a consumer
needs it, and a standard contract needs none of it to be marked. They arrive with the first product
that distinguishes on them (an old-R vs new-R name, a sub-vs-senior basis trade), each validated
rather than guessed — the same discipline `underlying.py` applied to the identity fields.

Provenance:
  quarry: quarry/pricebook/credit/cds.py (the contract's content: quarterly ACT/360 premium, the
          recovery/notional conventions — mined for content, not for shape, per §4)
  source: ISDA Standard CDS contract; O'Kane (2008) Ch. 5
  oracle: an off-par flat-hazard mark against closed form (tests/L4/test_cds.py)
  slice:  credit-cds-mark (B6 slice 2)
"""

from __future__ import annotations

from dataclasses import dataclass

from pricebook.foundation.day_count import DayCountConvention
from pricebook.foundation.money import Money
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.foundation.schedule import Schedule


@dataclass(frozen=True)
class PremiumLeg:
    """The CDS premium (fee) leg: its accrual `schedule`, `day_count`, and the contractual
    `spread` (annualised, e.g. 0.01 = 100bp). Mirrors `FixedLeg` — the leg bundles its own
    convention context, so the engine never guesses a day count (§3b, §3d)."""

    schedule: Schedule
    day_count: DayCountConvention
    spread: float


@dataclass(frozen=True)
class CDS:
    """A vanilla single-name CDS on `entity`. `notional` is signed: **positive = bought
    protection** (pay the premium, receive `(1−R)·N` on default), negative = sold.

    **There is no `recovery` field.** It lived here until slice 4 and that was a mis-layering:
    §3c puts recovery at **L1** ("risk bumps them"), and keeping a copy on the contract meant a mark
    could use a different R from the one its curve was bootstrapped under — a par quote then priced
    to ≈96bp of notional, silently. The single R lives in `snapshot.scalars[RecoveryKey(entity)]`
    and both the bootstrap and the mark read it. (A genuinely *fixed-recovery* CDS, where R is a
    contractual term rather than a market assumption, is a different product and brings its own L2
    term when it arrives — §6b.)"""

    entity: ReferenceEntity
    premium: PremiumLeg
    notional: Money

    def __post_init__(self) -> None:
        if self.premium.spread < 0.0:
            raise ValueError(f"CDS spread must be non-negative; got {self.premium.spread}")
        if not self.premium.schedule.periods:
            raise ValueError("CDS premium leg needs at least one period")
