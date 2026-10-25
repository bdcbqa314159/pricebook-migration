"""BlackModel — the lognormal-vol model for optionlets (L3).

The SECOND `CalibratedModel` (after `DiscountingModel`) — the first real rule-of-two test of the
capability model. Like `DiscountingModel` it is BUILT, not solved: it carries the `MarketSnapshot`
(A1) and reads its vol from `market.surfaces` (vol calibration/stripping is a later slice). It adds
the `ImpliedVol` capability; `implied_vol` delegates to the surface under the `Q3′a` semantic
contract (lognormal, T-forward measure — see `models/protocols.py`), and carries `Lognormal` as its
`vol_law`: a flat `Surface` quotes a Black vol, so the model's law is fixed, not configurable.

Provenance:
  quarry: quarry/pricebook/models/black76.py (the model side)
  source: docs/22 Q1 (2nd CalibratedModel) · Q3′a (semantic contract); §B4 (Black-76 model)
  oracle: caplet reprices to Black-76 off model.implied_vol; DiscountingModel still prices linear
  slice:  black-caplet (C2 slice 1)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pricebook.foundation import RateIndex, Tenor
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import SurfaceKey, SwaptionSurfaceKey, flat_surface
from pricebook.models.black import vol_time_measure
from pricebook.models.vol_law import Lognormal, VolLaw


@dataclass(frozen=True)
class BlackModel:
    """Carries `market` (A1). Satisfies `CalibratedModel` (`.market`), `ImpliedVol` (`.implied_vol`
    + `.vol_law`, reads `SurfaceKey(index)`), AND `SwaptionVol` (`.swaption_vol`, reads
    `SwaptionSurfaceKey`) — opt-in capabilities on one model (doc 22 Q1). Adding `swaption_vol` did
    not change the meaning of `market` or the vol read; it extended the model additively."""

    market: MarketSnapshot
    vol_law: VolLaw = Lognormal()  # BlackModel IS the lognormal law — a flat Surface quotes a Black vol

    def implied_vol(self, index: RateIndex, expiry: date, strike: float, forward: float) -> float:
        # `forward` is IGNORED: a flat/term `Surface` is forward-independent (it has no smile axis),
        # so Black's vol read is unchanged by threading it — which is what keeps every BlackModel
        # number byte-identical across the slice-25 amendment.
        del forward
        tm = vol_time_measure(self.market.valuation_date)  # the canonical vol clock (§3d, #4)
        return flat_surface(self.market.surfaces[SurfaceKey(index)]).at(expiry, strike, tm)

    def swaption_vol(
        self, index: RateIndex, expiry: date, swap_tenor: Tenor, strike: float, forward: float
    ) -> float:
        del forward  # as above — a flat swaption surface carries no S dependence
        tm = vol_time_measure(self.market.valuation_date)
        return flat_surface(self.market.surfaces[SwaptionSurfaceKey(index, swap_tenor)]).at(expiry, strike, tm)
