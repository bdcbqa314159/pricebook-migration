"""Equity option pricer (L4) — the vanilla European, by composition.

**No new pricing formula.** The equity option is the existing `black` atom evaluated on the
equity forward and discounted: `PV = df · black(F, K, σ, t, type)` with `F = S·e^{−q·t}/df`.
Black-Scholes-Merton and Black-76-on-the-forward are the same model written two ways, so the
slice's content is the *forward construction*, not the option formula — which is exactly what
§3d asks for (compose the atom, never re-derive it). The oracle checks the composition against
the BSM **spot** form, an independent arrangement of the same mathematics.

Provenance:
  quarry: quarry/pricebook/options/equity_option.py (the European vanilla content)
  source: Black (1976) on the forward; Merton (1973) for the continuous dividend yield `q`
  oracle: matches the BSM spot form to 1e-10 across strikes/types/q; put-call parity
          `C − P = df·(F − K)`; `F = S·e^{(r−q)t}`; σ→0 → discounted forward intrinsic
  slice:  equity-vanilla ((c) slice 1)
"""

from __future__ import annotations

from pricebook.engine.registry import register
from pricebook.foundation import Money, PricingFailure, PricingResult
from pricebook.market.building_blocks import equity_forward
from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey
from pricebook.models.black import black, vol_time_measure
from pricebook.models.protocols import CalibratedModel, EquityVol
from pricebook.products.equity import EquityOption


@register(EquityOption)
def price_equity_option(
    option: EquityOption, model: CalibratedModel
) -> PricingResult | PricingFailure:
    """Mark a European equity option. Capability dispatch, not type dispatch: any model carrying
    `EquityVol` prices this, so a later smile or local-vol model drops in without touching the
    engine (§1 — no `isinstance` on a concrete model)."""
    if not isinstance(model, EquityVol):  # capability check — a protocol, not a concrete-type ladder
        return PricingFailure("an equity option requires a model with the EquityVol capability")

    market = model.market
    vd = market.valuation_date
    tm = vol_time_measure(vd)  # the canonical vol clock, shared with the surface read (§3d, #4)
    t = tm.year_fraction(option.expiry)  # anchored at the valuation date by `vol_time_measure`

    try:
        spot = market.scalars[EquitySpotKey(option.underlying)]
        q = market.scalars[DividendYieldKey(option.underlying)]
        vol = model.equity_vol(option.underlying, option.expiry, option.strike)
        # the discount factor carries the financing leg; `r` is never read separately (see
        # `equity_forward` — one source for `e^{r·t}`, so the forward and the discount cannot drift)
        df = market.curves.discount(option.currency, None).df(option.expiry)
    except KeyError as exc:  # unmarked underlying / missing curve → a value, not a crash (invariant 4)
        return PricingFailure(f"equity option is unpriceable: {exc} is not marked")

    forward = equity_forward(spot, q, df, t)
    pv = df * black(forward, option.strike, vol, t, option.option_type)
    return PricingResult(pv=Money(pv, option.currency), accrued=None, basis=None)
