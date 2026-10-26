"""Calibration quotes — market data, distinct from products (L1, doc 18 §1).

Pure data: each quote is what the market prints, keyed to the curve segment it builds
(doc 18 §1). The calibrator turns a quote into a `CalibrationInstrument` (L3) and the
matching tradeable product (L2). A future is quoted as a PRICE; its implied forward rate
is `1 − price` (the convexity correction is deferred to the models topic).

Provenance:
  quarry: quarry/pricebook/curves/ (DepositQuote/FRAQuote/FutureQuote/ParSwapQuote)
  source: doc 18 §1 (quotes are market data); §2 (futures: rate = 1 − price)
  oracle: each quote's instrument reprices to par; future reproduces 1 − price at IMM
  slice:  cash-instruments (T1 slice 3, Step B)
"""

from __future__ import annotations

import math

from dataclasses import dataclass
from datetime import date

from pricebook.foundation import Tenor


@dataclass(frozen=True)
class ParSwapQuote:
    """A par swap of `tenor` at its market par `rate` — the mid/long pillar."""

    tenor: Tenor
    rate: float


@dataclass(frozen=True)
class DepositQuote:
    """A cash deposit from spot to `tenor` at `rate` — the discount-curve front."""

    tenor: Tenor
    rate: float


@dataclass(frozen=True)
class FRAQuote:
    """A forward-rate agreement over ``[start, end]`` at `rate` — a projection-curve
    forward segment. `start=None` means spot (the front-anchoring FRA)."""

    start: Tenor | None
    end: Tenor
    rate: float


@dataclass(frozen=True)
class FutureQuote:
    """An IMM-dated futures quote: `price` (decimal, ~0.965) at IMM date `imm_start`; the
    implied forward rate is ``1 − price`` over ``[imm_start, imm_start + index.tenor]``."""

    imm_start: date
    price: float


@dataclass(frozen=True)
class CapQuote:
    """A flat (quoted) cap volatility: the single lognormal vol that prices the whole cap
    maturing at `maturity`, struck at `strike` — the vol-strip's pillar (doc 18 §1 shape, a
    vol quote). The caplet vols are STRIPPED from a ladder of these (C2 slice 3)."""

    maturity: date
    strike: float
    flat_vol: float


@dataclass(frozen=True)
class SmileQuote:
    """A quoted volatility SMILE at one `expiry`: `strikes` (strictly ascending), the corresponding
    lognormal `vols` one per strike, and the `forward` the smile is quoted AT. The SABR calibration
    target — a smile is a single-expiry row of the surface. Parallel tuples (not a dict) keep it
    ordered and hashable; `__post_init__` guards the length match and the ≥3 points a 3-parameter
    (α, ρ, ν) fit needs.

    **`forward` is intrinsic to the quote, not a calibration parameter** (ruling B4, thread 0008).
    Without it the vols are uninterpretable — a smile fitted against the wrong forward is silently
    wrong by the F-gap — so it travels WITH the smile for exactly the reason `law` travels with
    `SabrSurface.params`. It is REQUIRED: a defaulted forward would reinstate the hidden
    canonical-accrual reconstruction slice A deleted on the read side, which is wrong for any
    product whose forward is not a single-period rate (a swaption's is `float_leg_pv/rpv01`, 48.8bp
    away on a non-canonical underlying). Each consumer supplies the forward its own product
    defines."""

    expiry: date
    strikes: tuple[float, ...]
    vols: tuple[float, ...]
    forward: float

    def __post_init__(self) -> None:
        if len(self.strikes) != len(self.vols):
            raise ValueError("SmileQuote: strikes and vols must have equal length")
        if len(self.strikes) < 3:
            raise ValueError("SmileQuote: a 3-parameter SABR fit needs ≥3 strikes")
        if any(b <= a for a, b in zip(self.strikes, self.strikes[1:])):
            raise ValueError("SmileQuote: strikes must be strictly ascending")
        if not math.isfinite(self.forward):
            raise ValueError(f"SmileQuote: the quoted forward must be finite; got {self.forward}")
