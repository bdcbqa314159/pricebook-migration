"""Implied-vol inversion — one inverter for every law (L3).

`implied_vol(law, call_price, forward, strike, t)` recovers the volatility that reproduces an
UNDISCOUNTED call price under `law`. Discounting stays out, exactly as it does in `black` and
`bachelier`: the caller divides the `df · N · τ` the engine multiplied in, so the inverter has one
job and a signature that fits (§3b).

**One function, every law.** Because a law is a value with its own `price` (slice 22), the inversion
is law-generic: it inverts `law.price`, so the lognormal, shifted-lognormal and normal cases are the
same code, and `law.defined` decides the domain. The quarry needed a separate inverter per law — and
never had one for the shifted law. §3d holds by construction, not by test: the inverse composes the
very function it inverts, so a price and its implied vol cannot drift apart.

**Put prices go through parity, not through a flag.** The implied vol of a put IS the implied vol of
the call at the same strike; that is the whole content of put-call parity, which is exact and
identical in every law here (`C − P = F − K`). `call_price_from_put` names the relation, so the
solver never carries an option-type branch.

Unattainable inputs RAISE (below intrinsic, above the vol cap, non-positive expiry, outside the
law's domain) — never a mid-bracket consolation value, which is what the quarry returned after a
failed bisection. L3 raising is the established convention: the L4 engine and the calibrators convert
to `PricingFailure`/`CalibrationFailure` at their boundary (invariant 4).

Provenance:
  quarry: quarry/pricebook/options/implied_vol.py (implied_vol_black76 / implied_vol_bachelier)
  source: Black (1976); Bachelier (1900); put-call parity; CLAUDE.md 3d (shared atoms) · 7bb (scipy)
  oracle: price→vol→price round trip recovers a KNOWN vol per law (<1e-10) and its price (<1e-14);
          PUT prices invert through parity to the same vol; an independent bisection on an inline
          erf-Black agrees; below-intrinsic / above-cap / t<=0 / out-of-domain all raise
  slice:  implied-vol (T1 slice 24)
"""

from __future__ import annotations

from pricebook.foundation import invert_increasing
from pricebook.models.vol_law import VolLaw
from pricebook.products.option import OptionType

_VOL_FLOOR = 1e-9  # the lower bracket: f(FLOOR) is the intrinsic to within rounding
_VOL_SEED = 0.05  # the starting upper bracket, doubled from here (not a guess at the answer)
_VOL_CAP = 5.0  # 500% lognormal / 500bp-per-unit normal: beyond this the quote is not a vol
_PRICE_EPS = 1e-15  # a price this close to the intrinsic carries no vol information at all


def call_price_from_put(put_price: float, forward: float, strike: float) -> float:
    """The call price implied by a put price at the same strike — put-call parity
    `C = P + (F − K)` on UNDISCOUNTED prices. Exact and law-independent (every law in this tree
    prices a forward that is a martingale under its own measure), so inverting a put means converting
    it here first rather than threading an option type into the solver."""
    return put_price + (forward - strike)


def implied_vol(law: VolLaw, call_price: float, forward: float, strike: float, t: float) -> float:
    """The volatility, in `law`'s own units, that makes `law.price(forward, strike, ·, t, CALL)`
    equal `call_price` (undiscounted). Monotonic in the vol from the intrinsic upward, so the solve
    is a bracketed Brent (§7bb) and not a Newton that needs a fallback. Raises if the price is
    unattainable, if it sits at its intrinsic to machine precision (no time value ⇒ no vol
    information), if `t ≤ 0`, or if `(forward, strike)` is outside the law's domain.

    **Conditioning, stated rather than hidden:** the accuracy of an implied vol is bounded by the
    price's. Just above the intrinsic the price is nearly flat in the vol, so a price good to one ulp
    pins the vol only loosely — recovery degrades smoothly from ~1e-12 for an at-the-money quote to
    ~1e-6 a hair above the intrinsic, and the oracle asserts tolerances sized to that (§7c)."""
    if t <= 0.0:
        raise ValueError(f"t must be positive to imply a vol; got {t!r}")
    if not law.defined(forward, strike):
        raise ValueError(
            f"forward {forward!r} / strike {strike!r} outside the {type(law).__name__} law's domain"
        )
    # `vol = 0` IS the intrinsic (every law's degenerate branch), so the lower bound needs no
    # law-specific arithmetic. A price AT the intrinsic to machine precision implies no vol: the
    # price function is flat there (vega has underflowed), so any answer in [0, ∞) fits it equally
    # well. Deep-in-the-money and near-zero-expiry quotes land here; returning the bracket's floor
    # would be a confident 1e-9 for an option whose true vol is 5% — the quarry's silent habit.
    intrinsic = law.price(forward, strike, 0.0, t, OptionType.CALL)
    if call_price - intrinsic <= _PRICE_EPS * max(1.0, abs(call_price)):
        raise ValueError(
            f"call price {call_price!r} is at or below its intrinsic {intrinsic!r} to machine "
            f"precision — no vol is implied (the price carries no time value)"
        )
    return invert_increasing(
        lambda vol: law.price(forward, strike, vol, t, OptionType.CALL),
        call_price,
        _VOL_FLOOR,
        _VOL_SEED,
        _VOL_CAP,
    )
