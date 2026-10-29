"""`TimeBump` and theta — the market's clock advances, the contract does not.

Theta is the one first-order greek that is **not** a market-data bump: it moves time. The two
ways to get it are not equivalent, and only one is legal here.

- **Bump the instrument's expiry** — forbidden. That mutates the *product* (§1, the same rule that
  kept recovery off the L2 `CDS`), and it also answers a different question: a shorter-dated
  contract, not the same contract seen tomorrow.
- **Advance the market's `valuation_date` and forward-start the curves** — what `TimeBump` does.
  `df_new(T) = df_old(T)/df_old(t+Δt)`, market otherwise held, so `r`, `q`, `σ` and spot are
  unchanged and only the clock moves.

The oracle is the Black-Scholes closed-form theta against that finite difference (the slice-0
analytic-vs-FD pattern). The reference is written in spot form and never forward-starts anything,
so it is an independent statement of the same derivative.
"""

import math
from datetime import date, timedelta

import pytest
from scipy.stats import norm

from pricebook.foundation import Currency
from pricebook.foundation.equity import EquityUnderlying
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import DividendYieldKey, EquitySpotKey, MarketSnapshot
from pricebook.market.vol_surface import EquitySurfaceKey, Surface
from pricebook.models.black import vol_time_measure
from pricebook.models.black_model import BlackModel
from pricebook.products.equity import EquityOption
from pricebook.products.option import OptionType
from pricebook.risk.bump import TimeBump
from pricebook.risk.greeks import theta
from pricebook.risk.priceable import priceable

VAL = date(2026, 1, 15)
ACME = EquityUnderlying("ACME")
EXPIRY = VAL + timedelta(days=365)
S, VOL, R, Q, T = 100.0, 0.20, 0.05, 0.03, 1.0
USD_DISCOUNT = CurveKey(CurveRole.DISCOUNT, Currency.USD, None)


def _market(spot: float = S, vol: float = VOL, q: float = Q) -> MarketSnapshot:
    curve = DiscountCurve(
        time_measure=vol_time_measure(VAL), times=(0.0, 10.0), dfs=(1.0, math.exp(-R * 10.0))
    )
    return MarketSnapshot(
        valuation_date=VAL,
        curves=CurveSet({USD_DISCOUNT: curve}),
        scalars={EquitySpotKey(ACME): spot, DividendYieldKey(ACME): q},
        surfaces={EquitySurfaceKey(ACME): Surface(vols=(vol,))},
    )


def _opt(strike: float = 100.0, kind: OptionType = OptionType.CALL) -> EquityOption:
    return EquityOption(underlying=ACME, strike=strike, expiry=EXPIRY, option_type=kind)


def _p(option: EquityOption):
    return priceable(option, BlackModel)


def _bs_theta(k: float, call: bool = True) -> float:
    """`∂V/∂t` holding (S, r, q, σ) — the standard Black-Scholes-Merton theta, calendar-time
    signed (so it is the NEGATIVE of `∂V/∂T`)."""
    d1 = (math.log(S / k) + (R - Q + 0.5 * VOL * VOL) * T) / (VOL * math.sqrt(T))
    d2 = d1 - VOL * math.sqrt(T)
    carry = -S * math.exp(-Q * T) * norm.pdf(d1) * VOL / (2.0 * math.sqrt(T))
    if call:
        return carry + Q * S * math.exp(-Q * T) * norm.cdf(d1) - R * k * math.exp(-R * T) * norm.cdf(d2)
    return carry - Q * S * math.exp(-Q * T) * norm.cdf(-d1) + R * k * math.exp(-R * T) * norm.cdf(-d2)


# ── the headline oracle ─────────────────────────────────────────────────────────────────────
def test_theta_matches_the_black_scholes_closed_form() -> None:
    """One business-day forward difference against the closed form. The FD tolerance is loose on
    purpose: a one-sided difference is `O(Δt)` accurate, and Δt = 1/365 — so ~1e-2 absolute on a
    theta of order −6 is the truncation error, not a defect. Tightening it would mean asserting
    the closed form against itself."""
    for strike in (80.0, 100.0, 125.0):
        for kind, call in ((OptionType.CALL, True), (OptionType.PUT, False)):
            got = theta(_p(_opt(strike, kind)), _market())
            want = _bs_theta(strike, call)
            assert got == pytest.approx(want, abs=2e-2), (strike, kind, got, want)


def test_theta_converges_to_the_closed_form_as_the_step_shrinks() -> None:
    """The real evidence that it is the right derivative and not merely a close number: the
    forward difference is `O(Δt)`, so halving the step must roughly halve the error. A wrong
    construction (an expiry bump, a curve not forward-started) would converge to a *different*
    limit, which a single tolerance cannot distinguish."""
    want = _bs_theta(100.0)
    errs = [abs(theta(_p(_opt()), _market(), days=d) - want) for d in (16, 8, 4, 2)]
    assert errs == sorted(errs, reverse=True), errs
    assert errs[0] / errs[-1] > 4.0, errs  # 8x step reduction ⇒ well over 4x error reduction


def test_a_long_option_DECAYS_theta_is_negative_for_both_types_at_the_money() -> None:
    assert theta(_p(_opt()), _market()) < 0.0
    assert theta(_p(_opt(kind=OptionType.PUT)), _market()) < 0.0


# ── the construction itself ─────────────────────────────────────────────────────────────────
def test_the_time_bump_forward_starts_the_curve_rather_than_shifting_rates() -> None:
    """`df_new(T) = df_old(T)/df_old(t+Δt)`. Checked directly, because this is the step that
    makes theta mean "the same contract tomorrow" rather than "a cheaper contract today"."""
    base = _market()
    bumped = TimeBump().apply(base, 30.0)
    t_plus = VAL + timedelta(days=30)
    assert bumped.valuation_date == t_plus
    old = base.curves.discount(Currency.USD, None)
    new = bumped.curves.discount(Currency.USD, None)
    for horizon in (90, 180, 365, 730):
        d = VAL + timedelta(days=horizon)
        assert new.df(d) == pytest.approx(old.df(d) / old.df(t_plus), rel=1e-12), horizon


def test_the_forward_started_curve_implies_the_SAME_zero_rate() -> None:
    """Market held means the *rates* are unchanged — only the clock moved. On a flat 5% curve the
    forward-started curve must still imply 5%, which is what distinguishes a re-anchoring from a
    parallel shift."""
    bumped = TimeBump().apply(_market(), 30.0)
    curve = bumped.curves.discount(Currency.USD, None)
    t_plus = VAL + timedelta(days=30)
    for horizon in (90, 365, 730):
        d = t_plus + timedelta(days=horizon)
        implied = -math.log(curve.df(d)) / (horizon / 365.0)
        assert implied == pytest.approx(R, rel=1e-9), horizon


def test_the_base_snapshot_is_never_mutated() -> None:
    base = _market()
    TimeBump().apply(base, 30.0)
    assert base.valuation_date == VAL
    assert base.curves.discount(Currency.USD, None).df(EXPIRY) == pytest.approx(math.exp(-R * T))


def test_theta_is_NOT_an_expiry_bump_AND_A_FLAT_CURVE_CANNOT_TELL_THEM_APART() -> None:
    """Guards the §1 call — and records why this test needs a SLOPED curve to do it.

    On a **flat** curve the two constructions are identical to the last bit:
    forward-starting gives `df(T)/df(Δ) = e^{−r(T−Δ)}`, and the expiry bump reads
    `df(T−Δ) = e^{−r(T−Δ)}` — the same number. So a flat fixture cannot distinguish a correct
    re-anchoring from an instrument mutation, and a test written on one would have passed
    whichever had been implemented. That is the structural-oracle rule in miniature (§6): a flat
    input strips flat whatever the construction's shape.

    With a **sloped** curve they separate, because forward-starting carries the whole remaining
    curve onto the new anchor while the expiry bump just reads an earlier point on the old one.
    """
    sloped = MarketSnapshot(
        valuation_date=VAL,
        curves=CurveSet(
            {
                USD_DISCOUNT: DiscountCurve(
                    time_measure=vol_time_measure(VAL),
                    times=(0.0, 0.5, 1.0, 2.0, 10.0),
                    dfs=(1.0, math.exp(-0.02 * 0.5), math.exp(-0.04 * 1.0),
                         math.exp(-0.055 * 2.0), math.exp(-0.07 * 10.0)),
                )
            }
        ),
        scalars={EquitySpotKey(ACME): S, DividendYieldKey(ACME): Q},
        surfaces={EquitySurfaceKey(ACME): Surface(vols=(VOL,))},
    )
    clock = theta(_p(_opt()), sloped, days=30)

    shorter = EquityOption(ACME, 100.0, EXPIRY - timedelta(days=30), OptionType.CALL)
    now = _p(_opt()).price_at(sloped)
    short = _p(shorter).price_at(sloped)
    expiry_bump = (short.pv.amount - now.pv.amount) / (30.0 / 365.0)

    assert clock != pytest.approx(expiry_bump, abs=1e-6), (clock, expiry_bump)
    # and the flat-curve degeneracy, asserted so the reason above cannot rot:
    flat_clock = theta(_p(_opt()), _market(), days=30)
    flat_short = _p(shorter).price_at(_market())
    flat_now = _p(_opt()).price_at(_market())
    flat_expiry = (flat_short.pv.amount - flat_now.pv.amount) / (30.0 / 365.0)
    assert flat_clock == pytest.approx(flat_expiry, rel=1e-12)


def test_a_curve_role_this_slice_cannot_re_anchor_is_REFUSED() -> None:
    """The bounded scope, asserted where it can be: a `df` curve forward-starts by the ratio
    identity, but a SURVIVAL curve is anchored too and re-anchoring it is not implemented. Rolling
    the clock and leaving it untouched would hand back a wrong CDS theta with no error, so the
    snapshot is refused instead.

    (The *other* boundary — a cashflow crossing `[t, t+Δt]`, which invariant 6 re-partitions —
    cannot be guarded here: detecting it means inspecting the instrument for its cashflow dates,
    the type-switch §1 forbids. It is a documented precondition on `theta`, and the contract
    question it raises is escalated rather than silently answered.)"""
    from pricebook.foundation.reference_entity import ReferenceEntity
    from pricebook.market.survival_curve import SurvivalCurve

    base = _market()
    with_survival = MarketSnapshot(
        valuation_date=VAL,
        curves=CurveSet(
            {
                **base.curves.curves,
                CurveKey(CurveRole.SURVIVAL, ReferenceEntity("ACME")): SurvivalCurve(
                    measure=vol_time_measure(VAL), times=(0.0, 5.0), survivals=(1.0, 0.9)
                ),
            }
        ),
        scalars=base.scalars,
        surfaces=base.surfaces,
    )
    with pytest.raises(ValueError, match="survival"):
        TimeBump().apply(with_survival, 30.0)
