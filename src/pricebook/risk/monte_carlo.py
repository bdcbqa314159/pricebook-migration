"""The generic Monte-Carlo core (L5) — sample a `StateProcess`, value, average.

Everything model-specific lives behind two things the caller supplies: the **process** (which
knows its own dynamics) and the **value function** (which knows what the states are worth). This
module knows neither, which is the whole point — it must name no concrete dynamics, and a test
asserts that it does not (§1: depend on the capability, not the type).

The value function stays a plain callable rather than a `Payoff` protocol: §6b's rule of two is
not met for it yet — exposure valuation and an option payoff are its two present uses, but they
are both *closures over already-existing* atoms (HW's bond, a vanilla payoff), so there is no
shared vocabulary to name. A `Payoff` type arrives when a consumer needs to *store* or *dispatch
on* one; CLAUDE.md §3d already names it as the deferred block for exotics.

Provenance:
  quarry: quarry/pricebook/models/mc_exposure.py (the MC loop CONTENT; its CVA/DVA/FVA bundling
          and rates-specific shape are not carried — ng splits profile from atom)
  source: standard Monte-Carlo estimator; stderr = s/√n (Glasserman, Monte Carlo Methods ch. 1)
  oracle: a European equity option over BlackScholesProcess reproduces the c1 Black-Scholes
          closed form within 3·stderr; HW exposures byte-identical through this core
  slice:  c2 StateProcess ((c) slice 2)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.models.process import StateProcess


@dataclass(frozen=True)
class McEstimate:
    """A Monte-Carlo estimate and its standard error.

    The stderr is returned rather than left to the caller because an MC number without it is not
    a result: every oracle against this has to be stated in standard errors (the green-oracle gate
    has no tolerance to offer otherwise), and a caller that has to recompute `s/√n` from the
    sample will eventually use `s` instead."""

    mean: float
    stderr: float


def mc_mean(
    process: StateProcess,
    t: float,
    numerics: MonteCarloConfig,
    value: Callable[[NDArray[np.float64]], NDArray[np.float64]],
) -> McEstimate:
    """`E[value(state(t))]` by Monte-Carlo, with its standard error.

    `value` is applied to the WHOLE array, not per path: both present consumers are vectorised
    closed forms, and a per-path Python loop is what made the first MC exposure draft take 73
    seconds for one test file before vectorisation took it to 0.45 (ledger `NG-WATCH-CLOCK`)."""
    states = process.sample_state(t, numerics)
    values = value(states)
    n = values.size
    return McEstimate(
        mean=float(np.mean(values)),
        stderr=float(np.std(values, ddof=1)) / math.sqrt(n) if n > 1 else 0.0,
    )
