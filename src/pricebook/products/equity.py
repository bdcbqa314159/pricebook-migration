"""Equity option product (L2) — pure data, European.

Provenance:
  quarry: quarry/pricebook/options/equity_option.py (the vanilla European content; its Greeks,
          American exercise and exotics are NOT carried — deferred to their consumers, §6b)
  source: Black (1976) via the equity forward; Merton (1973) continuous dividend yield
  oracle: prices to the Black-Scholes-Merton spot form to 1e-10 (test_equity_vanilla)
  slice:  equity-vanilla ((c) slice 1)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pricebook.foundation import Currency
from pricebook.foundation.equity import EquityUnderlying
from pricebook.products.option import OptionType


@dataclass(frozen=True)
class EquityOption:
    """A European equity option: the right to buy (`CALL`) or sell (`PUT`) one unit of
    `underlying` at `strike` on `expiry`. Four fields and no notional — a one-unit contract, so
    quantity is the holder's business (the L6 trade), not the product's.

    Describes only; it does not price itself (§2). Spot, dividend yield and vol are NOT fields:
    they are market state reached through the model's snapshot, which is what makes a
    model/market mismatch unrepresentable.

    `currency` IS a field, and deliberately so: it names the discount curve to mark against.
    Deriving it from the snapshot instead ("the only curve there is") reads correctly in a
    single-currency book and silently marks a EUR option off the USD curve the moment the
    snapshot holds two — a wrong number with no error."""

    underlying: EquityUnderlying
    strike: float
    expiry: date
    option_type: OptionType
    currency: Currency = Currency.USD


@dataclass(frozen=True)
class EquityForward:
    """A European equity forward: pay `strike` at `expiry`, receive one unit of `underlying`.

    Built here because the exposure slice needs a product whose **MtM goes negative** — a long
    option's never does, so `max(V, 0)` is a no-op on it and an exposure builder that dropped the
    floor entirely would pass every option test. The forward is the smallest product that
    exercises the floor, and its own exposure has a closed form (the positive part of a forward
    IS a call), so it is an oracle rather than scaffolding."""

    underlying: EquityUnderlying
    strike: float
    expiry: date
    currency: Currency = Currency.USD
