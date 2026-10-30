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

from collections.abc import Sequence

from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.foundation.results import PricingFailure
from pricebook.market.survival_curve import SurvivalHandle
from pricebook.models.protocols import CalibratedModel
from pricebook.products.swap import VanillaSwap
from pricebook.risk.exposure import ExposureProfile, swaption_exposure_profile


def exposure_integral(profile: ExposureProfile, weights: Sequence[float]) -> float:
    """`Σ profileᵢ · weightᵢ` — the ONE integral every valuation adjustment is.

    CVA, DVA and FVA differ **only** in the weight: the counterparty's survival increment, our
    own, or the funding spread over each interval. They do not differ in the integral, and the
    quarry having three separate loops for it (plus a fourth for MVA) is exactly the §3d smell the
    annuity pair taught — the calibrator and the engine each rolling their own `Σ τ·df` is how two
    stages come to disagree about day count while every test passes.

    **It does not discount.** Profiles arrive already discounted to today (`cva` weights by `ΔQ`
    and nothing else), so a `df` here would be the second one — the bug that shipped one layer up
    in v0.140.0 and made every adjustment 5.14% too large."""
    if len(weights) != len(profile):
        raise ValueError(
            f"{len(weights)} weights for {len(profile)} exposure dates — one weight per date"
        )
    return sum(exposure * w for (_, exposure), w in zip(profile, weights))


def survival_weights(profile: ExposureProfile, survival: SurvivalHandle) -> tuple[float, ...]:
    """The default-in-the-interval probabilities `ΔQ(tᵢ) = Q(tᵢ₋₁) − Q(tᵢ)`.

    **Increments, never levels.** Each term must pair the exposure at `tᵢ` with the probability of
    defaulting *in* `(tᵢ₋₁, tᵢ]`; using the survival level instead is the classic error, and the
    `hazard → 0 ⇒ CVA → 0` limit is what catches it — increments vanish there and levels do not.
    Extracted as its own function so CVA and DVA share one definition of the weight as well as one
    integral."""
    weights: list[float] = []
    prev_q = 1.0
    for when, _ in profile:
        q = survival.survival(when)
        weights.append(prev_q - q)
        prev_q = q
    return tuple(weights)


def cva(profile: ExposureProfile, survival: SurvivalHandle, recovery: float) -> float:
    """Unilateral CVA over `profile`: `LGD · Σ EE(tᵢ)·ΔQ(tᵢ)`.

    Composed, not rolled: the weight comes from `survival_weights` and the sum from
    `exposure_integral`, both shared with DVA and (the integral) with FVA. A test asserts this
    equals the pre-refactor definition **to the ULP**.

    `profile` must be **discounted to today** — this function applies the survival weighting and
    nothing else. Takes the profile rather than a trade, so an MC profile composes the identical
    definition."""
    if not profile:
        return 0.0
    return (1.0 - recovery) * exposure_integral(profile, survival_weights(profile, survival))


def fva(profile: ExposureProfile, funding_spread: float) -> float:
    """Funding valuation adjustment: `Σ EPE(tᵢ)·s_f·Δtᵢ`, through the shared integral.

    **Deliberately not survival-weighted.** Funding is a spread paid over *time*, not a loss
    conditional on a default, so a `ΔQ` here would be the wrong integrand rather than a more
    precise one — which is why the weight, not the integral, is what differs between FVA and CVA.
    `Δtᵢ` is measured from the profile's own dates, so FVA needs no separate clock."""
    if not profile or funding_spread == 0.0:
        return 0.0
    weights = [0.0]
    for (prev, _), (when, _) in zip(profile, profile[1:]):
        weights.append(funding_spread * ((when - prev).days / 365.0))
    return exposure_integral(profile, weights)


def bilateral_cva(cva_value: float, dva_value: float) -> float:
    """BCVA = `CVA − DVA`. A pure combination of two numbers ng already has, so it takes no new
    input and is asserted to the ULP rather than to a tolerance.

    **It can be negative**, and that is not a bug: a desk whose own hazard exceeds the
    counterparty's shows a *gain*, because its own default extinguishes a liability. Sign
    conventions are where bilateral XVA goes wrong, so the sign flip is a test.

    **First-to-default is NOT modelled here.** A rigorous BCVA conditions each leg on the other
    party not having defaulted first, which needs a **joint** survival law; this is the standard
    independent-legs approximation. `deferred→` the WWR / joint-default consumer, which is the
    same widening `gbm.py` and wrong-way risk already wait on."""
    return cva_value - dva_value


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
