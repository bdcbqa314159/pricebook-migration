"""SABR implied-vol expansions — the analytic block of the SABR dynamics (L3).

`sabr_vol(forward, strike, t, params)` is the Hagan et al. (2002) lognormal (Black-76) implied
volatility of the SABR dynamics — the closed-form ANALYTIC BLOCK of a dynamics, so it lives at L3,
not L0 (the `models/black.py` precedent, CLAUDE.md §1). Discounting is OUT (df ∉ its args); the L4
engine multiplies `df·N·τ·black(F, K, σ_SABR, t)`, exactly as for a flat vol.

This module is the ANALYTIC BLOCK only — the expansions, no market data. The model that reads them
off a snapshot is `models/sabr_model.py`, and the laws that pair each expansion with its option
formula and its domain are `models/vol_law.py` (the `black.py` / `black_model.py` precedent).

Provenance:
  quarry: quarry/pricebook/options/sabr.py
  source: Hagan, Kumar, Lesniewski, Woodward (2002) "Managing Smile Risk" eq 2.17a/2.18
  oracle: sabr_vol vs an independent inline Hagan; ATM branch = eq 2.18; caplet → Black
  slice:  sabr-caplet (T1 slice 20) · model split out in sabr-multilaw (T1 slice 22)
"""

from __future__ import annotations

import math

from pricebook.market.vol_surface import SabrParams

_ATM_LOG_TOL = 1e-12  # |log(F/K)| below this ⇒ the removable z/χ(z) singularity; use the ATM branch


def sabr_vol(forward: float, strike: float, t: float, params: SabrParams) -> float:
    """Hagan 2002 lognormal implied vol σ_B(F, K). β is fixed (carried on `params`). At F=K the
    z/χ(z) factor has a removable singularity → the ATM branch (eq 2.18). `t` is the option
    year-fraction on the canonical vol clock (§3d)."""
    a, b, rho, nu = params.alpha, params.beta, params.rho, params.nu
    one_mb = 1.0 - b
    if abs(math.log(forward / strike)) < _ATM_LOG_TOL:  # ATM, eq 2.18 (and the F=K limit)
        f_pow = forward**one_mb
        correction = (
            one_mb * one_mb / 24.0 * a * a / forward ** (2.0 * one_mb)
            + 0.25 * rho * b * nu * a / f_pow
            + (2.0 - 3.0 * rho * rho) / 24.0 * nu * nu
        )
        return a / f_pow * (1.0 + correction * t)
    log_fk = math.log(forward / strike)
    fk_pow = (forward * strike) ** (one_mb / 2.0)
    z = nu / a * fk_pow * log_fk
    # z/χ(z) → 1 as z→0 (removable): ν=0 gives z=χ=0 exactly (0/0), so take the limit for tiny z
    z_over_chi = 1.0 if abs(z) < 1e-12 else z / math.log(
        (math.sqrt(1.0 - 2.0 * rho * z + z * z) + z - rho) / (1.0 - rho)
    )
    denom = fk_pow * (
        1.0 + one_mb * one_mb / 24.0 * log_fk**2 + one_mb**4 / 1920.0 * log_fk**4
    )
    correction = (
        one_mb * one_mb / 24.0 * a * a / (forward * strike) ** one_mb
        + 0.25 * rho * b * nu * a / fk_pow
        + (2.0 - 3.0 * rho * rho) / 24.0 * nu * nu
    )
    return a / denom * z_over_chi * (1.0 + correction * t)


def sabr_normal_vol(forward: float, strike: float, t: float, params: SabrParams) -> float:
    """Hagan 2002 NORMAL (Bachelier) implied vol σ_N(F, K) for the **β = 0** SABR dynamics
    (`dF = σ dW₁`, `dσ = ν σ dW₂`) — the negative-rates workhorse.

    This is eq 2.17b specialised to β=0, where the two log-moneyness series cancel identically and
    the exact β=0 expansion variable is `z = (ν/α)(F − K)`: **no `log(F/K)`, no `(FK)^p`**, so the
    formula is defined for forwards and strikes of EITHER SIGN. That is the whole reason the normal
    law exists, and the reason it is not expressed as a *conversion* of the lognormal vol (the
    quarry's `σ_B·√(FK)`, which inherits the lognormal's positivity requirement and is only exact
    at the money).

        σ_N = α · z/χ(z) · (1 + (2 − 3ρ²)/24 · ν² · t),   z = (ν/α)(F − K)

    A general-β CEV dynamics quoted in normal-vol units is a different object (a conversion between
    laws); it RAISES here rather than being silently approximated — deferred to its first consumer
    (`OPEN.md`). At `F = K` the `z/χ(z)` factor has the same removable singularity as the lognormal
    expansion → the limit 1. `t` is the option year-fraction on the canonical vol clock (§3d)."""
    a, b, rho, nu = params.alpha, params.beta, params.rho, params.nu
    if b != 0.0:
        raise ValueError(
            f"the normal SABR law is the β=0 dynamics; got β={b} — a general-β CEV quoted in "
            f"normal-vol units is a law conversion, deferred to its first consumer"
        )
    z = nu / a * (forward - strike)
    # z/χ(z) → 1 as z→0 (removable): F=K or ν=0 gives z=χ=0 exactly, so take the limit for tiny z
    z_over_chi = 1.0 if abs(z) < _ATM_LOG_TOL else z / math.log(
        (math.sqrt(1.0 - 2.0 * rho * z + z * z) + z - rho) / (1.0 - rho)
    )
    return a * z_over_chi * (1.0 + (2.0 - 3.0 * rho * rho) / 24.0 * nu * nu * t)
