"""Root-finding and least-squares — thin scipy adapters (L0, S17).

`scipy.optimize` behind our own API + provenance: Brent (bracketed root), Newton (with
derivative), secant (without), and Levenberg-Marquardt least-squares for calibration
residuals. This **replaces** the hand-rolled `bisect_root`/`nelder_mead` — no duplicates,
one swap point for the C++ port. Never call scipy from engines/models — call these.

Provenance:
  quarry: quarry/pricebook/core/ (solvers)
  source: scipy.optimize (brentq, newton, least_squares method='lm')
  oracle: brent/newton/secant find sqrt(2); LM recovers a linear fit's coefficients
  slice:  l0-numerics (Topic 0 gate S17)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

import numpy as np
from scipy.optimize import brentq as _brentq
from scipy.optimize import least_squares as _least_squares
from scipy.optimize import newton as _newton


def brent(
    f: Callable[[float], float],
    lo: float,
    hi: float,
    tol: float = 1e-14,
    max_iter: int = 200,
) -> float:
    """Root of `f` bracketed in ``[lo, hi]`` (Brent). `f(lo)`, `f(hi)` must differ in sign."""
    # brentq returns a bare float without full_output; the stub types it as a union, so cast.
    return float(cast(float, _brentq(f, lo, hi, xtol=tol, maxiter=max_iter)))


def invert_increasing(
    f: Callable[[float], float],
    target: float,
    lo: float,
    hi: float,
    cap: float,
) -> float:
    """The inverse of a monotonically INCREASING `f`: the `x` in `[lo, cap]` with `f(x) = target`.

    `hi` is a starting guess for the upper bracket, DOUBLED until it straddles `target` or passes
    `cap` — the caller rarely knows how high to look, and evaluating `f` at a needlessly huge `hi`
    can overflow or lose precision. Unattainable targets RAISE, naming which end failed: below
    `f(lo)` the target is outside the function's range from below; above `f(cap)` the search gave up
    at a declared ceiling. Never returns a mid-bracket consolation value — a returned non-solution is
    the worst kind of silent wrongness (CLAUDE.md 5).

    Promoted from a hand-rolled loop that had been duplicated (the caplet-vol strip's marginal solve
    and the implied-vol inversion are the same search); both compose this now.

    Provenance note: the bracket-then-Brent shape is deliberate — Brent needs a sign change, and this
    is the piece scipy does not provide (3-7bb: own what scipy lacks, adapt what it has).
    """
    f_lo = f(lo) - target
    if f_lo > 0.0:
        raise ValueError(f"target {target!r} is below f(lo={lo!r}) = {f(lo)!r} (increasing f)")
    f_hi = f(hi) - target
    while f_lo * f_hi > 0.0 and hi < cap:
        hi *= 2.0
        f_hi = f(hi) - target
    if f_lo * f_hi > 0.0:
        raise ValueError(f"target {target!r} not attainable below the cap {cap!r}")
    return brent(lambda x: f(x) - target, lo, hi)


def newton(
    f: Callable[[float], float],
    x0: float,
    fprime: Callable[[float], float],
    tol: float = 1e-12,
    max_iter: int = 100,
) -> float:
    """Root of `f` from `x0` using its derivative `fprime` (Newton)."""
    return float(_newton(f, x0, fprime=fprime, tol=tol, maxiter=max_iter))


def secant(
    f: Callable[[float], float],
    x0: float,
    x1: float,
    tol: float = 1e-12,
    max_iter: int = 100,
) -> float:
    """Root of `f` from two starting points `x0`, `x1` (secant — no derivative needed)."""
    return float(_newton(f, x0, x1=x1, tol=tol, maxiter=max_iter))


def least_squares(
    residual: Callable[[Sequence[float]], Sequence[float]],
    x0: Sequence[float],
    tol: float = 1e-12,
    max_iter: int = 1000,
    bounds: tuple[Sequence[float], Sequence[float]] | None = None,
) -> list[float]:
    """Minimise ``sum(residual(x)^2)`` from `x0`; returns the solution vector. Unbounded uses
    Levenberg-Marquardt; passing `bounds=(lower, upper)` constrains the solution to a box
    (Trust Region Reflective — LM cannot take bounds). The natural shape for calibration."""
    return root_nd(residual, x0, tol, max_iter, bounds)[0]


def root_nd(
    residual: Callable[[Sequence[float]], Sequence[float]],
    x0: Sequence[float],
    tol: float = 1e-12,
    max_iter: int = 1000,
    bounds: tuple[Sequence[float], Sequence[float]] | None = None,
) -> tuple[list[float], list[list[float]], bool]:
    """Solve the N-D system ``F(x) = 0`` from `x0` by least-squares. Returns
    ``(solution, jacobian, converged)`` where `jacobian` is ``∂residualᵢ/∂xⱼ`` at the solution
    (rows = residuals, cols = unknowns). Unbounded uses Levenberg-Marquardt; `bounds=(lower,
    upper)` switches to Trust Region Reflective and keeps the solution in the box. Non-convergence
    — including a solver error or a residual that blows up — is returned as ``converged=False``
    (failure is a value), never raised. The single N-D solver for calibration (§7bb)."""
    try:
        if bounds is None:
            result = _least_squares(
                residual, list(x0), method="lm", xtol=tol, ftol=tol, max_nfev=max_iter
            )
        else:
            result = _least_squares(
                residual, list(x0), method="trf",
                bounds=(list(bounds[0]), list(bounds[1])), xtol=tol, ftol=tol, max_nfev=max_iter,
            )
    except (ValueError, FloatingPointError, ZeroDivisionError):
        return list(map(float, x0)), [], False
    x = [float(v) for v in result.x]
    jac = [[float(v) for v in row] for row in np.atleast_2d(np.asarray(result.jac, dtype=float))]
    return x, jac, bool(result.success)
