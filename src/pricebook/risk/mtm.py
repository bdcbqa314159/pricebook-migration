"""Mark-to-market on SAMPLED states (L5) — the valuation half of exposure.

Split out of `risk/exposure.py` at the ceiling that file set for itself: it had grown four rates
exposure builders, an equity one, and a `singledispatch` table, and the checkpoint named the next
exposure builder as the moment to split. The seam is by **concern**, not by asset class:
*valuing an instrument on sampled states* here, *aggregating those values into a profile or a
report* there. Both the exposure profiles and the XVA report need this, and neither needs the
other.

**Dispatched structurally, never by an `isinstance` ladder** (§1). `singledispatch` is the
stdlib's extensible equivalent of the engine registry ng already uses for pricers, so a new
product registers its own valuation without this module changing — and the AST gate in
`tests/L5/test_greeks.py` enforces that the ladder does not come back.

Every implementation **composes the atoms the matching pricer composes** — HW's bond for the
swap, `black_vec` on the equity forward — so an exposure and the price it is an exposure to
cannot disagree about the contract (§3d).

Provenance:
  quarry: quarry/pricebook/models/mc_exposure.py (the revalue-on-paths CONCEPT; its
          `revalue(paths, step)` callback over a joint path matrix is not carried — ng samples
          marginals, and every consumed functional of that module is marginal)
  source: Hull-White coupon-bond decomposition; Black (1976) on the equity forward
  oracle: the swap MtM reprices HW's own Jamshidian decomposition; the equity MtM reproduces the
          c1 closed form; `EPE − ENE = V₀/df` holds on the samples these produce
  slice:  xva-reporting (B7)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date, timedelta
from functools import singledispatch

import numpy as np
from numpy.typing import NDArray

from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.market.snapshot import DividendYieldKey
from pricebook.market.vol_surface import EquitySurfaceKey, flat_surface
from pricebook.models.black import black_vec, vol_time_measure
from pricebook.models.process import StateProcess, ZeroBondStates
from pricebook.products.equity import EquityForward, EquityOption
from pricebook.foundation import Accrual
from pricebook.products.swap import VanillaSwap


def _swap_mtm_vec(
    swap: VanillaSwap,
    flows: list[tuple[float, float]],
    model: ZeroBondStates,
    t_exp: float,
    r: NDArray[np.float64],
) -> NDArray[np.float64]:
    """A swap's mark at `t_exp` over an array of short rates, **signed by its notional**.

    At an accrual boundary the float leg is worth par, so the fixed-payer's value per unit notional
    is `(1 − P(t,tₙ)) − Σ K·τⱼ·P(t,tⱼ)` — the same coupon bond HW's Jamshidian decomposes, composed
    rather than restated (§3d). The notional carries the sign, so a receiver is the payer's negative
    and netting is plain addition."""
    t_last = flows[-1][0]
    fixed = np.zeros_like(r)
    for t_j, c in flows:
        fixed += c * model.bond_vec(t_exp, t_j, r)
    return swap.notional * (1.0 - model.bond_vec(t_exp, t_last, r) - fixed)


def _remaining_fixed_flows(
    swap: VanillaSwap, expiry: date, model: StateProcess
) -> list[tuple[float, float]]:
    """The fixed leg's `(tⱼ, K·τⱼ)` still outstanding at `expiry`, each `τ` from the leg's own
    convention — so a semi-annual or odd-day-count underlying values correctly."""
    measure = vol_time_measure(model.market.valuation_date)
    flows: list[tuple[float, float]] = []
    for p in swap.fixed_leg.schedule.periods:
        if p.payment_date <= expiry:
            continue
        tau = Accrual(p.accrual_start, p.accrual_end, swap.fixed_leg.day_count).year_fraction()
        flows.append((measure.year_fraction(p.payment_date), swap.fixed_leg.rate * tau))
    return flows


@singledispatch
def _residual_value(
    instrument: object, states: NDArray[np.float64], t: float, process: StateProcess
) -> NDArray[np.float64]:
    """The instrument's MtM at exposure time `t`, vectorised over sampled spot `states`.

    **Dispatched structurally, not by an `isinstance` ladder.** The first draft branched on the
    product type inside the builder, and `test_central_diff_core_has_no_key_type_switch` caught
    it — correctly: §1 forbids exactly that ladder in risk, and the AST test is what makes the
    prohibition real rather than aspirational. `singledispatch` is the stdlib's extensible
    equivalent of the engine registry ng already uses for pricers, so a new equity product
    registers its own valuation without this module changing.

    Each implementation composes the SAME atoms the c1 pricer composes, so the exposure and the
    price cannot disagree about the contract (§3d)."""
    raise TypeError(f"no residual valuation registered for {type(instrument).__name__}")


def _carry_and_df(instrument, t: float, process: StateProcess) -> tuple[float, float, float]:
    """`(τ, growth-to-expiry, df(t→T))` — the three curve facts both products need, read once.
    `e^{r·τ}` comes from the discount-factor ratio, never from a separate `r` (§3d, as
    `equity_forward`)."""
    market = process.market
    tm = vol_time_measure(market.valuation_date)
    tau = tm.year_fraction(instrument.expiry) - t
    curve = market.curves.discount(instrument.currency, None)
    exp_date = market.valuation_date + timedelta(days=round(t * 365.0))
    df_t_to_T = curve.df(instrument.expiry) / curve.df(exp_date)
    q = market.scalars[DividendYieldKey(instrument.underlying)]
    carry = math.exp(-q * tau) / df_t_to_T if tau > 0.0 else 1.0
    return tau, carry, df_t_to_T


@_residual_value.register
def _(
    instrument: EquityForward, states: NDArray[np.float64], t: float, process: StateProcess
) -> NDArray[np.float64]:
    """A forward's MtM: `df(t→T)·(F(t,T) − K)`. **Goes negative**, which is what makes it the
    product that exercises the exposure floor an option cannot."""
    _, carry, df_t_to_T = _carry_and_df(instrument, t, process)
    return df_t_to_T * (states * carry - instrument.strike)


@_residual_value.register
def _(
    instrument: EquityOption, states: NDArray[np.float64], t: float, process: StateProcess
) -> NDArray[np.float64]:
    """An option's MtM: the residual Black value on the forward, discounted — the c1 composition
    evaluated at the sampled spot."""
    tau, carry, df_t_to_T = _carry_and_df(instrument, t, process)
    market = process.market
    vol = flat_surface(market.surfaces[EquitySurfaceKey(instrument.underlying)]).at(
        instrument.expiry, instrument.strike, vol_time_measure(market.valuation_date)
    )
    return df_t_to_T * black_vec(states * carry, instrument.strike, vol, tau, instrument.option_type)


@_residual_value.register
def _(
    instrument: VanillaSwap,
    states: NDArray[np.float64],
    t: float,
    process: ZeroBondStates,
) -> NDArray[np.float64]:
    """A swap's MtM over sampled short rates — the rates arm of the same table the equity
    products register into. Without it the XVA report would be equity-only, and
    `models/mc_exposure.py` would stay unsuperseded for its rates consumer."""
    model = process
    expiry = model.market.valuation_date + timedelta(days=round(t * 365.0))
    flows = _remaining_fixed_flows(instrument, expiry, model)
    if not flows:
        return np.zeros_like(states)
    return _swap_mtm_vec(instrument, flows, model, t, states)


def mtm_samples(
    instrument: object,
    process: StateProcess,
    dates: Sequence[date],
    numerics: MonteCarloConfig,
) -> tuple[tuple[date, NDArray[np.float64]], ...]:
    """Per-date MtM **samples** — the raw distribution every exposure functional is taken from.

    Returning the samples rather than a summary is what makes one simulation serve EPE, ENE, the
    PFE percentiles, peak and effective EPE at once. They are **marginals**: each date is drawn
    under its own forward measure, which is all any of those functionals need. A functional that
    conditions across dates — wrong-way risk — needs joint paths and is deferred with its
    consumer."""
    tm = vol_time_measure(process.market.valuation_date)
    out: list[tuple[date, NDArray[np.float64]]] = []
    for d in dates:
        t = tm.year_fraction(d)
        states = process.sample_state(t, numerics)
        out.append((d, np.asarray(_residual_value(instrument, states, t, process), dtype=float)))
    return tuple(out)
