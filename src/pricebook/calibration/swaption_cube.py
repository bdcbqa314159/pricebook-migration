"""The swaption vol-cube calibration — a node-scanning SABR fit over a quoted smile grid (L3).

Pure composition, like `calibrate_capfloor_sabr`: each node's smile goes through the SAME
`calibrate_sabr_smile` (slice 21's bounded least-squares + 1bp acceptance gate) at the forward the
node's `SmileQuote` carries, and the cube is DERIVED from the successes. No new fitting machinery,
no cube type — the cube IS `{SwaptionSurfaceKey → SabrSurface}`, which `SABRModel.swaption_vol`
already reads (slice A, v0.111.0).

Two defects of the quarry's `build_swaption_vol_cube` are structurally impossible here, not merely
tested against:

* **the silent drop.** The quarry wrapped each node's fit in `except Exception: pass`, so a quoted
  node that failed to calibrate vanished; 20 quotes with 5 failures became a 15-node cube with no
  signal, and all-failing became an empty-smile cube that repriced its own ATM backbone perfectly.
  Here the outcome map is keyed by **every quoted node**, so a vanished node cannot be represented
  (ruling B1/B2 — §6's floor rule on this slice's own grid).
* **the stored count.** `calibrated_count`/`quoted_count` are DERIVED from the map, never stored: a
  stored count is itself the proxy §6's second clause forbids, because it can drift from the
  collection it summarises.

Provenance:
  quarry: quarry/pricebook/options/swaption_vol_cube.py (the calibration + node scanner; the smile
          READ crossed in slice A as SABRModel.swaption_vol)
  source: docs/handoffs/spec_slice_B_swaption_cube.md (rulings B1–B4); Hagan et al. (2002)
  oracle: node count / no-silent-drop on a poisoned grid; S-identity per node on a NON-CANONICAL
          (semi-annual) underlying; round-trip; inverter parity; β explicit
  slice:  swaption-cube-calibration (T1 slice B)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Mapping

from pricebook.calibration.calibrate import CalibrationFailure, CalibrationResult, SolveConfig
from pricebook.calibration.sabr_calibrate import SabrCalibrationSpec, calibrate_sabr_smile
from pricebook.market.quotes import SmileQuote
from pricebook.market.vol_surface import SabrParams, SabrSurface, SwaptionSurfaceKey
from pricebook.models.protocols import ImpliedVol

#: One quoted node of the cube: WHICH surface (index + swap tenor) and the smile quoted on it.
#: A plain pair, not a new type — the smile already carries its own expiry and forward (B4), so a
#: wrapper would only relocate them (§6b: one consumer ⇒ concrete).
NodeQuote = tuple[SwaptionSurfaceKey, SmileQuote]

#: The per-node outcome, keyed by the node itself. The value is EXACTLY what the single-smile
#: calibrator returns, so the cube speaks one dialect with it (§3d).
NodeOutcome = tuple[SabrParams, CalibrationResult] | CalibrationFailure
CubeOutcomes = Mapping[tuple[SwaptionSurfaceKey, date], NodeOutcome]


@dataclass(frozen=True)
class SwaptionCubeCalibrationSpec:
    """What to fit: the `model` carrying the vol law the fit must speak (§3d), the quoted `nodes`
    (each a `SwaptionSurfaceKey` + its `SmileQuote`, which carries the forward the ENGINE marks for
    that node — ruling B4), the FIXED `beta`, and the `solve` config.

    `beta` has **no default**: it is a calibration choice that shapes the whole smile, so an
    unstated β is a contract error, not a 0.5 (audit F8, engine invariant 5)."""

    model: ImpliedVol
    nodes: tuple[NodeQuote, ...]
    beta: float
    solve: SolveConfig = field(default_factory=SolveConfig)


def build_swaption_vol_cube(spec: SwaptionCubeCalibrationSpec) -> CubeOutcomes | CalibrationFailure:
    """Fit a SABR smile at every quoted node. Returns the outcome for **every** node, keyed by
    `(surface key, expiry)` — successes as `(SabrParams, CalibrationResult)`, failures as that
    node's `CalibrationFailure` carrying its residuals. Never raises, never drops (B1/B2).

    An EMPTY grid is a `CalibrationFailure`, not an empty cube: a build that examined nothing must
    not report success (§6 floor-on-population — the same rule `verify.py provenance` answers to)."""
    if not spec.nodes:
        return CalibrationFailure("swaption cube calibration needs at least one quoted node")
    outcomes: dict[tuple[SwaptionSurfaceKey, date], NodeOutcome] = {}
    for key, smile in spec.nodes:
        node = (key, smile.expiry)
        if node in outcomes:
            return CalibrationFailure(
                f"node {key.index.id.name} {key.swap_tenor} {smile.expiry.isoformat()} is quoted twice"
            )
        # the SAME fit the caplet surface composes, at the forward THIS node's quote carries (B4)
        outcomes[node] = calibrate_sabr_smile(
            SabrCalibrationSpec(spec.model, smile, spec.beta, spec.solve)
        )
    return outcomes


def swaption_cube(outcomes: CubeOutcomes) -> Mapping[SwaptionSurfaceKey, SabrSurface]:
    """Derive the cube — `{SwaptionSurfaceKey → SabrSurface}`, the shape `SABRModel.swaption_vol`
    reads — from the nodes that calibrated. Failed nodes are simply absent from the surface; they
    are not hidden, because `outcomes` still carries them (that is the point of B2)."""
    params: dict[SwaptionSurfaceKey, dict[date, SabrParams]] = {}
    for (key, expiry), outcome in outcomes.items():
        if isinstance(outcome, CalibrationFailure):
            continue
        fitted, _ = outcome
        params.setdefault(key, {})[expiry] = fitted
    return {key: SabrSurface(rows) for key, rows in params.items()}


def calibrated_count(outcomes: CubeOutcomes) -> int:
    """How many quoted nodes produced an acceptable fit. DERIVED, never stored — a stored count is
    a proxy that can drift from the collection it summarises (§6 second clause)."""
    return sum(1 for o in outcomes.values() if not isinstance(o, CalibrationFailure))
