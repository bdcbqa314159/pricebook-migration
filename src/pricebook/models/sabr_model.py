"""SABRModel — the smile-aware optionlet model (L3).

Split out of `models/sabr.py` so the analytic expansions can be composed by `models/vol_law.py`
without an intra-layer cycle (the `black.py` / `black_model.py` precedent: the closed form and the
model that reads market data are separate modules).

`SABRModel` satisfies **two** opt-in capabilities (doc 22 Q1): `ImpliedVol` for the caplet smile and
`SwaptionVol` for the swaption smile — the same `SabrSurface` read under two keys, so one model
carries both without a fat base class or a type ladder. It is READ, not solved: `SabrParams` are
carried on the snapshot (`SurfaceKey(index)` for caplets, `SwaptionSurfaceKey(index, swap_tenor)` for
the swaption cube); calibration is a later slice.

**§3d, after ruling A (slice 25): the forward is an INPUT.** Both methods anchor the Hagan expansion
at the forward the ENGINE marked and passed in — F over the contract's own accrual for a caplet,
`S = float_leg_pv/rpv01` for a swaption. The model reconstructs nothing, so the price formula and the
smile cannot evaluate at different forwards. The previous shape (re-deriving F from the index's
canonical accrual) worked only because a caplet's accrual IS canonical; for a swaption the underlying
swap's conventions are not in `(index, expiry, swap_tenor)` at all, and reconstructing them moved S by
**48.8 basis points** (`docs/handoffs/AUDIT_swaption_sabr_read.md`).

Provenance:
  quarry: quarry/pricebook/options/sabr.py
  source: Hagan, Kumar, Lesniewski, Woodward (2002) "Managing Smile Risk"; docs/22 Q1
  oracle: a NON-CANONICAL (semi-annual) underlying's ATM payer lands on the SABR smile
          minimum — reds by 48.8bp under any reconstruct-S design; Hagan reference; negative S
  slice:  sabr-caplet (T1 slice 20) · split in sabr-multilaw (22) · swaption_vol in (25)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pricebook.foundation import RateIndex, Tenor
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import (
    SabrParams,
    SabrSurface,
    SurfaceKey,
    SwaptionSurfaceKey,
)
from pricebook.models.black import vol_time_measure
from pricebook.models.vol_law import Lognormal, VolLaw, vol_law_for


@dataclass(frozen=True)
class SABRModel:
    """Carries `market` (A1). Satisfies `CalibratedModel` (`.market`) and `ImpliedVol`
    (`.implied_vol` + `.vol_law`) — the SAME capability `BlackModel` exposes, now smile-aware.
    READ, not solved: reads `SabrParams` from `market.surfaces[SurfaceKey(index)]` (a
    `SabrSurface`); a flat `Surface` there is a config error surfaced as a value by the engine's
    catch (KeyError-family). The vol is the LAW's expansion, never a bare Hagan call — so the law
    and the vol it produces can never be mismatched."""

    market: MarketSnapshot
    vol_law: VolLaw = Lognormal()

    @classmethod
    def for_index(cls, market: MarketSnapshot, index: RateIndex) -> SABRModel:
        """Build the model with the law its OWN surface is quoted in — the sanctioned constructor,
        and the only place a `VolLawKind` tag becomes a `VolLaw` (via `vol_law_for`)."""
        surface = market.surfaces[SurfaceKey(index)]
        if not isinstance(surface, SabrSurface):
            raise ValueError(f"SABRModel expects a SabrSurface, got {type(surface).__name__}")
        return cls(market, vol_law_for(surface.law, surface.shift))

    def _params(self, key: SurfaceKey | SwaptionSurfaceKey, expiry: date) -> SabrParams:
        """The `SabrParams` at `expiry` under `key`, with the two structural reads both capabilities
        need: the surface must BE a `SabrSurface`, and its law tag must match the model's law (α means
        different things per law, so params read in the wrong law are wrong by a factor of F).
        Compared as VALUES through the same `vol_law_for` factory — no reverse mapping."""
        surface = self.market.surfaces[key]
        if not isinstance(surface, SabrSurface):  # a flat Surface under a SABRModel is a config error
            raise ValueError(f"SABRModel expects a SabrSurface, got {type(surface).__name__}")
        if vol_law_for(surface.law, surface.shift) != self.vol_law:
            raise ValueError(
                f"model law {type(self.vol_law).__name__} does not match the surface's "
                f"{surface.law.name} tag — use SABRModel.for_index"
            )
        return surface.at_expiry(expiry)

    def implied_vol(self, index: RateIndex, expiry: date, strike: float, forward: float) -> float:
        """The caplet smile at the forward the ENGINE marked. `forward` is an input, never
        reconstructed here (ruling A): the price formula and the smile therefore compose the same F
        by construction, and a stub / non-standard optionlet is priced at its own forward rather
        than refused (`OPEN.md` ML-D1, closed)."""
        params = self._params(SurfaceKey(index), expiry)
        t = vol_time_measure(self.market.valuation_date).year_fraction(expiry)
        return self.vol_law.sabr_vol(forward, strike, t, params)

    def swaption_vol(
        self, index: RateIndex, expiry: date, swap_tenor: Tenor, strike: float, forward: float
    ) -> float:
        """The swaption smile at the forward SWAP RATE the engine marked (`S = float_leg_pv/rpv01`).
        The cube is just `{SwaptionSurfaceKey(index, swap_tenor) → SabrSurface}` + this method — no
        new type (the quarry's `SwaptionVolCube`, with its nearest-node strike hack and silent
        calibration fallback, is NOT ported). Reading S rather than deriving it is what makes the
        smile and the price share one S: the underlying's fixed-leg frequency, day counts, collateral
        and seasoning are not derivable from `(index, expiry, swap_tenor)`, and reconstructing them
        moved S by 48.8bp across the conventions this tree uses."""
        params = self._params(SwaptionSurfaceKey(index, swap_tenor), expiry)
        t = vol_time_measure(self.market.valuation_date).year_fraction(expiry)
        return self.vol_law.sabr_vol(forward, strike, t, params)
