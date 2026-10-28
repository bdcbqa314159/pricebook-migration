"""Vanilla interest-rate swap — pure product data (L2).

A frozen description with no behaviour (pricing lives in L4). A `VanillaSwap` is a
fixed leg and a float leg on one notional/currency. The legs are bundled value objects
(≤5 fields each): a swap of 8 loose primitives is the same un-bundled smell PLR0913
can't see (CLAUDE.md §3b). The float leg's projection index arrives with multicurve —
its second (projection) curve is the consumer that earns it (rule of two).

Provenance:
  quarry: quarry/pricebook/fixed_income/swap.py
  source: docs/18 (T1 linear products); CLAUDE.md §2 (products are pure data)
  oracle: EURIBOR par swap reprices to zero NPV dual-curve through the L4 engine
  slice:  dual-curve-euribor-estr (T1 slice 2); float leg gained its index here
"""

from __future__ import annotations

from dataclasses import dataclass

from pricebook.foundation import Currency, DayCountConvention, RateIndex, Schedule


def _check_notionals(notionals: tuple[float, ...] | None, schedule: Schedule) -> None:
    """A notional schedule is meaningless unless it lines up with the accrual periods it weights,
    and a silent misalignment would price a real trade wrong (the weighting would slide by a
    period). Refused at construction — a trust boundary, so fail fast and loud."""
    if notionals is not None and len(notionals) != len(schedule.periods):
        raise ValueError(
            f"notionals has {len(notionals)} entries for {len(schedule.periods)} accrual periods"
        )


@dataclass(frozen=True)
class FixedLeg:
    """A fixed leg: its accrual `schedule`, `day_count`, fixed `rate`, and an optional per-period
    `notionals` schedule. `None` is the constant-notional case — the overwhelmingly common one —
    and means "the swap's scalar notional at every period", so the flat swap is the degenerate
    schedule rather than a separate product (no `VariableNotionalSwap`, no engine type-switch)."""

    schedule: Schedule
    day_count: DayCountConvention
    rate: float
    notionals: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        _check_notionals(self.notionals, self.schedule)


@dataclass(frozen=True)
class FloatLeg:
    """A floating leg: its accrual `schedule`, `day_count`, and the `index` it fixes on.
    The `index` selects the projection curve (`CurveSet.projection(index)`); for an OIS
    index that curve is the discount curve itself (single-curve degenerate)."""

    schedule: Schedule
    day_count: DayCountConvention
    index: RateIndex
    notionals: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        _check_notionals(self.notionals, self.schedule)


@dataclass(frozen=True)
class VanillaSwap:
    """A fixed-for-float swap on one `notional`/`currency`, discounted under a CSA in
    `collateral` currency (`None` = own-currency/OIS). PV is taken from the fixed-rate
    PAYER's side (pay fixed, receive float); the receiver is its negative. (Relocation
    trigger: `collateral`/CSA moves to the L6 trade layer when L6 lands.)"""

    notional: float
    currency: Currency
    fixed_leg: FixedLeg
    float_leg: FloatLeg
    collateral: Currency | None = None

    # ── the two readers the desks consume (`desks/api_desk`, `desks/swap_desk`). Description,
    #    not pricing — they report the contract's own notional profile and compute no PV, so
    #    they sit on the product without breaking "products do not price themselves" (§2).
    def notional_schedule(self) -> tuple[float, ...]:
        """The per-period notional of the FIXED leg — the amortisation profile. A constant-notional
        swap reports its scalar at every period, so callers never branch on which kind they hold."""
        if self.fixed_leg.notionals is not None:
            return self.fixed_leg.notionals
        return (self.notional,) * len(self.fixed_leg.schedule.periods)

    def average_notional(self) -> float:
        """The ARITHMETIC mean of the notional schedule — the quarry's definition
        (`fixed_income/swap.py::average_notional`, "arithmetic mean of the notional schedule"),
        carried unchanged so a crossing desk reports the same number. Note it is deliberately
        NOT time- or annuity-weighted: with uneven periods those differ, and matching the
        quarry's stated convention is what the retire needs."""
        sched = self.notional_schedule()
        return sum(sched) / len(sched)


@dataclass(frozen=True)
class XccyBasisSwap:
    """A constant-notional cross-currency basis swap under a `collateral` (domestic) CSA:
    pay a domestic OIS-flat leg, receive the `foreign_leg` (its currency = `foreign_leg.index`'s)
    plus a `basis` spread, with notional exchanged at spot at start and maturity.

    Minimal single-curve-per-currency form (doc 18 §1): the domestic leg is OIS-flat, so under
    its own collateral it prices to par and the notional exchange nets to zero — its PV, and with
    it the FX spot (`N_foreign = N_domestic/S`), CANCEL. The mark is therefore the foreign leg
    (discounted on the foreign-collateral curve, projected on the foreign OIS) plus the basis
    annuity plus the foreign notional exchange. Tenor-basis, MtM-notional resets, and NDFs are
    deferred (named triggers). (Relocation trigger: collateral/CSA → the L6 trade layer.)"""

    notional: float
    foreign_leg: FloatLeg
    collateral: Currency
    basis: float
