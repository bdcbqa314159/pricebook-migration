"""L4 oracles — the SABR swaption smile, read-not-solved (T1 slice 25).

**The teeth are in oracle 1, and they moved.** Under the threaded-forward signature, "do the vol's S
and the engine's S match?" is trivially true — the engine passes its own S — so asking it would be
vacuous, worse than no oracle at all. The oracle that still reds under any reconstruct-S design is
STRUCTURAL: price an ATM payer on a **NON-CANONICAL** underlying (a semi-annual schedule on a 3M
index, the `batch_c` shape) struck at the engine's marked S, and assert the mark equals
`annuity · black(S, S, σ_SABR(S, S))` — the ATM branch evaluated at the **engine's** S. A model that
rebuilt S from `(index, expiry, swap_tenor)` would evaluate the smile tens of basis points away; the
test asserts that failure mode explicitly, at both the vol and the PV level, so it reds under any
reconstruct-S design and greens only when the threaded S flows end-to-end. That is the §6
structural-oracle rule applied here: it tests the decomposition, not a scalar off it.

*(The mandate phrased this as "lands on the smile minimum". With ρ ≠ 0 and β < 1 the ATM point is
not the minimum — a SABR smile with a CEV backbone is a skew — so the oracle asserts the ATM
**branch** at the marked S instead, which is the discriminating content and strictly stronger.)*
"""

import math
from datetime import date

from pricebook.engine import price
from pricebook.engine.vanilla_option import underlying_tenor
from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    PricingFailure,
    PricingResult,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    get_rate_index,
)
from pricebook.market.building_blocks import float_leg_pv, rpv01
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot
from pricebook.market.vol_surface import (
    SabrParams,
    SabrSurface,
    Surface,
    SwaptionSurfaceKey,
    VolLawKind,
)
from pricebook.models.bachelier import bachelier
from pricebook.models.black import black
from pricebook.models.black_model import BlackModel
from pricebook.models.sabr import sabr_normal_vol, sabr_vol
from pricebook.models.sabr_model import SABRModel
from pricebook.models.vol_law import Normal, vol_law_for
from pricebook.products.option import OptionType, Swaption
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap

VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
DC365 = DayCountConvention.ACT_365_FIXED
Y, M = TenorUnit.YEAR, TenorUnit.MONTH
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(10, Y)
EXPIRY = VAL + Tenor(1, Y)
TENOR = Tenor(5, Y)
NOTIONAL = 1.0
PARAMS = SabrParams(alpha=0.20, beta=0.5, rho=-0.30, nu=0.40)


def _curves(proj_rate: float = 0.035) -> CurveSet:
    return CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.030, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, proj_rate, until=FAR),
        }
    )


def _swap(freq: Frequency, strike: float, tenor: Tenor = TENOR) -> VanillaSwap:
    sched = build_schedule(EXPIRY, EXPIRY + tenor, ScheduleTerms(frequency=freq, roll=RollRule(calendar=None)))
    return VanillaSwap(NOTIONAL, CCY, FixedLeg(sched, DC365, strike), FloatLeg(sched, DC365, INDEX))


def _marked_s(swap: VanillaSwap, curves: CurveSet) -> tuple[float, float]:
    """The engine's own S and annuity, composed from the SAME shared atoms it uses."""
    disc, proj = curves.discount(CCY), curves.projection(INDEX)
    annuity = rpv01(swap.fixed_leg.schedule, swap.fixed_leg.day_count, disc)
    return float_leg_pv(swap.float_leg.schedule, swap.float_leg.day_count, disc, proj) / annuity, annuity


def _model(
    curves: CurveSet,
    params: SabrParams,
    kind: VolLawKind = VolLawKind.LOGNORMAL,
    shift: float = 0.0,
) -> SABRModel:
    """A SABR model over a swaption cube node: `{SwaptionSurfaceKey(index, tenor) → SabrSurface}` and
    nothing else — no cube type (the quarry's `SwaptionVolCube` is not ported)."""
    snap = MarketSnapshot(
        VAL, curves, surfaces={SwaptionSurfaceKey(INDEX, TENOR): SabrSurface({EXPIRY: params}, kind, shift)}
    )
    return SABRModel(snap, vol_law_for(kind, shift))


# ── 1. THE STRUCTURAL ORACLE — a NON-CANONICAL underlying ──────────────────────────────────
def test_atm_payer_on_a_NON_CANONICAL_underlying_prices_at_the_marked_S() -> None:
    # the batch_c shape: SEMI-ANNUAL periods on a 3M index. Its S differs from every
    # reconstruct-from-conventions candidate by tens of basis points, so this reds unless the
    # engine's marked S is the one the smile is evaluated at.
    curves = _curves()
    semi = _swap(Frequency.SEMI_ANNUAL, 0.0)
    s, annuity = _marked_s(semi, curves)
    assert underlying_tenor(semi) == TENOR  # the cube key the engine will look up
    # the premise: a canonical-annual reconstruction would land ~30bp away from this S
    annual_s, _ = _marked_s(_swap(Frequency.ANNUAL, 0.0), curves)
    assert abs(annual_s - s) > 2e-4

    atm = _swap(Frequency.SEMI_ANNUAL, s)  # struck exactly AT the engine's marked S
    model = _model(curves, PARAMS)
    out = price(Swaption(atm, EXPIRY, OptionType.CALL), model)
    assert isinstance(out, PricingResult), out

    t = TM.year_fraction(EXPIRY)
    # struck at the marked S ⇒ F = K ⇒ the SABR **ATM branch** (the eq-2.18 removable singularity).
    # NB: with ρ = −0.3 and β = 0.5 this is NOT the smile's minimum — a SABR smile with ρ ≠ 0 and a
    # CEV backbone is a SKEW, and the ATM point is neither a minimum nor a maximum. The
    # discriminating statement is that the vol is evaluated at the ENGINE's S, which is what follows.
    atm_vol = sabr_vol(s, s, t, PARAMS)
    expected = NOTIONAL * annuity * black(s, s, atm_vol, t, OptionType.CALL)
    assert abs(out.pv.amount - expected) < 1e-12

    # THE TEETH, quantified: what a reconstruct-S model would have produced instead. Rebuilding the
    # underlying as the canonical ANNUAL swap displaces S by ~31bp, which moves the vol by ~26bp and
    # the PV by ~1.5% — so this oracle reds under any design that derives S instead of receiving it.
    wrong_vol = sabr_vol(annual_s, s, t, PARAMS)
    assert abs(wrong_vol - atm_vol) > 1e-4
    wrong_pv = NOTIONAL * annuity * black(s, s, wrong_vol, t, OptionType.CALL)
    assert abs(wrong_pv - expected) / expected > 1e-3


def test_the_same_holds_for_the_canonical_annual_underlying() -> None:
    # the control: the oracle is about the threaded S, not about semi-annual schedules
    curves = _curves()
    s, annuity = _marked_s(_swap(Frequency.ANNUAL, 0.0), curves)
    atm = _swap(Frequency.ANNUAL, s)
    out = price(Swaption(atm, EXPIRY, OptionType.CALL), _model(curves, PARAMS))
    assert isinstance(out, PricingResult), out
    t = TM.year_fraction(EXPIRY)
    expected = NOTIONAL * annuity * black(s, s, sabr_vol(s, s, t, PARAMS), t, OptionType.CALL)
    assert abs(out.pv.amount - expected) < 1e-12


# ── 2. Hagan reference, across the smile ───────────────────────────────────────────────────
def test_swaption_smile_matches_an_independent_hagan_reference() -> None:
    def ref_hagan(f: float, k: float, t: float, p: SabrParams) -> float:
        a, b, rho, nu = p.alpha, p.beta, p.rho, p.nu
        one_mb = 1.0 - b
        log_fk = math.log(f / k)
        fk = (f * k) ** (one_mb / 2.0)
        z = nu / a * fk * log_fk
        zx = 1.0 if abs(z) < 1e-12 else z / math.log(
            (math.sqrt(1.0 - 2.0 * rho * z + z * z) + z - rho) / (1.0 - rho)
        )
        denom = fk * (1.0 + one_mb**2 / 24.0 * log_fk**2 + one_mb**4 / 1920.0 * log_fk**4)
        corr = (one_mb**2 / 24.0 * a * a / (f * k) ** one_mb
                + 0.25 * rho * b * nu * a / fk
                + (2.0 - 3.0 * rho * rho) / 24.0 * nu * nu)
        return a / denom * zx * (1.0 + corr * t)

    curves = _curves()
    s, annuity = _marked_s(_swap(Frequency.ANNUAL, 0.0), curves)
    model = _model(curves, PARAMS)
    t = TM.year_fraction(EXPIRY)
    for strike in (s - 0.010, s - 0.004, s + 0.004, s + 0.012):
        swap = _swap(Frequency.ANNUAL, strike)
        out = price(Swaption(swap, EXPIRY, OptionType.CALL), model)
        assert isinstance(out, PricingResult), out
        s_k, annuity_k = _marked_s(swap, curves)
        expected = NOTIONAL * annuity_k * black(s_k, strike, ref_hagan(s_k, strike, t, PARAMS), t, OptionType.CALL)
        assert abs(out.pv.amount - expected) < 1e-12


def test_payer_receiver_parity_holds_across_the_smile() -> None:
    # parity composed from the atoms alone: payer − receiver = annuity·(S − K), no option formula
    curves = _curves()
    model = _model(curves, PARAMS)
    for strike in (0.025, 0.035, 0.045):
        swap = _swap(Frequency.ANNUAL, strike)
        s, annuity = _marked_s(swap, curves)
        payer = price(Swaption(swap, EXPIRY, OptionType.CALL), model)
        receiver = price(Swaption(swap, EXPIRY, OptionType.PUT), model)
        assert isinstance(payer, PricingResult) and isinstance(receiver, PricingResult)
        assert abs((payer.pv.amount - receiver.pv.amount) - NOTIONAL * annuity * (s - strike)) < 1e-12


# ── 3. Multi-law: a NEGATIVE forward swap rate ─────────────────────────────────────────────
def test_normal_law_swaption_prices_a_negative_forward_swap_rate() -> None:
    curves = _curves(proj_rate=-0.006)
    params = SabrParams(alpha=0.0060, beta=0.0, rho=-0.3, nu=0.4)
    swap = _swap(Frequency.ANNUAL, -0.004)
    s, annuity = _marked_s(swap, curves)
    assert s < 0.0  # the premise
    model = _model(curves, params, VolLawKind.NORMAL)
    out = price(Swaption(swap, EXPIRY, OptionType.CALL), model)
    assert isinstance(out, PricingResult), out
    t = TM.year_fraction(EXPIRY)
    vol = sabr_normal_vol(s, -0.004, t, params)
    expected = NOTIONAL * annuity * bachelier(s, -0.004, vol, t, OptionType.CALL)
    assert abs(out.pv.amount - expected) < 1e-12


def test_lognormal_law_swaption_refuses_a_negative_forward_swap_rate() -> None:
    curves = _curves(proj_rate=-0.006)
    out = price(Swaption(_swap(Frequency.ANNUAL, -0.004), EXPIRY, OptionType.CALL),
                _model(curves, PARAMS))
    assert isinstance(out, PricingFailure)
    assert "Lognormal" in out.reason


# ── structural reads ───────────────────────────────────────────────────────────────────────
def test_a_flat_surface_under_a_sabr_swaption_is_a_failure_value() -> None:
    curves = _curves()
    snap = MarketSnapshot(VAL, curves, surfaces={SwaptionSurfaceKey(INDEX, TENOR): Surface.flat(0.2)})
    out = price(Swaption(_swap(Frequency.ANNUAL, 0.035), EXPIRY, OptionType.CALL), SABRModel(snap))
    assert isinstance(out, PricingFailure)
    assert "SabrSurface" in out.reason


def test_a_law_mismatch_between_model_and_cube_is_a_failure_value() -> None:
    # the slice-22 guard, now exercised through the swaption key too
    curves = _curves()
    surface = SabrSurface({EXPIRY: PARAMS}, VolLawKind.LOGNORMAL, 0.0)
    snap = MarketSnapshot(VAL, curves, surfaces={SwaptionSurfaceKey(INDEX, TENOR): surface})
    out = price(Swaption(_swap(Frequency.ANNUAL, 0.035), EXPIRY, OptionType.CALL),
                SABRModel(snap, Normal()))
    assert isinstance(out, PricingFailure)
    assert "law" in out.reason


def test_sabr_model_carries_both_vol_capabilities() -> None:
    # doc 22 Q1: two opt-in capabilities on one model, no fat base class, no type ladder
    from pricebook.models.protocols import CalibratedModel, ImpliedVol, SwaptionVol
    model = _model(_curves(), PARAMS)
    assert isinstance(model, CalibratedModel)
    assert isinstance(model, ImpliedVol)
    assert isinstance(model, SwaptionVol)


def test_blackmodel_swaption_still_prices_off_a_flat_surface() -> None:
    # the amendment's byte-identicality claim, asserted in-suite: BlackModel ignores the new arg
    curves = _curves()
    swap = _swap(Frequency.ANNUAL, 0.035)
    s, annuity = _marked_s(swap, curves)
    snap = MarketSnapshot(VAL, curves, surfaces={SwaptionSurfaceKey(INDEX, TENOR): Surface.flat(0.22)})
    out = price(Swaption(swap, EXPIRY, OptionType.CALL), BlackModel(snap))
    assert isinstance(out, PricingResult), out
    t = TM.year_fraction(EXPIRY)
    expected = NOTIONAL * annuity * black(s, 0.035, 0.22, t, OptionType.CALL)
    assert abs(out.pv.amount - expected) < 1e-12
