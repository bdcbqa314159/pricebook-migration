"""Optionlet products — pure data (L2).

A `CapFloor` is a strip of them — pure data too: it holds its `schedule`, and `cap_ladder` derives
the optionlets (the ONE definition every stage composes, §3d).

A `Caplet` is an option on a forward rate: it pays `notional · τ · (F − strike)+` (a CALL — the
caplet) or `notional · τ · (strike − F)+` (a PUT — the floorlet) at the accrual end, where `F` is
the `index` forward over the accrual. Pure data — it does not price itself (pricing is L4).
`OptionType` is the payoff parity the pricer reads; the PUT arrived with its consumer, the floor
(slice 23).

Provenance:
  quarry: quarry/pricebook/options/capfloor.py (caplet composition)
  source: CLAUDE.md §2 (products are pure data); docs/12 §B5 (caps/floors)
  oracle: caplet reprices to Black-76 closed form through the L4 engine; a 2Y 3M cap is a
          SEVEN-caplet ladder (audit #10); cap − floor = the forward-start swap
  slice:  black-caplet (C2 slice 1) · CapFloor + cap_ladder in capfloor (T1 slice 23)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from datetime import date

from pricebook.foundation import Accrual, RateIndex, Schedule
from pricebook.products.swap import VanillaSwap


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


@dataclass(frozen=True)
class Caplet:
    """One optionlet on the `index` forward over `accrual`, struck at `strike`, on `notional`.
    Fixes at `accrual.start`, pays at `accrual.end`: a CALL (caplet) pays `notional · τ · (F −
    strike)+`, a PUT (floorlet) `notional · τ · (strike − F)+`. The element of a cap/floor ladder."""

    index: RateIndex
    accrual: Accrual
    strike: float
    notional: float
    option_type: OptionType = OptionType.CALL


@dataclass(frozen=True)
class CapFloor:
    """A cap (CALL) or floor (PUT) on `index` over `schedule`, struck at `strike`, on `notional` —
    pure data. It IS its ladder of optionlets, which `cap_ladder` derives; the product itself holds
    no caplet list, so there is exactly one definition of "which caplets a cap is" (§3d).

    The day count is the index's own (`index.accrual.day_count`) — a cap does not carry a second
    accrual convention; and the schedule must step at the index tenor for the ladder's caplets to be
    the index's canonical accruals (the engine's ruling-2 guard enforces it per caplet, loudly, so a
    mismatched schedule fails rather than pricing a different contract)."""

    index: RateIndex
    schedule: Schedule
    strike: float
    notional: float
    option_type: OptionType = OptionType.CALL

    def __post_init__(self) -> None:
        if self.notional <= 0.0:  # quarry content: a cap is written on a positive notional
            raise ValueError(f"notional must be positive, got {self.notional}")
        if len(self.schedule.periods) < 2:
            # the first period is never optional (its rate is set at the start), so a one-period
            # schedule has an EMPTY ladder — a cap with nothing optional in it is a mis-booking
            raise ValueError(
                f"a cap/floor needs ≥2 schedule periods (the first is already set); "
                f"got {len(self.schedule.periods)}"
            )


def cap_ladder(cap: CapFloor) -> tuple[Caplet, ...]:
    """The cap's optionlet strip — **the one definition**, composed by the L4 pricer, the caplet-vol
    strip and the SABR-cap calibration alike (§3d: an atom defined once, never re-derived per stage;
    audit #10 is exactly what re-deriving it cost).

    **The first period is excluded.** Its rate is set at the cap's start, so it is a known cashflow,
    not an option — caps are quoted excluding it (market convention, Brigo–Mercurio §1.6). It is also
    what makes a spot-starting cap priceable: the engine refuses a *seasoned* optionlet as a value
    (#3a), so a ladder including period 0 would fail every cap a vol strip needs to price. A
    genuinely forward-starting cap therefore loses a caplet — deferred with a trigger (`OPEN.md`),
    because including it needs the valuation date, which would make this atom valuation-dependent
    and the ladders of the pricer, the strip and the calibrator free to diverge again.

    Each caplet carries the **contract's own** accrual period (on the index's day count), not a
    substituted canonical one: `cap == Σ cap_ladder(cap)` is then exact, and a non-canonical schedule
    trips the per-caplet F-identity guard instead of silently repricing a different contract."""
    day_count = cap.index.accrual.day_count
    return tuple(
        Caplet(
            cap.index,
            Accrual(p.accrual_start, p.accrual_end, day_count),
            cap.strike,
            cap.notional,
            cap.option_type,
        )
        for p in cap.schedule.periods[1:]
    )


@dataclass(frozen=True)
class Swaption:
    """A European swaption on `swap` (a `VanillaSwap`), exercisable at `expiry` into physical
    settlement. The strike IS `swap.fixed_leg.rate`; `option_type` is the parity — a PAYER
    swaption (option to pay fixed) is a CALL on the swap rate, a RECEIVER a PUT. Pure data."""

    swap: VanillaSwap
    expiry: date
    option_type: OptionType
