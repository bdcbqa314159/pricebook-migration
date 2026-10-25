"""SABR smile calibration — fit (α, ρ, ν) to a quoted smile (L3).

Two entry points, one fit. `calibrate_sabr_smile` fits ONE quoted smile; `calibrate_capfloor_sabr`
composes the caplet-vol strip with it to fit a whole CAP surface (a smile per ladder expiry) —
regrouping only, no second fitting path.

A per-family calibrator beside `vol_strip.py`: given a single-expiry `SmileQuote`, fit the three
free SABR parameters (β is FIXED, carried on the spec) by bounded least-squares over the per-strike
vol residual, COMPOSING the SAME `vol_law.sabr_vol` expansion the model and engine read (§3d) — so
the fit is automatically in the model's own law (lognormal / shifted / normal), never in units the
engine does not price in. Failure is a value (invariant 4): a smile outside the law's domain, a
non-converged solve, or a converged-but-unacceptable fit returns `CalibrationFailure`.

The ACCEPTANCE gate (Cowork ruling 1): `converged` is the SOLVER's verdict, not the fit's. Bounded
TRF genuinely converges on a smile no SABR can fit — it finds the best of a bad lot — so a converged
fit whose worst vol residual exceeds `_MAX_VOL_RESIDUAL` (1bp, the quarry's own default) comes back
as a `CalibrationFailure` CARRYING its residuals. A returned-but-flagged result is a foot-gun: the
caller has to remember to look. NOTE the gate is deliberately NOT `SolveConfig.tolerance` — that is
the solver's step/objective xtol (1e-12), a different quantity from an acceptable fit in vol units;
gating on it would reject a round-trip fit that is exact to 8e-11.

§3d F-identity (the load-bearing constraint): the calibrator derives the forward from the model's OWN
projection curve, via the SAME canonical accrual `SABRModel.implied_vol` uses — so the fitted params,
written to a `SabrSurface` and read back by `SABRModel`, reproduce the calibrated smile at exactly the
F priced at, by construction (calibrate-to-quote == price-to-smile).

Provenance:
  quarry: quarry/pricebook/options/sabr.py (sabr_calibrate / calibrate_sabr_smile);
          options/capfloor.py (calibrate_capfloor_sabr — its SYNTHETIC smile shed, see the audit)
  source: Hagan et al. (2002); CLAUDE.md §1 (unified front) · §3d (shared atom, F-identity) · §7bb
  oracle: per-law round-trip seed recovery; reprice identity via SABRModel; out-of-domain
          smile → failure; a contradictory smile → failure (the acceptance gate)
  slice:  sabr-calibrate (T1 slice 21) · multi-law + acceptance gate in sabr-multilaw (slice 22)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, CalibrationResult, SolveConfig
from pricebook.foundation import RateIndex, root_nd
from pricebook.market.building_blocks import forward
from pricebook.calibration.vol_strip import VolCalibrationSpec, strip_caplet_vols
from pricebook.market.quotes import CapQuote, SmileQuote
from pricebook.market.vol_surface import SabrParams, SabrSurface
from pricebook.models.black import vol_time_measure
from pricebook.models.protocols import ImpliedVol
from pricebook.models.vol_law import Lognormal

_PARAM_CAP = 5.0  # α (vol scale) or ν (vol-of-vol) above 500% is unphysical — the box ceiling
_RHO_CAP = 0.9999  # ρ ∈ (−1, 1) open; the box approximates it (a real box, never a penalty term)
_MAX_VOL_RESIDUAL = 1e-4  # 1bp of vol: the ACCEPTANCE gate (the quarry's own max_rmse_bp default)
_MIN_SMILE_POINTS = 3  # (α, ρ, ν) — the same minimum `SmileQuote` enforces, checked before stripping


@dataclass(frozen=True)
class SabrCalibrationSpec:
    """What to fit: the `model` carrying the projection curve AND the vol law (its F and its law are
    what `SABRModel.implied_vol` reads — §3d), the `index` the smile is quoted on, the single-expiry
    `smile`, the FIXED `beta`, and the `solve` config (tolerance / iteration cap, reused verbatim)."""

    model: ImpliedVol
    index: RateIndex
    smile: SmileQuote
    beta: float
    solve: SolveConfig = field(default_factory=SolveConfig)


def calibrate_sabr_smile(
    spec: SabrCalibrationSpec,
) -> tuple[SabrParams, CalibrationResult] | CalibrationFailure:
    """Fit (α, ρ, ν) to `spec.smile` by bounded least-squares (no penalty). Returns the fitted
    `SabrParams` beside a `CalibrationResult`, or `CalibrationFailure` on a degenerate smile /
    non-convergence."""
    market = spec.model.market
    law = spec.model.vol_law  # the SAME law the model prices in — the fit can't be in other units
    index, smile, beta = spec.index, spec.smile, spec.beta
    # F via the SAME atoms SABRModel.implied_vol composes (§3d — ONE canonical accrual, no drift)
    accrual = index.canonical_accrual(smile.expiry)
    try:
        fwd = forward(market.curves.projection(index), accrual)
    except (ValueError, KeyError, ZeroDivisionError) as exc:
        return CalibrationFailure(str(exc))
    if any(not law.defined(fwd, k) for k in smile.strikes):  # the LAW's domain (cf. caplet #15)
        return CalibrationFailure(
            f"forward {fwd} / smile strikes outside the {type(law).__name__} law's domain"
        )
    t = vol_time_measure(market.valuation_date).year_fraction(smile.expiry)

    def residual(x: Sequence[float]) -> list[float]:
        params = SabrParams(x[0], beta, x[1], x[2])
        return [law.sabr_vol(fwd, k, t, params) - mv for k, mv in zip(smile.strikes, smile.vols)]

    atm = min(range(len(smile.strikes)), key=lambda i: abs(smile.strikes[i] - fwd))
    # the α SCALE is the LAW's own fact (σ_ATM·F^{1−β} lognormally, σ_ATM normally) — asking the law
    # keeps the seed correct for a negative forward, where `fwd ** (1−β)` is not even real
    x0 = [law.seed_alpha(smile.vols[atm], fwd, beta), -0.1, 0.3]  # ATM seed (ADAPTED from the quarry)
    bounds = ([1e-8, -_RHO_CAP, 1e-8], [_PARAM_CAP, _RHO_CAP, _PARAM_CAP])
    x, _jac, converged = root_nd(residual, x0, spec.solve.tolerance, spec.solve.max_iterations, bounds)
    if not converged:
        return CalibrationFailure("SABR smile fit did not converge")
    residuals = tuple(residual(x))
    worst = max(abs(r) for r in residuals)
    if worst > _MAX_VOL_RESIDUAL:  # RULING 1: converged ≠ acceptable — a bad fit is a FAILURE value
        return CalibrationFailure(
            f"SABR smile fit converged but missed by {worst * 1e4:.2f}bp of vol "
            f"(limit {_MAX_VOL_RESIDUAL * 1e4:.2f}bp) — no SABR smile fits these quotes",
            residuals=residuals,
        )
    return SabrParams(x[0], beta, x[1], x[2]), CalibrationResult(
        residuals=residuals, converged=True, jacobian=None
    )


@dataclass(frozen=True)
class CapSabrCalibrationSpec:
    """What to fit: the `model` carrying the curves AND the law (its F and its law are what
    `SABRModel.implied_vol` reads — §3d), the `index` the caps fix on, the flat-vol cap `quotes`
    across a (maturity × strike) grid, the FIXED `beta`, and the `solve` config."""

    model: ImpliedVol
    index: RateIndex
    quotes: tuple[CapQuote, ...]
    beta: float
    solve: SolveConfig = field(default_factory=SolveConfig)


def calibrate_capfloor_sabr(
    spec: CapSabrCalibrationSpec,
) -> tuple[SabrSurface, CalibrationResult] | CalibrationFailure:
    """Fit a SABR smile per expiry to a cap surface — **pure composition**, no new fitting machinery:

        cap flat vols (per strike) → `strip_caplet_vols` → caplet vols on the ONE `cap_ladder` grid
                                   → a `SmileQuote` per expiry → `calibrate_sabr_smile`

    So the #10-fixed ladder, the bounded least-squares fit, the 1bp acceptance gate (ruling 1) and
    the F-identity all arrive already paid for; this function only regroups. Returns the
    `SabrSurface` (params per ladder expiry, ready to hand to `SABRModel.for_index`) beside a
    `CalibrationResult` carrying every per-expiry residual, or `CalibrationFailure` (invariant 4).

    The quarry's version instead **invented** its smile — `avg_vol·(1 + 0.1·(K − F)/F)` off a single
    averaged vol, bucketed by `round(tenor·2)/2` — and fitted SABR to that, falling back to
    hardcoded params on any exception. Nothing here is synthetic: every vol fitted is a vol stripped
    from a quoted cap.
    """
    if spec.model.vol_law != Lognormal():
        # the strip produces LOGNORMAL caplet vols (a flat/term `Surface` is a lognormal object), so
        # fitting them under another law would read them in the wrong units — wrong by a factor of F
        return CalibrationFailure(
            f"cap-SABR calibration strips lognormal cap vols; the model's law is "
            f"{type(spec.model.vol_law).__name__} (a law-tagged cap surface is deferred)"
        )
    by_strike: dict[float, list[CapQuote]] = {}
    for q in spec.quotes:
        by_strike.setdefault(q.strike, []).append(q)
    if len(by_strike) < _MIN_SMILE_POINTS:
        return CalibrationFailure(
            f"a {_MIN_SMILE_POINTS}-parameter SABR fit needs ≥{_MIN_SMILE_POINTS} strikes; "
            f"got {len(by_strike)}"
        )
    maturities = {strike: {q.maturity for q in qs} for strike, qs in by_strike.items()}
    if len({frozenset(ms) for ms in maturities.values()}) > 1:
        # a ragged grid would strip different expiry grids per strike, and "the smile at an expiry"
        # would be a different set of strikes at every expiry
        return CalibrationFailure("every strike must be quoted on the same cap maturities")

    # one strip per strike — each is a sequential ladder strip at that strike (§3d: the same
    # `cap_ladder` the L4 pricer composes, so the pillars are the expiries the pricer asks for)
    vols_by_expiry: dict[date, dict[float, float]] = {}
    for strike in sorted(by_strike):
        stripped = strip_caplet_vols(
            VolCalibrationSpec(spec.model, spec.index, tuple(by_strike[strike]), spec.solve)
        )
        if isinstance(stripped, CalibrationFailure):
            return CalibrationFailure(f"strike {strike}: {stripped.reason}", stripped.residuals)
        surface, _ = stripped
        for expiry, vol in zip(surface.expiries, surface.vols):
            vols_by_expiry.setdefault(expiry, {})[strike] = vol

    params: dict[date, SabrParams] = {}
    residuals: list[float] = []
    for expiry in sorted(vols_by_expiry):
        row = vols_by_expiry[expiry]
        strikes = tuple(sorted(row))
        smile = SmileQuote(expiry, strikes, tuple(row[k] for k in strikes))
        fit = calibrate_sabr_smile(
            SabrCalibrationSpec(spec.model, spec.index, smile, spec.beta, spec.solve)
        )
        if isinstance(fit, CalibrationFailure):
            return CalibrationFailure(f"expiry {expiry.isoformat()}: {fit.reason}", fit.residuals)
        fitted, result = fit
        params[expiry] = fitted
        residuals += list(result.residuals)

    return SabrSurface(params), CalibrationResult(tuple(residuals), converged=True, jacobian=None)
