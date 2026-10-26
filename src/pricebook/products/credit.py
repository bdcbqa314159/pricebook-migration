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

    `recovery` is contractual here, not market state: this is the R the *contract* assumes for its
    mark. (The market-implied recovery a curve was bootstrapped under lives with the calibration —
    a basis between them is a real trade and arrives with its consumer.)"""

    entity: ReferenceEntity
    premium: PremiumLeg
    recovery: float
    notional: Money

    def __post_init__(self) -> None:
        if not 0.0 <= self.recovery < 1.0:
            raise ValueError(f"CDS recovery must be in [0, 1); got {self.recovery}")
        if self.premium.spread < 0.0:
            raise ValueError(f"CDS spread must be non-negative; got {self.premium.spread}")
        if not self.premium.schedule.periods:
            raise ValueError("CDS premium leg needs at least one period")
