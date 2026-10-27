"""The `SwaptionPrice` capability (`rulings_CP_xva_mc.md` §6) — making the 381bp unwritable.

Hull-White could not satisfy `SwaptionVol` honestly: that capability is keyed by
`(index, expiry, swap_tenor, strike)`, and Jamshidian needs the underlying's whole **coupon flow
set**. HW therefore had to *reconstruct* a swap, and the reconstruction was wrong by **381bp** on a
semi-annual underlying — guarded by an S-identity check, but still a guess.

`SwaptionPrice.swaption_price(swap, expiry, kind)` takes the **actual swap**, so there is nothing to
reconstruct and nothing to guard. This file asserts both halves: the previously-wrong case is now
*right by construction*, and the reconstruction machinery is **gone** — the `ProtectionWindow`
pattern, where the defect becomes unwritable rather than detected.
"""

import inspect
from datetime import date

from pricebook.engine import price
from pricebook.foundation import (
    DayCountConvention,
    Frequency,
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
from pricebook.models.hull_white import HullWhite
from pricebook.models.protocols import SwaptionPrice, SwaptionVol
from pricebook.products.option import OptionType, Swaption
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
CCY = INDEX.id.currency
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(30, Y)
EXPIRY = VAL + Tenor(2, Y)
TENOR = Tenor(5, Y)
RATE, A, SIGMA = 0.030, 0.05, 0.010


def _curves() -> CurveSet:
    return CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, RATE, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, RATE, until=FAR),
        }
    )


def _hw() -> HullWhite:
    return HullWhite(MarketSnapshot(VAL, _curves()), A, SIGMA, CCY)


def _swap(strike: float, freq: Frequency) -> VanillaSwap:
    sched = build_schedule(
        EXPIRY, EXPIRY + TENOR, ScheduleTerms(frequency=freq, roll=RollRule(calendar=None))
    )
    return VanillaSwap(1.0, CCY, FixedLeg(sched, DC365, strike), FloatLeg(sched, DC365, INDEX))


# ── THE SLICE'S POINT — the 381bp case is now right BY CONSTRUCTION ──────────────────────
def test_the_semi_annual_underlying_that_was_wrong_by_381bp_now_prices_exactly() -> None:
    """Before this slice the engine refused this swaption (the S-identity guard) because HW's
    reconstruction implied a different underlying; before the guard, it mispriced it by 381bp.
    The capability now hands HW the actual swap, so engine and model agree to machine precision."""
    hw = _hw()
    for strike in (0.025, 0.030, 0.035):
        swap = _swap(strike, Frequency.SEMI_ANNUAL)
        own = hw.swaption_price(swap, EXPIRY, OptionType.CALL)
        out = price(Swaption(swap, EXPIRY, OptionType.CALL), hw)
        assert isinstance(out, PricingResult), (strike, out)
        assert abs(out.pv.amount - own) < 1e-12 * max(1.0, abs(own)), (strike, out.pv.amount, own)


def test_every_underlying_frequency_agrees_now_not_just_the_canonical_one() -> None:
    hw = _hw()
    for freq in (Frequency.ANNUAL, Frequency.SEMI_ANNUAL, Frequency.QUARTERLY):
        swap = _swap(0.030, freq)
        own = hw.swaption_price(swap, EXPIRY, OptionType.CALL)
        out = price(Swaption(swap, EXPIRY, OptionType.CALL), hw)
        assert isinstance(out, PricingResult), out
        assert abs(out.pv.amount - own) < 1e-12 * max(1.0, abs(own))


# ── the reconstruction is GONE, not merely unused ────────────────────────────────────────
def test_the_reconstruction_machinery_is_DELETED() -> None:
    """Make-it-unwritable, the `ProtectionWindow` pattern. A fallback left in place is a fallback
    someone reaches for: the guess and its guard are removed, and their absence is asserted so the
    next reader cannot reintroduce them without this failing."""
    # Assert the MACHINERY is gone, not the vocabulary: the module still *explains* why the
    # reconstruction was removed, and a word-grep would flag that prose — the same false positive
    # the debt gate hits when a comment mentions a suppression. Structure is the thing to check.
    assert not hasattr(HullWhite, "_pending_swap")       # the guess
    assert not hasattr(HullWhite, "swaption_vol")        # the capability that forced it
    module = inspect.getmodule(HullWhite)
    assert not hasattr(module, "_S_IDENTITY_TOL")        # the guard the guess needed
    assert not hasattr(HullWhite, "vol_law")             # and the Black-vol inversion with it


def test_hull_white_satisfies_SwaptionPrice_and_no_longer_claims_SwaptionVol() -> None:
    """HW is a *pricing* model, not a surface — the capability it satisfies now says so. Claiming
    `SwaptionVol` was the category error that produced the 381bp."""
    hw = _hw()
    assert isinstance(hw, SwaptionPrice)
    assert not isinstance(hw, SwaptionVol)


def test_the_capability_takes_the_whole_swap_not_a_surface_key() -> None:
    params = list(inspect.signature(SwaptionPrice.swaption_price).parameters)
    assert params == ["self", "swap", "expiry", "kind"]
    assert "swap_tenor" not in params and "strike" not in params


# ── the engine dispatches structurally, and the vol path is untouched ────────────────────
def test_the_engine_prefers_the_price_capability_and_falls_back_to_the_vol_one() -> None:
    """Structural protocol-membership dispatch, the `ImpliedVol`/`SwaptionVol` pattern — no
    `isinstance` on the *instrument*, and no branch naming a concrete model."""
    from pricebook.engine import vanilla_option

    source = inspect.getsource(vanilla_option.price_swaption)
    assert "SwaptionPrice" in source and "SwaptionVol" in source
    assert "HullWhite" not in source and "SABRModel" not in source and "BlackModel" not in source


def test_a_model_with_neither_capability_is_a_failure_value() -> None:
    from pricebook.foundation import PricingFailure
    from pricebook.models.discounting_model import DiscountingModel

    out = price(
        Swaption(_swap(0.030, Frequency.ANNUAL), EXPIRY, OptionType.CALL),
        DiscountingModel(MarketSnapshot(VAL, _curves())),
    )
    assert isinstance(out, PricingFailure), out


# ── HW's own identities still hold through the new path ──────────────────────────────────
def test_payer_receiver_parity_still_holds_through_the_engine() -> None:
    """Model-independent: `payer − receiver = annuity·(S − K)`. Now checked through the *engine*,
    so it validates the capability wiring and not only HW's internals."""
    hw = _hw()
    curves = hw.market.curves
    for freq in (Frequency.ANNUAL, Frequency.SEMI_ANNUAL):
        atm = _swap(0.0, freq)
        annuity = rpv01(atm.fixed_leg.schedule, atm.fixed_leg.day_count, curves.discount(CCY))
        s = float_leg_pv(
            atm.float_leg.schedule, atm.float_leg.day_count, curves.discount(CCY),
            curves.projection(INDEX),
        ) / annuity
        for strike in (s - 0.01, s, s + 0.01):
            swap = _swap(strike, freq)
            payer = price(Swaption(swap, EXPIRY, OptionType.CALL), hw)
            receiver = price(Swaption(swap, EXPIRY, OptionType.PUT), hw)
            assert isinstance(payer, PricingResult) and isinstance(receiver, PricingResult)
            assert abs((payer.pv.amount - receiver.pv.amount) - annuity * (s - strike)) < 1e-8
