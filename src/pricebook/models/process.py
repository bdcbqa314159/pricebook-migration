"""`StateProcess` — the simulatable-dynamics abstraction (L3).

The ratified cross-cutting abstraction of the (c) arc, introduced with **both** its consumers
present (§6b's rule of two met at birth): Hull-White's exact Gaussian sampler is refactored onto
it, and `BlackScholesProcess` is written against it. The generic MC core composes it without
knowing which dynamics it holds (§1 — no `isinstance` on a concrete model).

**Why the protocol is a MARGINAL sampler and not a path/grid sampler.** Both present consumers
have an *exact* transition at a single date under that date's own forward measure — HW's short
rate is Gaussian, BS's spot lognormal — so neither needs time stepping, and a time grid would be
a reproducibility knob that cannot change the answer (`MonteCarloConfig` says exactly this). A
joint-path shape is a different capability: it is what **wrong-way risk** needs, because WWR
conditions on the default time and therefore on the *joint* law across dates. It arrives with
that consumer, named rather than guessed — widening the protocol now for a consumer that does not
exist is the speculative generality §6b forbids.

Provenance:
  quarry: quarry/pricebook/models/processes_extended.py · models/gbm.py (the process CONCEPT and
          the GBM content; their `evolve`-per-step shape is NOT carried — exact sampling makes
          stepping unnecessary for both present consumers)
  source: Hull & White (1990) for the Gaussian transition; Black-Scholes (1973) / Merton (1973)
          for the lognormal; docs/22 Q1 (capability protocols on models)
  oracle: both HW and BS satisfy one protocol; `E[S_t] = S₀e^{(r−q)t}` and the lognormal variance
          on the drawn states; a European option by MC reproduces the c1 closed form within
          3·stderr; HW MC byte-identical across 140 exposure points after the refactor
  slice:  c2 StateProcess ((c) slice 2)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from pricebook.foundation import Currency
from pricebook.foundation.equity import EquityUnderlying
from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey, MarketSnapshot
from pricebook.market.vol_surface import EquitySurfaceKey, flat_surface
from pricebook.models.black import vol_time_measure


@runtime_checkable
class StateProcess(Protocol):
    """A dynamics that can be simulated: draw the state variable at one date.

    The state's *meaning* is the dynamics' own business — HW draws a short rate, BS draws a spot —
    and the MC core deliberately does not know which. What it relies on is the contract: an array
    of `numerics.paths` draws of the state at `t`, under `t`'s own forward measure, **exactly**
    (no discretisation bias), and reproducible from `numerics.seed` (invariant 1)."""

    @property
    def market(self) -> MarketSnapshot:
        """The snapshot the dynamics was built on (A1) — declared on the capability rather than
        reached with `getattr`, the same fix `SurvivalHandle.bumped_at` and
        `CurveHandle.forward_started` made."""
        ...

    def sample_state(self, t: float, numerics: MonteCarloConfig) -> NDArray[np.float64]: ...


@dataclass(frozen=True)
class BlackScholesProcess:
    """Equity spot under Black-Scholes-Merton, sampled **exactly**:

        S_t = S₀ · exp( (r − q − ½σ²)·t + σ√t·Z ),   Z ~ N(0,1)

    Exact, not an Euler step, so MC's only error is statistical — which is what lets the oracle be
    *agreement with the c1 closed form* rather than mere convergence.

    `r` is taken from the discount curve as `−ln df(t)/t`, never as a separate parameter: the same
    single-source rule `equity_forward` follows, so the simulated drift and the pricer's discount
    cannot disagree (§3d). Spot, `q` and `σ` are read from the snapshot by `EquityUnderlying` key,
    so the process carries no market state of its own (A1 — the model carries the snapshot)."""

    market: MarketSnapshot
    underlying: EquityUnderlying
    currency: Currency

    def sample_state(self, t: float, numerics: MonteCarloConfig) -> NDArray[np.float64]:
        spot = self.market.scalars[EquitySpotKey(self.underlying)]
        q = self.market.scalars[DividendYieldKey(self.underlying)]
        drift_total = self._growth(t) - q * t
        if t <= 0.0:
            return np.full(numerics.paths, spot)
        vol = flat_surface(self.market.surfaces[EquitySurfaceKey(self.underlying)]).at(
            self._date(t), spot, vol_time_measure(self.market.valuation_date)
        )
        if vol <= 0.0:
            return np.full(numerics.paths, spot * math.exp(drift_total))
        rng = np.random.default_rng((numerics.seed, round(t * 1_000_000)))
        z = rng.standard_normal(numerics.paths)
        return spot * np.exp(drift_total - 0.5 * vol * vol * t + vol * math.sqrt(t) * z)

    def _growth(self, t: float) -> float:
        """`r·t` read off the curve as `−ln df(t)`. One source for the financing leg — see
        `equity_forward`, which makes the same substitution for the same reason."""
        return -math.log(self.market.curves.discount(self.currency, None).df(self._date(t)))

    def _date(self, t: float) -> date:
        """`t` back to a date on the canonical ACT/365F vol clock, so the drift, the vol read and
        the discount all sit on one `date → t` map (§3d, #4) rather than three."""
        return self.market.valuation_date + timedelta(days=round(t * 365.0))
