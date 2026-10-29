"""Equity greeks (L5) — bump-and-reprice through the c1 pricer.

Every greek here is a finite difference over a snapshot bump: the equity option is repriced at a
perturbed `MarketSnapshot` through the **same** L4 pricer that marks it, so a greek cannot drift
from the price it differentiates. No closed-form greek lives in the library — the closed forms
appear only as *test references* (`tests/L5/test_equity_greeks.py`), which is what makes those
tests an oracle rather than a restatement.

Spot and dividend-yield sensitivities ride the generic `ScalarBump`; vega rides the existing
`SurfaceBump`. Neither is equity-specific machinery: the asset class contributed keys, and the
risk mechanisms were already there (§3c — a new asset adds keys, not a parallel risk stack).

Provenance:
  quarry: quarry/pricebook/options/equity_option.py (the greeks suite — mined for WHAT is
          reported, not for HOW: the quarry computes closed forms, ng bumps)
  source: Black-Scholes-Merton greeks (Hull, Options Futures and Other Derivatives §19)
  oracle: delta vs `e^{−qT}·N(d₁)`; vega vs ng's own `black_vega`·df; gamma structural (positive,
          peaks at the FORWARD, call/put identical); greek parity `Δ_C − Δ_P = e^{−qT}`
  slice:  equity-greeks + ScalarBump ((c), before c2)
"""

from __future__ import annotations

from pricebook.foundation import PricingFailure
from pricebook.foundation.equity import EquityUnderlying
from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey, MarketSnapshot
from pricebook.market.vol_surface import EquitySurfaceKey
from pricebook.risk.bump import ScalarBump, SurfaceBump
from pricebook.risk.greeks import central_diff
from pricebook.risk.priceable import Priceable

#: Spot bump for delta/gamma — 1bp of a ~100 spot. Large enough that the FD noise floor
#: (~1e-16 relative on the PV) stays far below the truncation error, small enough that the
#: O(h²) truncation stays under the 1e-6 the oracle asserts.
_SPOT_SHIFT = 0.01
#: Vol and dividend-yield bumps are in absolute rate terms — 1bp.
_RATE_SHIFT = 1e-4


def _underlying(p: Priceable) -> EquityUnderlying | None:
    """The option's underlying, needed to build the key the bump targets. Read off the instrument
    the `Priceable` closes over rather than passed in, so a caller cannot ask for ACME's delta on
    a NVDA option — a mismatch that would silently return 0.0 (bumping a key the price does not
    read) rather than fail."""
    instrument = getattr(p, "instrument", None)
    return getattr(instrument, "underlying", None)


def equity_delta(p: Priceable, market: MarketSnapshot) -> float | PricingFailure:
    """`∂PV/∂S` — the spot sensitivity, per unit of spot (not per 1% and not per bump)."""
    u = _underlying(p)
    if u is None:
        return PricingFailure("equity delta needs a priceable carrying an equity underlying")
    return central_diff(p, market, ScalarBump(EquitySpotKey(u)), _SPOT_SHIFT)


def equity_gamma(p: Priceable, market: MarketSnapshot) -> float | PricingFailure:
    """`∂²PV/∂S²`, as the central second difference `(V₊ − 2V₀ + V₋)/h²`.

    Built here rather than on `central_diff` because that helper is a *first* difference and
    bending it to do both would make its contract ambiguous. A second difference is also
    noisier — it divides by `h²` — which is why the oracle for gamma is structural (sign, where
    it peaks, call/put identity) instead of a tight analytic match."""
    u = _underlying(p)
    if u is None:
        return PricingFailure("equity gamma needs a priceable carrying an equity underlying")
    bump = ScalarBump(EquitySpotKey(u))
    h = _SPOT_SHIFT
    try:
        up = p.price_at(bump.apply(market, h))
        mid = p.price_at(market)
        down = p.price_at(bump.apply(market, -h))
    except KeyError as exc:
        return PricingFailure(f"no market data to bump at key {exc}")
    if isinstance(up, PricingFailure):
        return up
    if isinstance(mid, PricingFailure):
        return mid
    if isinstance(down, PricingFailure):
        return down
    return (up.pv.amount - 2.0 * mid.pv.amount + down.pv.amount) / (h * h)


def equity_vega(p: Priceable, market: MarketSnapshot) -> float | PricingFailure:
    """`∂PV/∂σ` per unit of vol, through the EXISTING `SurfaceBump` — equity contributed a
    surface key, not a second vega mechanism."""
    u = _underlying(p)
    if u is None:
        return PricingFailure("equity vega needs a priceable carrying an equity underlying")
    return central_diff(p, market, SurfaceBump(EquitySurfaceKey(u)), _RATE_SHIFT)


def equity_dividend_rho(p: Priceable, market: MarketSnapshot) -> float | PricingFailure:
    """`∂PV/∂q` — sensitivity to the continuous dividend yield. Negative for a call: a higher `q`
    lowers the forward. Named `_rho` by analogy with the rate sensitivity it mirrors; the two are
    equal and opposite for a call under a flat curve, which is a useful sanity check but not an
    identity the library asserts (the curve is not flat in general)."""
    u = _underlying(p)
    if u is None:
        return PricingFailure("equity dividend rho needs a priceable carrying an equity underlying")
    return central_diff(p, market, ScalarBump(DividendYieldKey(u)), _RATE_SHIFT)
