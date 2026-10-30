"""Hull-White 1F — the calibrated short-rate model, static (L3).

    dr = (θ(t) − a·r) dt + σ dW

**θ(t) is not a free parameter.** It is pinned by the initial discount curve, which is what makes HW
reprice that curve *by construction* rather than by fit — so the term-structure oracle is an exact
identity (1e-12), not a fit quality. The analytic content:

    B(t,T)    = (1 − e^{−a(T−t)}) / a
    ln A(t,T) = ln(P(0,T)/P(0,t)) + B(t,T)·f(0,t) − (σ²/4a)(1 − e^{−2at})·B(t,T)²
    P(t,T; r) = A(t,T)·e^{−B(t,T)·r}

**Simulation is deliberately absent.** §6b: its first consumer is the MC-exposure slice, so it
arrives with MC rather than speculatively here. A calibrated closed-form HW is complete and
oracle-able on its own — curve reprice, zero-bond option, Jamshidian swaption, and the σ→0 / a→0
limits are all rung-1 — so this is not a half-built abstraction.

**HW satisfies `SwaptionVol` like any other model, not as a special case.** It prices a European
swaption in closed form (Jamshidian) and then **inverts that price to a Black vol** through slice
24's law-generic inverter, so the engine's existing Black path reproduces the HW price exactly. The
engine never learns that HW exists: structural dispatch, no `isinstance` (§1). And the underlying is
the engine's own `S = float_leg_pv/rpv01` — the shared atom, never a re-derivation (§3d), which is
what the cross-model oracle checks.

Provenance:
  quarry: quarry/pricebook/models/hull_white.py (the A/B closed forms are mined for CONTENT; its
          trinomial-tree shape is not carried — the tree is a numerical method, deferred with MC)
  source: Hull & White (1990) "Pricing Interest-Rate-Derivative Securities"; Brigo & Mercurio §3.3
          (the A/B form and Jamshidian's decomposition); Jamshidian (1989)
  oracle: P_HW(0,T) == curve DF to 1e-12 at every pillar and every (a, σ); zero-bond call/put parity;
          swaption payer/receiver parity against the linear atoms; the engine reproduces HW's own
          Jamshidian price to 1e-9 for ANNUAL and SEMI-ANNUAL underlyings alike (the §3d identity —
          the semi-annual leg of it is what the 381bp reconstruction used to break); σ→0, a→0 limits
  slice:  hull-white (B7 prerequisite — the first simulatable dynamics, static half);
          swaption-price-capability (v0.129.0 — HW became a `SwaptionPrice`, not a `SwaptionVol`)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from numpy.typing import NDArray

from pricebook.foundation.day_count import DayCountConvention
from pricebook.foundation.distributions import norm_cdf
from pricebook.foundation.money import Currency
from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.foundation.rate_index import RateIndex
from pricebook.foundation.solvers import brent
from pricebook.foundation.tenor import Tenor
from pricebook.market.building_blocks import float_leg_pv, rpv01
from pricebook.market.snapshot import MarketSnapshot
from pricebook.models.implied_vol import implied_vol
from pricebook.models.vol_law import Lognormal, VolLaw
from pricebook.products.option import OptionType
from pricebook.products.swap import VanillaSwap

#: Window for the instantaneous-forward difference quotient, in years. One day is the finest a
#: `df(date)` curve can resolve (cf. NG-DEFER-DF-CONTINUOUS), so f(0,t) is read at that resolution.
_DF_WINDOW = 1.0 / 365.0
#: Bracket for Jamshidian's `r*`. Wide enough for distressed and negative-rate regimes alike; the
#: solve fails as a value outside it rather than returning a bracket end.
_R_STAR_BRACKET = (-0.50, 1.00)


@dataclass(frozen=True)
class HullWhite:
    """HW-1F calibrated to the snapshot's discount curve for `currency`, with constant `a` and
    `sigma`. Term-structure `sigma(t)` is deferred (§6b — the quarry started constant too, and a
    term structure needs a consumer that quotes more than one expiry's vol)."""

    market: MarketSnapshot
    a: float
    sigma: float
    currency: Currency

    def __post_init__(self) -> None:
        if self.a <= 0.0:
            raise ValueError(
                f"Hull-White mean reversion must be positive; got {self.a}. (a → 0 is the Ho-Lee "
                "limit, which `b()` handles as a limit — it is not an admissible parameter.)"
            )
        if self.sigma < 0.0:
            raise ValueError(f"Hull-White sigma must be non-negative; got {self.sigma}")

    # ── the capability the engine dispatches on ───────────────────────────────────────────
    #
    # HW satisfies `SwaptionPrice`, NOT `SwaptionVol`, and that is the whole correction of this
    # slice. `SwaptionVol` is keyed by `(index, expiry, swap_tenor, strike)` — right for a model
    # that reads a surface, wrong for one that prices a contract: Jamshidian needs the underlying's
    # whole coupon flow set, which the key cannot carry. Forced through it, HW had to reconstruct a
    # swap, and the reconstruction was wrong by **381bp** on a semi-annual underlying. The
    # reconstruction, its S-identity guard, and the Black-vol inversion are all **deleted** — there
    # is nothing left to guess, so the defect is unwritable rather than detected.

    # ── the StateProcess capability (c2) ──────────────────────────────────────────────────
    def sample_state(self, t: float, numerics: MonteCarloConfig) -> NDArray[np.float64]:
        """`r(t)` under the `t`-forward measure: Gaussian, mean `f(0,t)`, variance
        `σ²(1 − e^{−2at})/(2a)`. **Exact** — no time stepping, so MC's only error is statistical.

        The mean being the *instantaneous forward* is an identity, not an approximation: the
        `α(t)` shift that fits the curve and the forward-measure drift adjustment cancel, because
        `(1 − e^{−aT}) − (1 − e^{−2aT})/2 ≡ (1 − e^{−aT})²/2`. Dropping the drift adjustment is
        the classic error here and would bias every exposure by `σ²B(0,t)²/2`.

        **Moved here from `risk/exposure.py` in c2** — the dynamics owns its own sampler. L5 was
        reaching into `_instantaneous_forward` and `sigma` to build it, which is the layer below
        being read through its privates; now L5 depends on the `StateProcess` capability instead.
        The arithmetic and the seeding are unchanged, which is why the 140-point exposure capture
        is byte-identical across the refactor.

        Seeded per call *and per date* from the config's seed, so a profile is reproducible
        byte-identically (invariant 1) while different dates do not share draws."""
        if self.sigma == 0.0 or t <= 0.0:
            return np.full(numerics.paths, self._instantaneous_forward(t))
        return self.state_from_normal(t, self.normal_draws(t, numerics))

    def normal_draws(self, t: float, numerics: MonteCarloConfig) -> NDArray[np.float64]:
        """The idiosyncratic standard-normal draws for date `t`, seeded per date so a profile is
        reproducible byte-identically (invariant 1) while dates do not share draws. Exposed so a
        **correlated** sampler can reuse the identical stream as its own `W` — which is what makes
        the ρ→0 case of wrong-way risk an exact identity rather than a statistical agreement."""
        return np.random.default_rng((numerics.seed, round(t * 1_000_000))).standard_normal(
            numerics.paths
        )

    def state_from_normal(self, t: float, z: NDArray[np.float64]) -> NDArray[np.float64]:
        """`r(t) = f(0,t) + √(σ²(1−e^{−2at})/(2a))·z` — the transition as a pure function of its
        driver, which is the factoring the correlated sampler composes.

        **Costs ≤1.4e-17 relative against the previous `rng.normal(mean, sd)` call** (numpy's
        `normal` does not associate identically to `mean + sd·standard_normal`), so the landed MC
        exposure baseline shifts in its last digit. Taken deliberately: the alternative is two
        mappings from the driver to the state, which is the atom-re-derived smell §3d forbids and
        would make ρ→0 agreement a coincidence of two formulas instead of an identity. Same trade
        the variable-notional slice made for `weighted_annuity` at 2.9e-17 of notional."""
        mean = self._instantaneous_forward(t)
        if self.sigma == 0.0 or t <= 0.0:
            return np.full(np.shape(z), mean)
        var = self.sigma**2 * (1.0 - math.exp(-2.0 * self.a * t)) / (2.0 * self.a)
        return mean + math.sqrt(var) * z

    def bond_vec(
        self, t: float, maturity: float, states: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """`P(t,T; r)` over an ARRAY of short rates — the `ZeroBondStates` capability.

        The same closed form `bond` evaluates for one rate: `log A` and `B` are curve-and-
        parameter facts independent of `r`, so they are computed once per maturity and the path
        dimension stays in numpy (§3d — one formula, two call shapes, exactly as `black_vec` is
        to `black`).

        **Moved here from `risk/exposure.py`**, which was building it out of `_log_a` — a private
        of this class read from L5. Second instance of that reach in two slices (the first was
        `sample_state`), and both were dragged out by declaring the capability rather than by a
        dependency check: `acyclic` and `layers` see the module edge, not the privacy."""
        return np.exp(self._log_a(t, maturity) - self.b(t, maturity) * states)

    # ── the closed forms ──────────────────────────────────────────────────────────────────
    @property
    def r0(self) -> float:
        """`r(0) = f(0,0)`, the instantaneous forward at the short end — HW's initial state."""
        return self._instantaneous_forward(0.0)

    def b(self, t: float, maturity: float) -> float:
        """`B(t,T) = (1 − e^{−a(T−t)})/a`. For very small `a` the closed form divides by a vanishing
        number, so the series limit `T − t` (Ho-Lee) is used instead — the limit is exact to the
        order kept, and the alternative is catastrophic cancellation."""
        dt = maturity - t
        if dt <= 0.0:
            return 0.0
        if self.a * dt < 1e-6:
            return dt * (1.0 - 0.5 * self.a * dt)  # the two-term expansion of (1 − e^{−a·dt})/a
        return (1.0 - math.exp(-self.a * dt)) / self.a

    def bond(self, t: float, maturity: float, r: float) -> float:
        """`P(t,T; r) = A(t,T)·e^{−B(t,T)·r}`. At `t = 0, r = r0` this returns the curve's own DF to
        machine precision — the fit is an identity, not an approximation."""
        return math.exp(self._log_a(t, maturity) - self.b(t, maturity) * r)

    def zero_bond_option(
        self, expiry: float, maturity: float, strike: float, kind: OptionType
    ) -> float:
        """A European option at `expiry` on the zero-coupon bond maturing at `maturity`.

        Gaussian rates make the bond lognormal under the `expiry`-forward measure, so this is Black
        with `σ_P = σ·B(expiry, maturity)·√((1 − e^{−2a·expiry})/(2a))` — the integrated bond vol.
        At `σ = 0` it collapses to the discounted intrinsic, which is the limit oracle."""
        p_t = self.bond(0.0, expiry, self.r0)
        p_s = self.bond(0.0, maturity, self.r0)
        vol = self._bond_vol(expiry, maturity)
        if vol <= 0.0:  # deterministic rates: the discounted intrinsic
            intrinsic = (p_s / p_t - strike) if kind is OptionType.CALL else (strike - p_s / p_t)
            return p_t * max(intrinsic, 0.0)
        h = math.log(p_s / (strike * p_t)) / vol + 0.5 * vol
        if kind is OptionType.CALL:
            return p_s * norm_cdf(h) - strike * p_t * norm_cdf(h - vol)
        return strike * p_t * norm_cdf(vol - h) - p_s * norm_cdf(-h)

    def swaption_price(self, swap: VanillaSwap, expiry: date, kind: OptionType) -> float:
        """A European swaption by **Jamshidian decomposition**.

        At expiry a payer swap is worth `1 − CB`, where `CB` is the coupon bond paying the fixed
        leg plus notional — so a payer swaption is a PUT on that bond struck at par. `P(T,tᵢ)` is
        monotone decreasing in `r`, hence so is `CB`, hence `{CB < 1} = {r > r*}` for the single
        `r*` where `CB(r*) = 1`. Striking each zero-bond option at `P(T,tᵢ; r*)` therefore turns one
        option on a sum into a **sum of options** with no approximation.

        Returns the value per the swap's notional, undiscounted beyond the bond prices themselves."""
        t_exp = self._years(expiry)
        if t_exp <= 0.0:
            return 0.0
        flows = self._coupon_flows(swap, expiry)
        if not flows:
            return 0.0
        r_star = self._r_star(flows, t_exp)
        leg = OptionType.PUT if kind is OptionType.CALL else OptionType.CALL
        total = 0.0
        for t_i, c_i in flows:
            strike_i = self.bond(t_exp, t_i, r_star)
            total += c_i * self.zero_bond_option(t_exp, t_i, strike_i, leg)
        return abs(swap.notional) * total

    # ── internals ─────────────────────────────────────────────────────────────────────────
    def _discount(self):
        return self.market.curves.discount(self.currency)

    def _years(self, d: date) -> float:
        return self._measure().year_fraction(d)

    def _measure(self):
        return self._discount().time_measure

    def _df(self, t: float) -> float:
        """The curve's own DF at year-fraction `t`, reached through `df(date)`."""
        measure = self._measure()
        anchor = measure.anchor
        return self._discount().df(anchor + timedelta(days=round(t * 365.0)))

    def _log_a(self, t: float, maturity: float) -> float:
        """`ln A(t,T)` — the term that carries the curve, and the reason the fit is exact."""
        if maturity <= t:
            return 0.0
        df_t = self._df(t) if t > 0.0 else 1.0
        df_T = self._df(maturity)
        b = self.b(t, maturity)
        f_t = self._instantaneous_forward(t)
        decay = 1.0 - math.exp(-2.0 * self.a * t)
        return math.log(df_T / df_t) + b * f_t - (self.sigma**2 / (4.0 * self.a)) * decay * b * b

    def _instantaneous_forward(self, t: float) -> float:
        """`f(0,t) = −∂ ln P(0,t)/∂t`, by a one-day forward difference — the finest a `df(date)`
        curve resolves (NG-DEFER-DF-CONTINUOUS names the sub-day gap)."""
        lo = self._df(t) if t > 0.0 else 1.0
        hi = self._df(t + _DF_WINDOW)
        return -(math.log(hi) - math.log(lo)) / _DF_WINDOW

    def _coupon_flows(self, swap: VanillaSwap, expiry: date) -> list[tuple[float, float]]:
        """The coupon bond's flows `(tᵢ, cᵢ)`: the fixed leg's `K·τᵢ`, with the notional added to
        the final one. Each `τ` comes from the leg's own convention, so a semi-annual or odd
        day-count underlying decomposes correctly (slice A's lesson)."""
        from pricebook.foundation.day_count import Accrual

        sched = swap.fixed_leg.schedule
        day_count: DayCountConvention = swap.fixed_leg.day_count
        flows: list[tuple[float, float]] = []
        for p in sched.periods:
            if p.payment_date <= expiry:
                continue
            tau = Accrual(p.accrual_start, p.accrual_end, day_count).year_fraction()
            flows.append((self._years(p.payment_date), swap.fixed_leg.rate * tau))
        if flows:
            t_last, c_last = flows[-1]
            flows[-1] = (t_last, c_last + 1.0)
        return flows

    def _r_star(self, flows: list[tuple[float, float]], t_exp: float) -> float:
        """The `r` at which the coupon bond is worth par. Monotone decreasing in `r`, so a bracketed
        solve is exact and needs no fallback; outside the bracket it raises rather than returning an
        end (a bracket end is a non-solution, and §5 forbids silent ones)."""

        def residual(r: float) -> float:
            return sum(c * self.bond(t_exp, t_i, r) for t_i, c in flows) - 1.0

        lo, hi = _R_STAR_BRACKET
        return brent(residual, lo, hi)

    def _bond_vol(self, expiry: float, maturity: float) -> float:
        """`σ_P = σ·B(T,S)·√((1 − e^{−2aT})/(2a))` — the integrated volatility of `P(T,S)`."""
        if self.sigma == 0.0 or expiry <= 0.0:
            return 0.0
        decay = (1.0 - math.exp(-2.0 * self.a * expiry)) / (2.0 * self.a)
        return self.sigma * self.b(expiry, maturity) * math.sqrt(decay)
