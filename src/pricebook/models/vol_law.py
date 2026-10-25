"""Volatility laws — the (formula · expansion · domain) triple a model quotes its vol in (L3).

A "vol" is meaningless without the law it is quoted in: 20% lognormal and 20% normal are different
numbers for different formulas, valid on different domains. A `VolLaw` is the VALUE that binds the
three inseparable pieces together, so no stage can mix them:

| law | option formula | SABR expansion | defined where |
|---|---|---|---|
| `Lognormal` | `black(F, K, σ, t)` | Hagan 2002 eq 2.17a | `F > 0`, `K > 0` |
| `ShiftedLognormal(s)` | `black(F+s, K+s, σ, t)` | eq 2.17a on the shifted pair | `F+s > 0`, `K+s > 0` |
| `Normal` | `bachelier(F, K, σ_N, t)` | Hagan 2002 eq 2.17b | everywhere (`F`, `K` free) |

**Why a value and not a flag.** The engine composes `model.vol_law.price(...)` — polymorphic
dispatch, so a third law never adds a branch to a pricer. A `law is NORMAL` ladder inside
`price_caplet` is exactly the `isinstance`-on-model prohibition (CLAUDE.md §1); the ONE place a law
is chosen is `vol_law_for`, at model construction.

`defined(F, K)` is the law's DOMAIN, polymorphic in place of the hard-coded `F ≤ 0 ⇒ failure` guard
the lognormal-only engine carried (audit #15): a negative forward is a failure under `Lognormal` and
perfectly ordinary under `Normal`.

Rule of two (§6b): three real laws arrive together with three real consumers each (engine pricer,
SABR model, smile calibrator) — nothing speculative.

Provenance:
  quarry: quarry/pricebook/options/sabr.py (shifted_sabr_implied_vol / sabr_normal_vol); models/black76.py
  source: Hagan et al. (2002) eq 2.17a/2.17b; Black (1976); Bachelier (1900); Cowork SABR-cluster ruling
  oracle: Lognormal.price ≡ black (byte-identical promotion); ShiftedLognormal(0) ≡ Lognormal;
          Normal.price ≡ an independent inline Bachelier; β=0,ν=0 ⇒ σ_N ≡ α at every strike
  slice:  sabr-multilaw (T1 slice 22)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pricebook.market.vol_surface import SabrParams, VolLawKind
from pricebook.models.bachelier import bachelier
from pricebook.models.black import black
from pricebook.models.sabr import sabr_normal_vol, sabr_vol
from pricebook.products.option import OptionType


@runtime_checkable
class VolLaw(Protocol):
    """The law a volatility is quoted in — its option formula, its SABR expansion, its domain.

    **Semantic contract.** `price` is the UNDISCOUNTED expectation of the payoff under the measure
    in which the underlying is a martingale (`E[(F − K)+]` / `E[(K − F)+]`); the L4 engine multiplies
    the numeraire (`df · N · τ` for an optionlet, the annuity for a swaption), exactly as for a flat
    vol. `vol` is always in THIS law's units — never mixed across laws. `sabr_vol` returns a vol in
    the same units `price` consumes, so `price(F, K, law.sabr_vol(F, K, t, p), t, type)` is the one
    composition every stage shares (§3d)."""

    def price(
        self, forward: float, strike: float, vol: float, t: float, option_type: OptionType
    ) -> float: ...

    def sabr_vol(self, forward: float, strike: float, t: float, params: SabrParams) -> float: ...

    def defined(self, forward: float, strike: float) -> bool: ...

    def seed_alpha(self, atm_vol: float, forward: float, beta: float) -> float: ...


@dataclass(frozen=True)
class Lognormal:
    """The Black-76 law: the forward is lognormal, the vol is a Black vol. The law every slice
    before this one assumed implicitly — `price` DELEGATES to `black`, so promoting the engine onto
    `vol_law.price` moved no number (the slice-22 byte-identicality oracle)."""

    def price(
        self, forward: float, strike: float, vol: float, t: float, option_type: OptionType
    ) -> float:
        return black(forward, strike, vol, t, option_type)

    def sabr_vol(self, forward: float, strike: float, t: float, params: SabrParams) -> float:
        return sabr_vol(forward, strike, t, params)

    def defined(self, forward: float, strike: float) -> bool:
        return forward > 0.0 and strike > 0.0

    def seed_alpha(self, atm_vol: float, forward: float, beta: float) -> float:
        return atm_vol * forward ** (1.0 - beta)


@dataclass(frozen=True)
class ShiftedLognormal:
    """The displaced-diffusion law: `F + shift` is lognormal, so a NEGATIVE forward is ordinary as
    long as `F + shift > 0`. Every member is the lognormal one evaluated on the SHIFTED pair — one
    composition, no second expansion to keep in sync (§3d). `shift` is a rate (`0.03` = 3%), chosen
    per market and carried on the surface beside the params it belongs to."""

    shift: float

    def price(
        self, forward: float, strike: float, vol: float, t: float, option_type: OptionType
    ) -> float:
        return black(forward + self.shift, strike + self.shift, vol, t, option_type)

    def sabr_vol(self, forward: float, strike: float, t: float, params: SabrParams) -> float:
        return sabr_vol(forward + self.shift, strike + self.shift, t, params)

    def defined(self, forward: float, strike: float) -> bool:
        return forward + self.shift > 0.0 and strike + self.shift > 0.0

    def seed_alpha(self, atm_vol: float, forward: float, beta: float) -> float:
        return atm_vol * (forward + self.shift) ** (1.0 - beta)


@dataclass(frozen=True)
class Normal:
    """The Bachelier law: the forward diffuses ARITHMETICALLY, the vol is an absolute rate vol
    (`0.008` = 80bp), and NOTHING needs to be positive — `defined` is unconditionally true. Its SABR
    expansion is the β=0 dynamics (`sabr_normal_vol`), whose `z = (ν/α)(F − K)` carries no
    log-moneyness, so the smile survives through zero. The law to reach for when rates are negative
    and the market quotes normal vols rather than a shift."""

    def price(
        self, forward: float, strike: float, vol: float, t: float, option_type: OptionType
    ) -> float:
        return bachelier(forward, strike, vol, t, option_type)

    def sabr_vol(self, forward: float, strike: float, t: float, params: SabrParams) -> float:
        return sabr_normal_vol(forward, strike, t, params)

    def defined(self, forward: float, strike: float) -> bool:
        return True

    def seed_alpha(self, atm_vol: float, forward: float, beta: float) -> float:
        return atm_vol  # β=0 ⇒ α IS the ATM normal vol to leading order


def vol_law_for(kind: VolLawKind, shift: float) -> VolLaw:
    """The ONE tag→law mapping (CLAUDE.md §1): a `SabrSurface`'s data tag becomes the law value that
    prices it. Called at model construction — never inside a pricer, a calibrator or a risk bump, so
    no higher layer ever branches on which law it is dealing with."""
    if kind is VolLawKind.LOGNORMAL:
        return Lognormal()
    if kind is VolLawKind.SHIFTED_LOGNORMAL:
        return ShiftedLognormal(shift)
    return Normal()
