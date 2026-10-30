"""Standard-normal distribution — thin scipy adapter (L0, S17).

`scipy.stats.norm` behind our own API + provenance, so there is **one** place to pin
behaviour and **one** swap point for the C++ port. Never call scipy from engines/models —
call these.

Provenance:
  quarry: quarry/pricebook/core/ (distributions)
  source: scipy.stats.norm (pdf/cdf/ppf)
  oracle: norm_cdf(0)=0.5 and published values; norm_ppf inverts norm_cdf; p∉(0,1) raises
  slice:  l0-numerics (Topic 0 gate S17)
"""

from __future__ import annotations

from scipy.stats import norm


def norm_pdf(x: float) -> float:
    """Standard-normal probability density."""
    return float(norm.pdf(x))


def norm_cdf(x: float) -> float:
    """Standard-normal cumulative distribution."""
    return float(norm.cdf(x))


def norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (quantile). `p` must be strictly in (0, 1)."""
    if not 0.0 < p < 1.0:
        raise ValueError(f"norm_ppf requires 0 < p < 1, got {p}")
    return float(norm.ppf(p))


def norm_ppf_vec(x):
    """`norm_ppf` over an ARRAY — the inverse CDF at a vector of probabilities.

    The same scipy call at a different shape, and it exists for the same reason `black_vec` and
    `bond_vec` do: calling the scalar version inside a path loop is `O(paths)` Python calls, which
    has now cost this project three slices (73s rates MC, 59s equity exposure, and the WWR
    copula's 400k-path inverse-CDF, which did not finish inside a 120s test timeout). Bound to the
    scalar by a tested elementwise identity, so two shapes cannot become two functions (§3d).
    """
    return norm.ppf(x)
