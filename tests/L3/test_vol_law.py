"""L3 oracles — the vol LAWS (T1 slice 22).

Three laws, each a (formula · SABR expansion · domain) triple. The oracles are closed-form
anchors and independent code paths, never "the law agrees with itself":

* `bachelier` vs an independent inline normal formula (`erf`) + exact put-call parity;
* `Normal.sabr_vol` (β=0 normal SABR) against its ρ=0 `asinh` closed form — a genuinely
  different function — plus the ν=0 ⇒ σ_N ≡ α anchor at EVERY strike, negative strikes included;
* the price-level cross-law check: the same β=0 SABR dynamics priced through the normal law
  (`bachelier` at σ_N) and through the lognormal law (`black` at σ_B) agree to expansion order —
  the check that catches a wrong SCALE (the quarry's σ_B·√(FK) conversion fails it);
* `ShiftedLognormal(0)` ≡ `Lognormal` at every strike (structural identity, exact).
"""

import math
from datetime import date

import pytest

from pricebook.market.vol_surface import SabrParams, SabrSurface, VolLawKind
from pricebook.models.bachelier import bachelier
from pricebook.models.black import black
from pricebook.models.sabr import sabr_normal_vol, sabr_vol
from pricebook.models.vol_law import (
    Lognormal,
    Normal,
    ShiftedLognormal,
    VolLaw,
    vol_law_for,
)
from pricebook.products.option import OptionType

CALL, PUT = OptionType.CALL, OptionType.PUT
EXPIRY = date(2027, 1, 15)


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _ref_bachelier(f: float, k: float, vol: float, t: float, call: bool) -> float:
    """Independent undiscounted Bachelier: (F−K)Φ(d) + σ√t·φ(d), d = (F−K)/(σ√t)."""
    if vol <= 0.0 or t <= 0.0:
        return max(f - k, 0.0) if call else max(k - f, 0.0)
    s = vol * math.sqrt(t)
    d = (f - k) / s
    if call:
        return (f - k) * _phi(d) + s * _pdf(d)
    return (k - f) * _phi(-d) + s * _pdf(d)


# ── bachelier: the normal-model sibling of black ───────────────────────────────────────────
def test_bachelier_matches_independent_normal_formula() -> None:
    for f in (-0.004, 0.0, 0.012, 0.035):
        for k in (-0.01, 0.0, 0.02, 0.05):
            for vol in (0.0008, 0.004, 0.02):
                for t in (0.25, 1.0, 7.0):
                    for ot, call in ((CALL, True), (PUT, False)):
                        assert abs(bachelier(f, k, vol, t, ot) - _ref_bachelier(f, k, vol, t, call)) < 1e-15


def test_bachelier_put_call_parity_is_exact() -> None:
    # call − put = F − K under the normal law, for ANY sign of F and K (the lognormal cannot)
    for f in (-0.01, 0.0, 0.03):
        for k in (-0.02, 0.0, 0.04):
            c = bachelier(f, k, 0.005, 2.0, CALL)
            p = bachelier(f, k, 0.005, 2.0, PUT)
            assert abs((c - p) - (f - k)) < 1e-15


def test_bachelier_degenerate_returns_forward_intrinsic() -> None:
    assert bachelier(-0.01, -0.02, 0.0, 1.0, CALL) == pytest.approx(0.01, abs=1e-15)
    assert bachelier(-0.01, -0.02, 0.005, 0.0, CALL) == pytest.approx(0.01, abs=1e-15)
    assert bachelier(-0.02, -0.01, 0.0, 1.0, CALL) == 0.0  # out of the money
    assert bachelier(-0.02, -0.01, 0.0, 1.0, PUT) == pytest.approx(0.01, abs=1e-15)


# ── the β=0 normal SABR expansion ──────────────────────────────────────────────────────────
def test_sabr_normal_vol_rho_zero_is_the_asinh_closed_form() -> None:
    # ρ=0 ⇒ x(z) = log(√(1+z²) + z) = asinh(z), so σ_N = α·z/asinh(z)·(1 + ν²t/12).
    # `math.asinh` is a genuinely independent code path from the implementation's log/sqrt.
    a, nu, t = 0.006, 0.45, 2.0
    params = SabrParams(alpha=a, beta=0.0, rho=0.0, nu=nu)
    for f, k in ((0.02, 0.03), (0.02, 0.005), (-0.004, 0.01), (0.01, -0.006)):
        z = (nu / a) * (f - k)
        expected = a * (z / math.asinh(z)) * (1.0 + (2.0 - 0.0) / 24.0 * nu * nu * t)
        assert abs(sabr_normal_vol(f, k, t, params) - expected) < 1e-15


def test_sabr_normal_vol_nu_zero_is_alpha_at_every_strike() -> None:
    # the closed-form anchor: zero vol-of-vol ⇒ the normal SABR IS Bachelier with σ_N = α,
    # at EVERY strike and for NEGATIVE forwards/strikes too (no log(F/K) anywhere)
    params = SabrParams(alpha=0.0075, beta=0.0, rho=-0.3, nu=0.0)
    for f in (-0.01, 0.0, 0.02):
        for k in (-0.03, 0.0, 0.015, 0.06):
            assert abs(sabr_normal_vol(f, k, 3.0, params) - 0.0075) < 1e-16


def test_sabr_normal_vol_atm_branch() -> None:
    # F=K ⇒ z=0, the removable singularity: σ_N = α(1 + (2−3ρ²)ν²t/24)
    a, rho, nu, t = 0.006, -0.35, 0.5, 1.5
    params = SabrParams(alpha=a, beta=0.0, rho=rho, nu=nu)
    expected = a * (1.0 + (2.0 - 3.0 * rho * rho) / 24.0 * nu * nu * t)
    assert abs(sabr_normal_vol(0.021, 0.021, t, params) - expected) < 1e-16


def test_sabr_normal_vol_skew_orientation() -> None:
    # ρ<0 tilts the NORMAL smile the same way it tilts the lognormal one: low strikes carry more vol
    params = SabrParams(alpha=0.006, beta=0.0, rho=-0.5, nu=0.5)
    low = sabr_normal_vol(0.02, 0.01, 1.0, params)
    high = sabr_normal_vol(0.02, 0.03, 1.0, params)
    assert low > high


def test_sabr_normal_vol_rejects_a_non_zero_beta() -> None:
    # the NORMAL law is the β=0 dynamics; a general-β CEV quoted in normal-vol units is a
    # CONVERSION, deferred to its first consumer (see OPEN.md) — never silently approximated
    with pytest.raises(ValueError):
        sabr_normal_vol(0.02, 0.03, 1.0, SabrParams(0.2, 0.5, -0.3, 0.4))


def test_normal_and_lognormal_laws_price_the_same_beta0_dynamics() -> None:
    # SCALE oracle (approximation, not identity): σ_B (eq 2.17a) and σ_N (β=0 normal SABR) describe
    # ONE model, so their prices agree to the order of the expansions. A conversion that is off by a
    # factor of F (the quarry's σ_B·√(FK)) fails this by orders of magnitude.
    f, t = 0.030, 1.0
    # β=0 ⇒ α is in ABSOLUTE rate units: σ_B = α/√(FK) ≈ 25% and σ_N ≈ α = 75bp are the SAME
    # dynamics, so ONE SabrParams serves both laws and the two prices must agree.
    params = SabrParams(alpha=0.0075, beta=0.0, rho=-0.2, nu=0.3)
    for k in (0.026, 0.030, 0.034):
        p_ln = black(f, k, sabr_vol(f, k, t, params), t, CALL)
        p_nm = bachelier(f, k, sabr_normal_vol(f, k, t, params), t, CALL)
        assert abs(p_ln - p_nm) / max(p_ln, 1e-12) < 5e-4  # measured ~1e-4; the quarry conversion ~3e-3


# ── the laws as values ─────────────────────────────────────────────────────────────────────
def test_every_law_satisfies_the_protocol() -> None:
    for law in (Lognormal(), ShiftedLognormal(0.03), Normal()):
        assert isinstance(law, VolLaw)


def test_lognormal_price_delegates_to_black() -> None:
    for k in (0.01, 0.035, 0.09):
        assert Lognormal().price(0.035, k, 0.2, 1.0, CALL) == black(0.035, k, 0.2, 1.0, CALL)


def test_shifted_lognormal_with_zero_shift_is_the_lognormal_law() -> None:
    plain, shifted = Lognormal(), ShiftedLognormal(0.0)
    params = SabrParams(0.2, 0.5, -0.3, 0.4)
    for k in (0.005, 0.035, 0.12):
        assert shifted.price(0.035, k, 0.2, 1.0, CALL) == plain.price(0.035, k, 0.2, 1.0, CALL)
        assert shifted.sabr_vol(0.035, k, 1.0, params) == plain.sabr_vol(0.035, k, 1.0, params)


def test_shifted_lognormal_shifts_both_arguments() -> None:
    s = 0.03
    law = ShiftedLognormal(s)
    params = SabrParams(0.2, 0.5, -0.3, 0.4)
    f, k = -0.005, 0.01  # a NEGATIVE forward: the shifted pair is positive, the law is defined
    assert law.price(f, k, 0.2, 1.0, CALL) == black(f + s, k + s, 0.2, 1.0, CALL)
    assert law.sabr_vol(f, k, 1.0, params) == sabr_vol(f + s, k + s, 1.0, params)


def test_each_law_knows_its_own_domain() -> None:
    assert Lognormal().defined(0.02, 0.03) and not Lognormal().defined(-0.001, 0.03)
    assert not Lognormal().defined(0.02, 0.0)
    assert ShiftedLognormal(0.03).defined(-0.005, 0.01)  # F+s > 0, K+s > 0
    assert not ShiftedLognormal(0.03).defined(-0.04, 0.01)  # F+s < 0
    assert Normal().defined(-0.05, -0.09)  # the normal law is defined everywhere
    assert Normal().defined(0.0, 0.0)


def test_vol_law_for_is_the_one_tag_to_law_mapping() -> None:
    assert vol_law_for(VolLawKind.LOGNORMAL, 0.0) == Lognormal()
    assert vol_law_for(VolLawKind.NORMAL, 0.0) == Normal()
    assert vol_law_for(VolLawKind.SHIFTED_LOGNORMAL, 0.03) == ShiftedLognormal(0.03)


def test_sabr_surface_validates_its_law_tag() -> None:
    params = SabrParams(0.2, 0.5, -0.3, 0.4)
    with pytest.raises(ValueError):  # a shift only means something under the SHIFTED law
        SabrSurface({EXPIRY: params}, VolLawKind.LOGNORMAL, 0.03)
    with pytest.raises(ValueError):  # …and the SHIFTED law needs a positive one
        SabrSurface({EXPIRY: params}, VolLawKind.SHIFTED_LOGNORMAL, 0.0)
    with pytest.raises(ValueError):  # the NORMAL law is the β=0 dynamics
        SabrSurface({EXPIRY: params}, VolLawKind.NORMAL, 0.0)
    SabrSurface({EXPIRY: SabrParams(0.006, 0.0, -0.3, 0.4)}, VolLawKind.NORMAL, 0.0)  # ok
