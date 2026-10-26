"""XVA — the valuation adjustments, composed over an exposure profile (L5).

    CVA = LGD · Σᵢ EE(tᵢ) · (Q(tᵢ₋₁) − Q(tᵢ))

**`cva` is THE single definition and the exposure method is the pluggable part** (§3d). The
swaption-approximation profile (slice 1) and an MC profile (a later slice) feed this same function,
so the two cannot become two CVAs that happen to agree — the vol-law and forward-threading precedent,
applied before it can bite rather than after.

`LGD = 1 − R` comes from `scalars[RecoveryKey(entity)]`, and `Q` from the entity's survival curve, so
both are reached through the snapshot and a bump at either home moves the charge (doc 11's
bump-consistency face). In slice 1 the survival curve feeds only the default leg; at the MC /
wrong-way-risk slice it will feed the exposure paths **and** this integral, which is precisely the
two-stages-one-input shape that face exists for.

Provenance:
  quarry: quarry/pricebook/risk/xva.py (the CVA/DVA/FVA family — MC-based, NOT crossed here; its
          retirement rides with the general-exposure slice)
  source: Gregory Ch. 12; Brigo-Morini-Pallavicini (unilateral CVA as the discounted expected loss)
  oracle: the composition re-summed independently; hazard→0 ⇒ CVA→0; monotone in hazard and LGD;
          exactly proportional to (1−R); N intervals → N terms
  slice:  cva-analytic (B7 slice 1)
"""

from __future__ import annotations

from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.foundation.results import PricingFailure
from pricebook.market.survival_curve import SurvivalHandle
from pricebook.models.protocols import CalibratedModel
from pricebook.products.swap import VanillaSwap
from pricebook.risk.exposure import ExposureProfile, swaption_exposure_profile


def cva(profile: ExposureProfile, survival: SurvivalHandle, recovery: float) -> float:
    """Unilateral CVA over `profile`: `LGD · Σ EE(tᵢ)·ΔQ(tᵢ)`.

    Each term pairs the exposure at `tᵢ` with the probability of defaulting **in** `(tᵢ₋₁, tᵢ]` —
    the survival *increment*, not the survival level. Using the level instead is the classic error
    and the `hazard → 0 ⇒ CVA → 0` limit is what catches it: increments vanish there, levels do not.

    Takes the profile rather than a trade, so an MC profile composes the identical definition."""
    if not profile:
        return 0.0
    total = 0.0
    prev_q = 1.0
    for when, ee in profile:
        q = survival.survival(when)
        total += ee * (prev_q - q)
        prev_q = q
    return (1.0 - recovery) * total


def swap_cva(
    swap: VanillaSwap, model: CalibratedModel, entity: ReferenceEntity
) -> float | PricingFailure:
    """The unilateral CVA of one swap against one counterparty — a single-trade netting set.

    Composition only: `swaption_exposure_profile` for the exposure leg, the entity's survival curve
    for the default leg, `scalars[RecoveryKey]` for the loss. Netting across trades (slice 2), DVA
    (slice 3), MC exposure, collateral/MPOR and wrong-way risk are each deferred with their own
    trigger — this is deliberately the unilateral single-trade case."""
    profile = swaption_exposure_profile(swap, model)
    if isinstance(profile, PricingFailure):
        return profile
    try:
        survival = model.market.curves.survival(entity)
        recovery = model.market.recovery(entity)
    except (KeyError, ValueError) as exc:
        return PricingFailure(f"CVA: {exc}")
    return cva(profile, survival, recovery)
