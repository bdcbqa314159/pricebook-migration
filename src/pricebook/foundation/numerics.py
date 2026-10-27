"""Numerical configuration — the explicit reproducibility knobs (L0).

Engine invariant 5: *all reproducibility knobs arrive in an explicit numerical-config value,
decomposed by method family (≤5 fields each); never a hidden default.* The invariant also records
that the concrete type "lands with the first engine that reads it — Phase 4 deleted the speculative
`NumericalConfig` with its guessed knob names". **This is that landing**, and the first engine is the
CDS mark, whose protection leg is an integral over a grid.

**Two of the four families are here now** — `integration` (the CDS protection leg) and
`monte_carlo` (the MC exposure profile). §3b names the eventual decomposition
`(monte_carlo, lattice, integration, solver)`; `lattice` and `solver` still have no consumer, so
§6b keeps them out. The aggregate wrapping the families likewise waits: each consumer today takes
exactly the one family it reads, which is stricter than a bag it must index into, and the parameter
is already named `numerics` so only the *type* widens when an aggregate is justified.

Provenance:
  quarry: quarry/pricebook/core/numerical_config.py (the knob-bag concept; its shape is NOT carried —
          the quarry's was one flat config, which §3b forbids)
  source: CLAUDE.md engine invariant 5; §3b (decompose by method family, ≤5 fields each)
  oracle: a CDS priced without it is a PricingFailure, never a guessed grid; the grid is observable
          (two grids give two marks)
  slice:  credit-cds-mark (B6 slice 2)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrationConfig:
    """The quadrature family's knobs. `steps_per_year` is the uniform grid density for an integral
    taken over calendar time — the CDS protection leg's `∫ df·(−dQ)` is the first consumer.

    **There is no default.** A guessed grid is exactly the hidden reproducibility knob invariant 5
    forbids, and for the protection leg it is not even monotone in accuracy: `CurveHandle.df` takes a
    **date**, so past roughly monthly steps a one-day step's midpoint floors to its start and `df` is
    read half a day early at every step. See `building_blocks.protection_leg` for the measurement."""

    steps_per_year: int

    def __post_init__(self) -> None:
        if self.steps_per_year < 1:
            raise ValueError(f"steps_per_year must be a positive integer; got {self.steps_per_year}")


@dataclass(frozen=True)
class MonteCarloConfig:
    """The simulation family's knobs: how many `paths`, and the RNG `seed`.

    **Neither has a default**, and the seed is the sharper of the two: without it a run cannot be
    repeated, so a defaulted seed is not merely a hidden knob (invariant 5) but a breach of
    referential transparency (invariant 1) — identical inputs must give identical output, and an
    unseeded sampler makes "identical inputs" impossible to state.

    **No time grid.** Hull-White's short rate is exactly Gaussian under each exposure date's own
    forward measure, so dates are sampled **directly** with no stepping and no discretisation bias;
    a grid would be a knob that cannot change the answer. A model whose transition is *not* exact
    would need one — it arrives with that model, not speculatively here (§6b). Variance reduction
    (antithetic, control variates) likewise waits for a performance consumer."""

    paths: int
    seed: int

    def __post_init__(self) -> None:
        if self.paths < 1:
            raise ValueError(f"paths must be a positive integer; got {self.paths}")
