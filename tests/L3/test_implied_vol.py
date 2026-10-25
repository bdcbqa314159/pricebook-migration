"""L3 oracles — implied-vol inversion, one inverter for every law (T1 slice 24).

`implied_vol(law, call_price, forward, strike, t)` inverts the law's OWN `price`, so the round trip
`vol → price → vol` is a known-answer test at both ends: the vol that went in IS the answer, and the
inverse composes the very function it inverts (§3d — price and implied-vol cannot drift apart).

The quarry needed one inverter per law (and never had one for the shifted law); it also hid three
silent-wrong paths this file pins shut: a non-solution returned after a failed bisection, a
`hi = forward * 5.0` bracket that is negative for a negative forward, and a 500% cap that silently
returned ≈2.5. Every unattainable input here RAISES, named.
"""

import math
from datetime import date

import pytest

from pricebook.foundation import invert_increasing
from pricebook.models.bachelier import bachelier
from pricebook.models.black import black
from pricebook.models.implied_vol import call_price_from_put, implied_vol
from pricebook.models.vol_law import Lognormal, Normal, ShiftedLognormal
from pricebook.products.option import OptionType

CALL, PUT = OptionType.CALL, OptionType.PUT
SHIFT = 0.030
LOGNORMAL_CASES = (  # (law, forward, vols) — vols in that law's own units
    (Lognormal(), 0.035, (0.05, 0.20, 0.60, 1.50)),
    (ShiftedLognormal(SHIFT), 0.035, (0.05, 0.20, 0.60)),
    (ShiftedLognormal(SHIFT), -0.005, (0.10, 0.30, 0.80)),  # negative forward, shifted positive
    (Normal(), 0.035, (0.0010, 0.0060, 0.0200)),
    (Normal(), -0.005, (0.0010, 0.0060, 0.0200)),  # the case the quarry's bracket broke on
)


# ── the round trip, per law ────────────────────────────────────────────────────────────────
def test_round_trip_recovers_the_vol_in_every_law() -> None:
    # Only WELL-CONDITIONED quotes are asserted tightly: an implied vol is no more accurate than the
    # price it is implied from, and just above the intrinsic the price is nearly flat in the vol. The
    # filter is explicit (time value must be a real fraction of the price) rather than a hand-picked
    # grid, and the degenerate end is covered by its own tests below — not quietly skipped.
    checked = 0
    for law, fwd, vols in LOGNORMAL_CASES:
        for vol in vols:
            for moneyness in (-0.015, -0.005, 0.0, 0.005, 0.015):
                strike = fwd + moneyness
                if not law.defined(fwd, strike):
                    continue
                for t in (0.25, 1.0, 5.0):
                    px = law.price(fwd, strike, vol, t, CALL)
                    time_value = px - law.price(fwd, strike, 0.0, t, CALL)
                    if time_value < 1e-8 * max(1.0, abs(px)):  # vega has underflowed
                        continue
                    back = implied_vol(law, px, fwd, strike, t)
                    assert abs(back - vol) < 1e-10, (law, fwd, strike, vol, t, back)
                    # and the price comes back exactly: the inverse composes the same `price`
                    assert abs(law.price(fwd, strike, back, t, CALL) - px) < 1e-14
                    checked += 1
    assert checked > 150  # the grid is 285 cases; the filter must not be eating most of them


def test_put_prices_invert_through_the_parity_atom() -> None:
    # the content of the quarry's `option_type` parameter, as an identity instead of a flag: the
    # implied vol of a put IS the implied vol of its call, because C − P = F − K in every law
    for law, fwd, vols in LOGNORMAL_CASES:
        for vol in vols:
            for strike in (fwd - 0.01, fwd, fwd + 0.01):
                if not law.defined(fwd, strike):
                    continue
                call_px = law.price(fwd, strike, vol, 1.0, CALL)
                if call_px - law.price(fwd, strike, 0.0, 1.0, CALL) < 1e-8 * max(1.0, abs(call_px)):
                    continue  # no time value ⇒ no vol to recover (see the degenerate tests)
                put = law.price(fwd, strike, vol, 1.0, PUT)
                call = call_price_from_put(put, fwd, strike)
                assert abs(call - law.price(fwd, strike, vol, 1.0, CALL)) < 1e-15
                assert abs(implied_vol(law, call, fwd, strike, 1.0) - vol) < 1e-10


def test_the_lognormal_case_matches_an_independent_inversion() -> None:
    # an INDEPENDENT bisection on an inline erf-Black — a different solver on a different price
    # implementation — agrees with the production inverter
    def phi(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def ref_black(f: float, k: float, v: float, t: float) -> float:
        s = v * math.sqrt(t)
        d1 = (math.log(f / k) + 0.5 * s * s) / s
        return f * phi(d1) - k * phi(d1 - s)

    f, t = 0.035, 2.0
    for k in (0.025, 0.035, 0.050):
        for vol in (0.12, 0.35, 0.90):
            target = ref_black(f, k, vol, t)
            lo, hi = 1e-8, 5.0
            for _ in range(300):
                mid = 0.5 * (lo + hi)
                if ref_black(f, k, mid, t) < target:
                    lo = mid
                else:
                    hi = mid
            assert abs(implied_vol(Lognormal(), target, f, k, t) - 0.5 * (lo + hi)) < 1e-9


# ── failure, never a silent number ─────────────────────────────────────────────────────────
def test_a_price_at_its_intrinsic_raises_instead_of_returning_the_bracket_floor() -> None:
    # deep in the money at a small vol: the price IS the intrinsic in double precision, so no vol is
    # implied. The quarry returned whatever its solver landed on — a confident ~1e-9 for a 5% vol.
    law = Lognormal()
    px = law.price(0.035, 0.020, 0.05, 0.25, CALL)
    assert px == law.price(0.035, 0.020, 0.0, 0.25, CALL)  # the intrinsic, bit for bit: N(d) saturated
    with pytest.raises(ValueError, match="intrinsic"):
        implied_vol(law, px, 0.035, 0.020, 0.25)


def test_near_intrinsic_inversion_amplifies_price_error() -> None:
    # Two ULPS of time value above the intrinsic, and a price that itself carries rounding — here
    # reconstructed through parity, which is how a real quote arrives. The vol is still recovered to
    # ~1e-6, but NOT to the 1e-10 a well-conditioned quote gives: near the intrinsic the price is
    # almost flat in the vol, so the inverse amplifies the price's own error. Pinned as a documented
    # property (§7c — tolerances sized to the problem), not left as a surprise for a consumer.
    law, fwd, strike, vol = Lognormal(), 0.035, 0.035 - 0.01, 0.05
    direct = law.price(fwd, strike, vol, 1.0, CALL)
    via_parity = call_price_from_put(law.price(fwd, strike, vol, 1.0, PUT), fwd, strike)
    assert abs(via_parity - direct) < 1e-14  # the two prices agree to a few ulps…
    back = implied_vol(law, via_parity, fwd, strike, 1.0)
    assert abs(implied_vol(law, direct, fwd, strike, 1.0) - vol) < 1e-12  # …but invert differently
    assert abs(back - vol) < 1e-5


def test_a_price_below_intrinsic_raises() -> None:
    # `law.price(…, vol=0, …)` IS the intrinsic (the laws' degenerate branch), so the lower bound
    # needs no law-specific arithmetic — the bracket's own lo end reports it
    with pytest.raises(ValueError, match="intrinsic"):
        implied_vol(Lognormal(), 0.0, 0.040, 0.030, 1.0)  # intrinsic is 0.010, asking for 0
    with pytest.raises(ValueError, match="intrinsic"):
        implied_vol(Normal(), -1.0, -0.005, -0.010, 1.0)  # a negative price is below any intrinsic


def test_a_price_above_the_vol_cap_raises_instead_of_returning_the_cap() -> None:
    # the quarry returned ≈2.5 silently here (Black) or a garbage bracket (Bachelier)
    with pytest.raises(ValueError, match="cap|attainable"):
        implied_vol(Lognormal(), 0.0349999, 0.035, 0.035, 1.0)  # → the undiscounted forward, σ→∞
    with pytest.raises(ValueError, match="cap|attainable"):
        implied_vol(Normal(), 1e3, 0.035, 0.035, 1.0)


def test_a_non_positive_expiry_raises() -> None:
    for law, _, _ in LOGNORMAL_CASES:
        with pytest.raises(ValueError, match="expiry|t must"):
            implied_vol(law, 0.001, 0.035, 0.035, 0.0)


def test_a_forward_outside_the_laws_domain_raises() -> None:
    # the law decides, as everywhere else since slice 22 — no positivity test in the inverter
    with pytest.raises(ValueError, match="domain|Lognormal"):
        implied_vol(Lognormal(), 0.001, -0.005, 0.010, 1.0)
    with pytest.raises(ValueError, match="domain|ShiftedLognormal"):
        implied_vol(ShiftedLognormal(SHIFT), 0.001, -0.050, 0.010, 1.0)  # F + s < 0
    # …and the normal law has no such restriction
    assert implied_vol(Normal(), bachelier(-0.005, 0.010, 0.006, 1.0, CALL), -0.005, 0.010, 1.0) > 0.0


def test_lognormal_inversion_agrees_with_black_at_the_delegating_boundary() -> None:
    # `Lognormal.price` delegates to `black`, so inverting the law and inverting `black` are the
    # same problem — pinned so a future law change cannot silently decouple them
    px = black(0.035, 0.030, 0.25, 1.0, CALL)
    assert abs(implied_vol(Lognormal(), px, 0.035, 0.030, 1.0) - 0.25) < 1e-10


# ── the promoted L0 atom ───────────────────────────────────────────────────────────────────
def test_invert_increasing_expands_its_upper_bracket() -> None:
    # the hand-rolled loop that used to live in `vol_strip._solve_vol`, now shared (§3d)
    assert abs(invert_increasing(lambda x: x * x, 9.0, 0.0, 0.5, 100.0) - 3.0) < 1e-9
    assert abs(invert_increasing(lambda x: math.exp(x) - 1.0, 1.0, 0.0, 0.1, 10.0) - math.log(2.0)) < 1e-9


def test_invert_increasing_reports_which_end_failed() -> None:
    with pytest.raises(ValueError, match="below"):
        invert_increasing(lambda x: x * x, -1.0, 0.0, 1.0, 10.0)  # below f(lo) = 0
    with pytest.raises(ValueError, match="cap"):
        invert_increasing(lambda x: x * x, 1e6, 0.0, 1.0, 10.0)  # above f(cap) = 100
