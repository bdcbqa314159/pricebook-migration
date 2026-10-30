"""FVA and BCVA — and the one integral all the adjustments share.

**The §3d move applied to XVA.** CVA, DVA and FVA differ only in *what they weight the exposure
by* — the survival increment `ΔQ`, the own-survival increment, the funding spread `s_f·Δt` — and
not at all in the integral itself. The quarry has them as three separate loops (and a fourth for
MVA); ng has **one** `exposure_integral(profile, weights)` that each composes. The guard is the
same one the annuity pair carries: `cva` recomputed through the shared atom must equal the
existing `cva` to the last bit, so they cannot diverge in the integral the way the calibrator and
engine annuities could.

**BCVA is a pure combination** — `cva − dva` — so it takes no new input at all.
"""

import math
from datetime import date, timedelta

import pytest

from pricebook.foundation import Currency
from pricebook.market.curve import DiscountCurve
from pricebook.market.snapshot import FundingSpreadKey
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.models.black import vol_time_measure
from pricebook.risk.xva import bilateral_cva, cva, exposure_integral, fva, survival_weights

VAL = date(2026, 1, 15)
DATES = tuple(VAL + timedelta(days=365 * n) for n in (1, 2, 3, 4))
EPE = tuple((d, 1_000_000.0 * (1.0 - 0.2 * i)) for i, d in enumerate(DATES))
ENE = tuple((d, -0.0 + 300_000.0) for d in DATES)
R_FLAT = 0.03


def _survival(hazard: float) -> SurvivalCurve:
    return SurvivalCurve(
        measure=vol_time_measure(VAL), times=(0.0, 20.0), survivals=(1.0, math.exp(-hazard * 20.0))
    )


def _curve() -> DiscountCurve:
    return DiscountCurve(
        time_measure=vol_time_measure(VAL), times=(0.0, 30.0), dfs=(1.0, math.exp(-R_FLAT * 30.0))
    )


# ── 1. the shared atom, and that cva goes through it ────────────────────────────────────────
def test_cva_through_the_SHARED_ATOM_equals_the_existing_cva_to_the_ULP() -> None:
    """The rpv01 lesson applied to XVA: one integral, composed, so CVA and FVA cannot drift. If
    `cva` kept its own loop this would be two definitions agreeing today."""
    surv = _survival(0.02)
    via_atom = (1.0 - 0.4) * exposure_integral(EPE, survival_weights(EPE, surv))
    assert via_atom == cva(EPE, surv, 0.4)


def test_the_atom_is_a_PLAIN_WEIGHTED_SUM_with_no_hidden_discounting() -> None:
    """Profiles arrive discounted (the convention `cva` requires), so the atom must NOT discount
    again. Asserted against a hand sum, because a second discounting is exactly the bug that
    shipped in v0.140.0 one layer up."""
    weights = tuple(1.0 for _ in EPE)
    assert exposure_integral(EPE, weights) == pytest.approx(sum(e for _, e in EPE), rel=0.0)


def test_survival_weights_are_INCREMENTS_not_levels() -> None:
    """`ΔQ`, the thing `cva`'s docstring names as the classic error. Increments sum to `1 − Q(tₙ)`;
    levels would sum to something near `n`."""
    surv = _survival(0.02)
    w = survival_weights(EPE, surv)
    assert sum(w) == pytest.approx(1.0 - surv.survival(DATES[-1]), rel=1e-12)
    assert all(x > 0.0 for x in w)


# ── 2. FVA ──────────────────────────────────────────────────────────────────────────────────
def test_fva_matches_the_flat_spread_closed_form() -> None:
    """Flat spread, annual dates: `FVA = s_f·Σ EPE(tᵢ)·Δtᵢ` exactly — the closed form, since the
    profile is already discounted and the spread is constant."""
    s_f = 0.0075
    want = s_f * sum(e * 1.0 for _, e in EPE[1:])  # Δt = 1y between annual dates
    assert fva(EPE, s_f) == pytest.approx(want, rel=1e-12)


def test_fva_vanishes_at_a_zero_funding_spread() -> None:
    """FVA's analogue of `hazard → 0 ⇒ CVA → 0` — the structural limit."""
    assert fva(EPE, 0.0) == 0.0


def test_fva_is_linear_in_the_spread_and_in_the_exposure() -> None:
    assert fva(EPE, 0.02) == pytest.approx(2.0 * fva(EPE, 0.01), rel=1e-12)
    doubled = tuple((d, 2.0 * e) for d, e in EPE)
    assert fva(doubled, 0.01) == pytest.approx(2.0 * fva(EPE, 0.01), rel=1e-12)


def test_the_funding_spread_is_L1_MARKET_STATE_keyed_not_a_field() -> None:
    """Keys-not-fields (§3c): the funding spread is a market number risk bumps, so it lives in the
    snapshot's `scalars` under its own key — not as a field on a config or a product."""
    from pricebook.risk.bump import ScalarBump

    key = FundingSpreadKey(Currency.USD)
    assert key == FundingSpreadKey(Currency.USD)  # keyed by VALUE
    assert ScalarBump(key).key == key  # and bumpable through the one scalar mechanism


# ── 3. BCVA — a pure combination ────────────────────────────────────────────────────────────
def test_bilateral_cva_IS_cva_minus_dva_exactly() -> None:
    """A combination cannot drift, so this is asserted to the ULP rather than to a tolerance. It
    takes no new input: ng already has both halves."""
    c = cva(EPE, _survival(0.02), 0.4)
    d = cva(ENE, _survival(0.01), 0.4)
    assert bilateral_cva(c, d) == c - d


def test_bcva_is_the_UNILATERAL_cva_when_we_cannot_default() -> None:
    c = cva(EPE, _survival(0.02), 0.4)
    assert bilateral_cva(c, 0.0) == c


def test_bcva_flips_sign_when_our_own_credit_dominates() -> None:
    """A desk whose own hazard far exceeds the counterparty's shows a **negative** BCVA — a gain,
    because its own default extinguishes a liability. Sign conventions are where bilateral XVA
    goes wrong, so it is asserted rather than assumed."""
    c = cva(EPE, _survival(0.001), 0.4)
    d = cva(EPE, _survival(0.20), 0.4)  # same exposure, far worse own credit
    assert bilateral_cva(c, d) < 0.0
