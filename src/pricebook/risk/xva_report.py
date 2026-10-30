"""The XVA report (L5) — every exposure functional, from one set of marginal samples.

The surface `models/mc_exposure.py`'s consumer takes wholesale via `ExposureResult.to_dict()`:
EPE, **ENE**, **PFE percentiles**, **peak EE**, **effective EPE**, CVA, **DVA** and **FVA**.
Every one of them is a functional of the **per-date marginal distribution** of MtM — which is
exactly what ng samples — so none of them waits on joint paths. (Joint paths are wrong-way risk's
requirement, because WWR conditions on the default time; that stays deferred with its consumer.)

**What is composed rather than restated (§3d):**
- **DVA is `cva`.** `DVA = LGD_own·Σ ENE·ΔQ_own` is the CVA integral with the own-survival curve
  and the negative exposure, so this module calls `cva` with different arguments and defines no
  second formula. A test asserts the exact equality so one cannot drift from the other.
- **CVA is `cva`**, on the EPE profile, unchanged across its fourth consumer.

**Where ng deliberately differs from the quarry:** the quarry approximates all three adjustments
as `spread × Δt` (`cva += lgd·epe·s·dt`). ng uses the **survival increment** `ΔQ`, which `cva`'s
own docstring names as the thing the `hazard → 0` limit catches — a level-or-spread approximation
does not vanish there and an increment does. FVA keeps the spread form because funding is a
spread over time, not a default probability.

Provenance:
  quarry: quarry/pricebook/models/mc_exposure.py (the REPORT surface — which quantities a desk
          consumes; its spread×dt CVA/DVA and its engine-internal bundling are not carried)
  source: Basel III CCR (effective EPE as the time-average of the non-decreasing running maximum
          of EE); Gregory, *The xVA Challenge*, for the ENE/DVA and FVA definitions
  oracle: `EPE − ENE = V₀/df(0,t)` (an identity, both halves at once); DVA == `cva` on the ENE
          profile; a long option's ENE is identically zero; FVA linear in the funding spread
  slice:  xva-reporting (B7)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray

from pricebook.market.survival_curve import SurvivalHandle
from pricebook.risk.xva import ExposureProfile, cva

#: The percentiles a desk reports by default. Two, because one is not a profile shape and three
#: would be guessing at a convention — 95/99 are what the quarry's consumer reads.
DEFAULT_QUANTILES = (0.95, 0.99)


@dataclass(frozen=True)
class XvaTerms:
    """The counterparty and funding terms an XVA report is taken against.

    A value object rather than five loose arguments (§3b): `xva_report` would otherwise take
    seven, and the five here are one cohesive idea — *who can default, how much is recovered, and
    what funding costs*. `own_survival=None` means a **unilateral** report: no DVA, which is a
    real convention rather than a missing input, so it is expressed in the type."""

    survival: SurvivalHandle
    recovery: float
    own_survival: SurvivalHandle | None = None
    own_recovery: float = 0.4
    funding_spread: float = 0.0


@dataclass(frozen=True)
class XvaReport:
    # fields-exempt: N independent results (§3b names this type explicitly). These are eight
    # separate answers a desk reads side by side, not un-bundled vocabulary — there is no
    # sub-grouping that is itself a concept, and inventing one would relocate the smell rather
    # than remove it.
    """Everything the exposure simulation says, from one pass of marginal samples."""

    epe: ExposureProfile
    ene: ExposureProfile
    pfe: Mapping[float, ExposureProfile]
    ee_peak: float
    effective_epe: float
    cva: float
    dva: float
    fva: float


def xva_report(
    samples: Sequence[tuple[date, NDArray[np.float64]]],
    terms: XvaTerms,
    quantiles: Sequence[float] = DEFAULT_QUANTILES,
) -> XvaReport:
    """Every functional of the exposure distribution, from one set of per-date MtM samples.

    One simulation, many answers: taking the samples rather than a summary is what lets EPE, ENE,
    the percentiles and both running statistics come out of a single pass, instead of re-running
    the model once per quantity."""
    epe = tuple((d, float(np.mean(np.maximum(v, 0.0)))) for d, v in samples)
    ene = tuple((d, float(np.mean(np.maximum(-v, 0.0)))) for d, v in samples)
    pfe = {
        q: tuple((d, float(np.percentile(v, 100.0 * q))) for d, v in samples) for q in quantiles
    }

    values = [e for _, e in epe]
    ee_peak = max(values) if values else 0.0
    # Basel's EEE: the running MAXIMUM of EE, then time-averaged. Non-decreasing by construction,
    # which is the whole point — it is designed so that a trade rolling off cannot reduce the
    # capital measure, and a plain mean of EPE would let it.
    running, peak_so_far = [], float("-inf")
    for v in values:
        peak_so_far = max(peak_so_far, v)
        running.append(peak_so_far)
    effective_epe = sum(running) / len(running) if running else 0.0

    own = terms.own_survival
    return XvaReport(
        epe=epe,
        ene=ene,
        pfe=pfe,
        ee_peak=ee_peak,
        effective_epe=effective_epe,
        cva=cva(epe, terms.survival, terms.recovery),
        # the SAME atom, with the own curve and the negative exposure — not a second formula
        dva=cva(ene, own, terms.own_recovery) if own is not None else 0.0,
        fva=_fva(epe, terms.funding_spread),
    )


def _fva(epe: ExposureProfile, funding_spread: float) -> float:
    """`Σ EPE(tᵢ)·s_f·Δtᵢ` — funding carried on the expected positive exposure over each interval.

    Deliberately **not** survival-weighted like CVA/DVA: funding is a spread paid over *time*, not
    a loss conditional on a default, so a `ΔQ` here would be the wrong integrand rather than a
    more accurate one. `Δtᵢ` is measured in years from the profile's own dates, so the report
    needs no separate clock."""
    if not epe or funding_spread == 0.0:
        return 0.0
    total, prev = 0.0, epe[0][0]
    for when, exposure in epe[1:]:
        total += exposure * funding_spread * ((when - prev).days / 365.0)
        prev = when
    return total
