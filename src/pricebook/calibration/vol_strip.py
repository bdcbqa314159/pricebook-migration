"""Caplet-vol stripping — the first SOLVED volatility surface (L3).

The vol analogue of the curve bootstrap, in a new family: given ascending flat cap vols, strip
each quote interval's MARGINAL caplet vol so the caps reprice — a sequential 1-D Brent solve per
quote. It COMPOSES the same atoms the L4 caplet engine composes — `cap_ladder` (which caplets a cap
IS), the `Lognormal` law's undiscounted price, `forward`, and `df` — never a private caplet formula
and never the L4 engine itself (L3 ⊥ L4, §3d). **Audit #10 is discharged here:** the ladder comes
from the cap's own schedule, so the caplet grid is no longer forced to equal the quote grid, and
several new caplets in one quote interval share that interval's single marginal vol. A
per-family entry (a `Surface` is a different target than a `CurveSet`; vols are downstream of a
finished curve), reusing `SolveConfig` verbatim. Failure is a value (invariant 4): an infeasible
marginal (target outside the vol-attainable range) returns `CalibrationFailure`.

Provenance:
  quarry: quarry/pricebook/options/vol_calibration.py; options/capfloor.py (strip_caplet_vols)
  source: CLAUDE.md §1 (unified front over per-family solvers) · §3d (shared atoms); doc 22 (A) fork
  oracle: flat cap strips to a flat caplet-vol curve exactly; each cap reprices to its flat quote
          THROUGH the L4 engine on a finer caplet grid; a 5Y quote set strips 19 pillars, not 4
  slice:  caplet-vol-strip (C2 slice 3) · #10 ladder fix in capfloor (T1 slice 23)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from pricebook.calibration.calibrate import CalibrationFailure, CalibrationResult, SolveConfig
from collections.abc import Sequence

from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    RateIndex,
    RollRule,
    ScheduleTerms,
    StubType,
    TimeMeasure,
    build_schedule,
    invert_increasing,
)
from pricebook.market.building_blocks import forward
from pricebook.market.quotes import CapQuote
from pricebook.market.vol_surface import Surface
from pricebook.models.protocols import CalibratedModel
from pricebook.models.vol_law import Lognormal
from pricebook.products.option import CapFloor, Caplet, OptionType, cap_ladder

_ACT365F = DayCountConvention.ACT_365_FIXED
_VOL_CAP = 5.0  # a caplet vol above 500% is unphysical — treat the pillar as infeasible


@dataclass(frozen=True)
class VolCalibrationSpec:
    """What to strip: the `model` carrying the calibrated curves (A1 — the strip reads its
    curves, the vols are downstream of a finished curve), the `index` the caplets fix on, the
    ascending flat-cap `quotes`, and the `solve` config (reused verbatim — SEQUENTIAL/Brent)."""

    model: CalibratedModel
    index: RateIndex
    quotes: tuple[CapQuote, ...]
    solve: SolveConfig = field(default_factory=SolveConfig)


@dataclass(frozen=True)
class _Leg:
    """One caplet's fixed inputs (everything but the vol) — the undiscounted Black annuity
    `pay_df·τ` and the forward/strike/expiry it is struck on."""

    annuity: float  # pay_df · τ
    forward: float
    strike: float
    expiry_time: float

    def pv(self, vol: float) -> float:
        # the LOGNORMAL law explicitly: a flat/term `Surface` is a lognormal object (the only model
        # that reads one, `BlackModel`, carries `Lognormal` as a fixed law), so stripping in another
        # law would produce vols nothing can consume. Composed through the law, not a bare `black`
        # call, so it is the same composition the L4 pricer performs (§3d). A law-TAGGED term
        # structure is deferred to its first consumer (`OPEN.md`).
        return self.annuity * Lognormal().price(
            self.forward, self.strike, vol, self.expiry_time, OptionType.CALL
        )


def _solve_vol(legs: Sequence[_Leg], target_pv: float) -> float:
    """The ONE marginal vol reproducing `target_pv` across `legs` — every new caplet in a quote
    interval shares it (piecewise-constant marginal vol, the standard strip). The sum is monotonic
    increasing in the vol from the intrinsic (`vol→0`) to the undiscounted forward (`vol→∞`), so this
    is the generic monotone inverse: `invert_increasing` brackets it and reports an unattainable
    target instead of returning a consolation value. That bracket-expanding search used to be
    hand-rolled here; it is shared with the implied-vol inversion now (§3d — the same search, so the
    same atom), with the same floor, seed and cap it always used."""
    return invert_increasing(
        lambda vol: sum(leg.pv(vol) for leg in legs), target_pv, 1e-9, 0.05, _VOL_CAP
    )


def _leg_for(caplet: Caplet, spec: VolCalibrationSpec, tm: TimeMeasure) -> _Leg:
    """One ladder caplet's fixed inputs, composed from the SAME `forward`/`df` atoms the L4 pricer
    composes (§3d — the strip never imports the engine, L3 ⊥ L4)."""
    market = spec.model.market
    accrual = caplet.accrual
    return _Leg(
        annuity=market.curves.discount(spec.index.id.currency).df(accrual.end)
        * accrual.year_fraction(),
        forward=forward(market.curves.projection(spec.index), accrual),
        strike=caplet.strike,
        expiry_time=tm.year_fraction(accrual.start),
    )


def cap_for_quote(quote: CapQuote, spec: VolCalibrationSpec) -> CapFloor:
    """The cap a quote describes: from the valuation date to `quote.maturity`, stepping at the index
    tenor, anchored FORWARD on the start (`SHORT_BACK`) so each maturity's ladder EXTENDS the
    previous one's — which is what makes the sequential strip well-posed. Exposed because the
    SABR-cap calibration builds the same caps (one definition, §3d)."""
    terms = ScheduleTerms(
        Frequency(spec.index.id.tenor), RollRule(calendar=None), StubType.SHORT_BACK
    )
    schedule = build_schedule(spec.model.market.valuation_date, quote.maturity, terms)
    return CapFloor(spec.index, schedule, quote.strike, 1.0, OptionType.CALL)


def strip_caplet_vols(
    spec: VolCalibrationSpec,
) -> tuple[Surface, CalibrationResult] | CalibrationFailure:
    """Strip caplet vols from the flat cap quotes. Sequential over quotes: each quote's cap, priced
    at its flat vol, fixes the PV its whole LADDER must reproduce; the caplets it adds beyond the
    previous quote's ladder share ONE marginal vol, solved for. Returns the term-structure `Surface`
    (one pillar per ladder caplet) beside a `CalibrationResult`; an infeasible pillar, an
    inconsistent quote grid, or mixed strikes return `CalibrationFailure` (invariant 4).

    **Audit #10 (discharged here).** This used to build ONE caplet per quote — a "2Y cap" was a
    single caplet fixing at 2Y rather than the 7-caplet ladder it is, silently forcing the caplet
    grid to equal the quote grid. The ladder now comes from `cap_ladder`, the same atom the L4 pricer
    composes, so the stripped surface is indexed on exactly the expiries the pricer asks for.
    """
    quotes = sorted(spec.quotes, key=lambda q: q.maturity)
    if not quotes:
        return CalibrationFailure("no cap quotes to strip")
    strikes = {q.strike for q in quotes}
    if len(strikes) > 1:
        # a `Surface` has no strike axis, so stripping quotes at different strikes into one surface
        # would silently blend smiles — the same class of error as #10 (fit a smile per expiry with
        # `calibrate_capfloor_sabr` instead, which strips one strike at a time)
        return CalibrationFailure(
            f"all cap quotes must share one strike (a Surface has no strike axis); got {sorted(strikes)}"
        )
    tm = TimeMeasure(spec.model.market.valuation_date, _ACT365F)

    legs: list[_Leg] = []  # every ladder caplet seen so far, in expiry order
    vols: list[float] = []  # its stripped vol (the marginal of the interval it fell in)
    expiries: list[date] = []
    cap_pvs_flat: list[float] = []  # each quote's cap PV at its own flat vol (for the residuals)
    for q in quotes:
        ladder = cap_ladder(cap_for_quote(q, spec))
        try:
            ladder_legs = [_leg_for(c, spec, tm) for c in ladder]
        except (ValueError, KeyError, ZeroDivisionError) as exc:
            return CalibrationFailure(f"cap {q.maturity.isoformat()}: {exc}")
        off_grid = [
            c.accrual for c in ladder if c.accrual != spec.index.canonical_accrual(c.accrual.start)
        ]
        if off_grid:
            # the L4 pricer refuses a non-canonical optionlet (ruling 2), so a ladder carrying one
            # (a stub from an off-grid quote maturity) would strip vols nothing can price. Refuse
            # here, where the grid is chosen — strip and pricer agree on the ladder or neither runs.
            return CalibrationFailure(
                f"cap {q.maturity.isoformat()} is off the {spec.index.name} caplet grid: "
                f"{len(off_grid)} period(s) are not the index's canonical accrual"
            )
        if len(ladder_legs) <= len(legs):
            # this quote adds no caplet the previous quotes did not already fix: its flat vol and
            # theirs both claim the same marginal, so the system is over-determined. The quarry
            # skipped the quote silently; refuse it instead.
            return CalibrationFailure(
                f"cap {q.maturity.isoformat()} adds no new caplet to the ladder "
                f"(quote grid finer than the {spec.index.id.tenor} caplet grid)"
            )
        if ladder_legs[: len(legs)] != legs:
            # a longer cap's ladder must EXTEND a shorter one's, or "the marginal caplets" is not
            # even well defined (it would silently re-strip earlier expiries)
            return CalibrationFailure(
                f"cap {q.maturity.isoformat()}: its ladder does not extend the previous quote's"
            )
        # the flat quote prices the WHOLE cap; the marginal is what the already-stripped part leaves
        cap_pv_flat = sum(leg.pv(q.flat_vol) for leg in ladder_legs)
        stripped_pv = sum(leg.pv(v) for leg, v in zip(legs, vols))
        new_legs = ladder_legs[len(legs) :]
        try:
            marginal = _solve_vol(new_legs, cap_pv_flat - stripped_pv)
        except (ValueError, ZeroDivisionError) as exc:
            return CalibrationFailure(f"cap {q.maturity.isoformat()}: {exc}")
        legs = ladder_legs
        vols += [marginal] * len(new_legs)
        expiries += [c.accrual.start for c in ladder[len(expiries) :]]
        cap_pvs_flat.append(cap_pv_flat)

    # residuals: each cap repriced with the stripped vols vs its flat-quote PV (≈0 by construction)
    residuals: list[float] = []
    for q, cap_pv_flat in zip(quotes, cap_pvs_flat):
        n = len(cap_ladder(cap_for_quote(q, spec)))
        residuals.append(sum(legs[j].pv(vols[j]) for j in range(n)) - cap_pv_flat)

    surface = Surface(tuple(vols), tuple(expiries))
    converged = all(abs(r) < spec.solve.tolerance for r in residuals)
    return surface, CalibrationResult(tuple(residuals), converged=converged, jacobian=None)
