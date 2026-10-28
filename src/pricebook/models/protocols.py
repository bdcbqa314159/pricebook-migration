"""Model capability protocols (L3) — the closed-form building blocks a model exposes.

Promoted from doc 22 (F2), which *designed* these but deferred the code to the second model
(rule of two). C2 is that second model, so the protocols land now and the engine depends on the
CAPABILITY, not the concrete type (CLAUDE.md §1; doc 22 Q1/Q3′). `DiscountingModel` satisfies
`CalibratedModel` structurally (it carries `.market`); `BlackModel` adds `ImpliedVol`.

A vol capability EXTENDS `CalibratedModel` rather than sitting beside it: a volatility is only
meaningful bound to the market it was read from, and the calibrator needs both (`model.market` for
the curve, `model.vol_law` for the law) from one object — two parallel arguments could disagree.

A capability ships WITH its semantic contract (measure/numeraire/units) or it is not ratified
(doc 22 Q3′a) — otherwise "shared capability" degrades to shared signature + per-model semantics,
which is `isinstance` with extra steps.

Provenance:
  quarry: (none — new protocol surface; doc 22 designed it)
  source: docs/22 Q1 (CalibratedModel) · Q3′a (a capability carries its measure/units contract)
  oracle: the linear reprice-to-par suite prices through the protocol-typed engine unchanged
  slice:  black-caplet (C2 slice 1)
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from pricebook.foundation import RateIndex, Tenor
from pricebook.foundation.equity import EquityUnderlying
from pricebook.market.snapshot import MarketSnapshot
from pricebook.products.option import OptionType
from pricebook.products.swap import VanillaSwap
from pricebook.models.vol_law import VolLaw


@runtime_checkable
class CalibratedModel(Protocol):
    """A model bound to the `MarketSnapshot` it was calibrated to (A1). The engine reaches the
    market ONLY through `model.market`, never as a peer argument. Concrete models add one or more
    capability protocols; higher layers depend on the capability, not the concrete type."""

    @property
    def market(self) -> MarketSnapshot: ...


@runtime_checkable
class ImpliedVol(CalibratedModel, Protocol):
    """The implied-volatility capability — a vol AND the law it is quoted in, inseparably.

    **Semantic contract (doc 22 Q3′a).** `implied_vol(index, expiry, strike, forward)` is the implied
    volatility of the `index` forward rate, for an optionlet expiring at `expiry` struck at `strike`,
    quoted under the **T-FORWARD MEASURE** (T = the optionlet payment date), where the forward rate is
    a martingale. **`forward` is an INPUT, never reconstructed here** (ruling A, 2026-10-24): a smile
    is `σ(F, K)`, and the engine passes the F it actually marked — through the shared `forward` /
    `float_leg_pv` / `rpv01` atoms — so the price formula and the smile compose the SAME F by
    construction (§3d). A capability that re-derived F from conventions would own a private dialect of
    the forward atom, which is the §3d failure itself. **Its units are `vol_law`'s units** — annualized
    lognormal (`0.20` = 20%) under `Lognormal`/`ShiftedLognormal`, an absolute rate vol (`0.008` =
    80bp) under `Normal`. The two members are a MATCHED PAIR: `vol_law.price(F, K, implied_vol(...),
    t, type)` is the only sanctioned composition, and reading the vol without the law is a bug no
    type can catch — which is why the law is part of the capability, not a parallel argument.

    Renamed from `BlackVol` in slice 22; `forward` threaded in slice 25 (`OPEN.md` ML-D1 CLOSED —
    its first consumer, the swaption cube, arrived). Threading it also DELETED the canonical-accrual
    reconstruction, so a stub / non-standard optionlet is now priced correctly at its own forward
    instead of refused."""

    @property
    def vol_law(self) -> VolLaw: ...

    def implied_vol(
        self, index: RateIndex, expiry: date, strike: float, forward: float
    ) -> float: ...


@runtime_checkable
class SwaptionPrice(CalibratedModel, Protocol):
    """The swaption-**pricing** capability — for models that price the contract directly, rather
    than quoting a vol for the engine's Black formula to consume.

    **Why it is a sibling of `SwaptionVol` and not a variant of it.** A surface model (Black, SABR)
    reads a vol off a surface, and `(index, expiry, swap_tenor, strike)` is exactly the right key for
    that. A **short-rate model is not a surface**: Hull-White prices a European swaption by
    Jamshidian — one zero-bond option per coupon flow — so its price depends on the underlying's
    whole **flow set**: the fixed leg's frequency, its day counts, its schedule. None of that is in
    the key. Forced through `SwaptionVol`, HW had to *reconstruct* an underlying, and the
    reconstruction was wrong by **381bp** on a semi-annual swap
    (`AUDIT_hull_white_capability.md`) — ML-D1 again, an order of magnitude past slice A's 48.8bp.

    So this capability takes the **actual `swap`**. There is nothing to reconstruct, nothing to
    guard, and the 381bp is unwritable rather than detected — the same move `ProtectionWindow` made
    for the protection leg's day count.

    The engine prefers this capability and falls back to `SwaptionVol` + the law, by structural
    protocol membership — no `isinstance` on a concrete model, exactly as `ImpliedVol`/`SwaptionVol`
    are already chosen."""

    def swaption_price(self, swap: VanillaSwap, expiry: date, kind: OptionType) -> float: ...


@runtime_checkable
class EquityVol(CalibratedModel, Protocol):
    """The equity-volatility capability — a sibling of `ImpliedVol`, keyed by `EquityUnderlying`
    instead of `RateIndex`. Same shape, different asset dimension: a new asset class adds a key,
    and here a capability keyed by it, never a field on an existing one (§3c).

    `strike` is threaded for the smile axis that arrives with its consumer; a flat/term `Surface`
    ignores it today, exactly as `ImpliedVol` ignores `forward`."""

    def equity_vol(self, underlying: EquityUnderlying, expiry: date, strike: float) -> float: ...


@runtime_checkable
class SwaptionVol(CalibratedModel, Protocol):
    """The swaption-volatility capability — a SIBLING of `ImpliedVol`, not a reuse.

    **Semantic contract (doc 22 Q3′a).** `swaption_vol(index, expiry, swap_tenor, strike, forward)`
    is the implied volatility of the forward SWAP RATE `S = float_leg_pv / rpv01`, for a
    swap on `index` starting at `expiry` with tenor `swap_tenor`, struck at `strike`, quoted under
    the **ANNUITY (SWAP) MEASURE** — numeraire the fixed-leg annuity `rpv01`, under which `S` is a
    martingale and Black returns the undiscounted `E^A[(S − K)+]`; `PV = annuity · that`. **Units:**
    `vol_law`'s units (§22 Q3′a), as for `ImpliedVol`. DISTINCT from `ImpliedVol` (an index forward
    under the T-forward measure) — a swaption vol is never read through `ImpliedVol`, nor the
    reverse, and each capability carries the law its own vol is quoted in.

    **`forward` is the engine's marked S = `float_leg_pv/rpv01`, passed in** (ruling A): the
    underlying swap's fixed-leg frequency, day counts, collateral and seasoning are NOT derivable
    from `(index, expiry, swap_tenor)` — reconstructing S from conventions moved it by **48.8bp**
    across the conventions this tree itself uses (`AUDIT_swaption_sabr_read.md`). Passing it closes
    all four divergence vectors at once, because the vol stops reconstructing anything."""

    @property
    def vol_law(self) -> VolLaw: ...

    def swaption_vol(
        self, index: RateIndex, expiry: date, swap_tenor: Tenor, strike: float, forward: float
    ) -> float: ...
