"""Wrong-way risk (L5) — exposure and default correlated, through the SAME `cva`.

Unilateral CVA is, in general,

    CVA = LGD · Σ E[ (V(tᵢ))⁺ | default in (tᵢ₋₁, tᵢ] ] · ΔQ(tᵢ)

and independence is what makes the conditional expectation equal the unconditional one — which is
*exactly* ng's existing `LGD · Σ EE(tᵢ)·ΔQ(tᵢ)`.

**So the profile type does not change, and that is the whole design.** The spec anticipated a
"conditional-exposure profile, richer than `(date, EE)`" and flagged it as a possible contract
question. It is not one: the generalization is in **how `EE` is computed**, not in its shape.
`(date, EE)` already is the general form, the marginal profile is this one at ρ=0, and the same
`cva` consumes both. There is no second CVA and no new vocabulary type.

**The sign convention, stated because it is the classic WWR error.** The default driver is signed
so that **larger means EARLIER default**:

    Z_default = −Φ⁻¹(F(τ)),   F = 1 − Q the default CDF

so an early default (small `F`, very negative `Φ⁻¹`) gives a large positive `Z_default`. With that
signing, **ρ > 0 is wrong-way by construction** — adverse correlation, exposure high exactly when
the counterparty fails — and ρ < 0 is right-way. Without fixing the signing in the *driver*, "ρ > 0
is wrong-way" is a claim about a parametrisation rather than about economics, and the sign is
exactly what no magnitude check can catch.

**The copula, and why ρ→0 is an identity rather than a coincidence.** A Gaussian copula ties the
exposure driver to the default-timing driver:

    Z_exposure = ρ·Z_default + √(1−ρ²)·W

Default lands in `(tᵢ₋₁, tᵢ]` exactly when `Z_default` falls in the interval
`(Φ⁻¹(1−Q(tᵢ₋₁)), Φ⁻¹(1−Q(tᵢ))]`, so the conditional expectation is taken by drawing
`Z_default` from the **truncated** normal on that interval (exactly, by inverse-CDF) and `W` from
the *same seeded stream the marginal sampler uses*. At ρ=0 the first term vanishes,
`Z_exposure = W`, and the states are the identical draws — so the conditional profile reproduces
the marginal one to floating point with **no `if rho == 0` anywhere**. An implementation that
special-cased zero would make the anchor oracle vacuous, which is the failure mode this project
keeps finding; a test asserts on the AST that it does not.

Provenance:
  quarry: quarry/pricebook/models/gbm.py (`GBMGenerator`, the stepped joint-path generator) and
          quarry/pricebook/statistics/copulas.py (the Gaussian-copula CONTENT). Neither shape is
          carried: ng conditions analytically on the default interval rather than stepping a grid
          and filtering paths, which is why the ρ=0 case is exact instead of a subsample.
  source: Gregory, *The xVA Challenge*, ch. 15 (wrong-way risk); Li (2000) Gaussian copula for
          the default-time link; Hull & White (2012) on CVA with correlated exposure
  oracle: ρ→0 reproduces the marginal profile and the marginal CVA to 1e-12 (the generalization
          identity); wrong-way correlation raises CVA and right-way lowers it, monotone in ρ;
          the conditional profile itself moves with ρ; correlation bump-consistency
  slice:  wwr-joint-paths (B7)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

import numpy as np
from numpy.typing import NDArray

from pricebook.foundation import PricingFailure
from pricebook.foundation.distributions import norm_cdf, norm_ppf, norm_ppf_vec
from pricebook.foundation.numerics import MonteCarloConfig
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.building_blocks import ProtectionWindow
from pricebook.market.snapshot import CorrelationKey
from pricebook.market.survival_curve import SurvivalHandle
from pricebook.models.black import vol_time_measure
from pricebook.models.process import StateProcess
from pricebook.products.equity import EquityForward, EquityOption
from pricebook.risk.mtm import _residual_value
from pricebook.risk.xva import ExposureProfile


def wwr_exposure_profile(
    instrument: EquityOption | EquityForward,
    process: StateProcess,
    entity: ReferenceEntity,
    dates: Sequence[date],
    numerics: MonteCarloConfig,
) -> ExposureProfile | PricingFailure:
    """`EE(tᵢ) = df(0,tᵢ)·E[(V(tᵢ))⁺ | default in (tᵢ₋₁, tᵢ]]` — the exposure a defaulting
    counterparty actually leaves behind.

    Returns the **same** `(date, EE)` profile every other builder returns, discounted to today, so
    `cva` consumes it unchanged and the marginal profile is this one at ρ=0.

    Reads the correlation from the snapshot (`CorrelationKey(entity, factor)`) rather than taking
    it as an argument: it is market state that risk bumps, and a parameter here could not be
    bumped through `ScalarBump` (§3c)."""
    market = process.market
    curve = market.curves.discount(instrument.currency, None)
    survival = market.curves.survival(entity)
    rho = market.scalars[CorrelationKey(entity, instrument.underlying)]
    if not -1.0 <= rho <= 1.0:
        raise ValueError(f"correlation must lie in [-1, 1]; got {rho}")

    tm = vol_time_measure(market.valuation_date)
    out: list[tuple[date, float]] = []
    prev = market.valuation_date
    try:
        for d in dates:
            t = tm.year_fraction(d)
            window = ProtectionWindow(prev, d)  # the window default may land in
            z = _correlated_driver(process, window, rho, survival, numerics)
            values = _residual_value(instrument, process.state_from_normal(t, z), t, process)
            out.append((d, curve.df(d) * float(np.mean(np.maximum(values, 0.0)))))
            prev = d
    except (ValueError, KeyError, ZeroDivisionError) as exc:
        return PricingFailure(f"WWR exposure: {exc}")
    return tuple(out)


def _correlated_driver(
    process: StateProcess,
    window: ProtectionWindow,
    rho: float,
    survival: SurvivalHandle,
    numerics: MonteCarloConfig,
) -> NDArray[np.float64]:
    """`Z_exposure = ρ·Z_default + √(1−ρ²)·W`, with `Z_default` truncated to the interval in which
    the entity defaults.

    Vectorised throughout (`norm_ppf_vec`): the first draft called the scalar `norm_ppf` once per
    path, 400k times per date, and did not finish inside a 120-second test timeout — the third
    instance of the per-path-loop mistake, and the one the §7c clock gate now exists to catch.

    The truncation is **exact**, by inverse-CDF on the default-driver's own distribution, rather
    than by simulating default times and keeping the ones that land in the window. Filtering would
    make each interval's estimate a subsample — noisier, and it would make the ρ=0 case agree with
    the marginal only statistically instead of exactly."""
    # `ProtectionWindow` is reused rather than a new date pair invented: §3b says fold into an
    # existing ratified type, and "two dates and nothing else, the window a credit event may land
    # in" is exactly what the default window is. It also kept this signature at five arguments.
    t = vol_time_measure(process.market.valuation_date).year_fraction(window.end)
    q_start = survival.survival(window.start)
    q_end = survival.survival(window.end)
    # default in (t₀, t₁] ⟺ the uniform lies in [1−Q(t₀), 1−Q(t₁)) ⟺ Z_default in [a, b)
    a = norm_ppf(max(1.0 - q_start, 1e-12))
    b = norm_ppf(min(1.0 - q_end, 1.0 - 1e-12))
    rng = np.random.default_rng((numerics.seed, round(t * 1_000_000), 1))
    u = rng.uniform(norm_cdf(a), norm_cdf(b), numerics.paths)
    z_default = norm_ppf_vec(u)
    w = process.normal_draws(t, numerics)
    # NEGATED: `z_default` here is Φ⁻¹ of the default CDF, which is most negative for the EARLIEST
    # interval. Negating makes the driver "larger = earlier default", which is what makes ρ > 0
    # mean wrong-way (exposure high when they fail) rather than a statement about a parametrisation.
    return rho * (-z_default) + math.sqrt(max(1.0 - rho * rho, 0.0)) * w
