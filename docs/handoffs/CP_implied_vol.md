# Checkpoint — Implied-vol inversion (a short one, deliberately)

**Version:** v0.110.0 · **Slice:** `slice/24-implied-vol` · **Baseline:** v0.109.0 (cap/floor).
**Trigger:** a **module tick** + a **new cross-cutting L0 atom** (`invert_increasing`) — both §6
stops. **Mandate:** none from Cowork; this is the retiring slice recommended in `CP_capfloor.md` §7,
authorised by Bernardo while the slice-22/23 rulings are pending. One slice since the last
checkpoint, and the slice is small, so this report is short by design rather than padded to shape.

## 1. What landed

Two quarry functions with one algorithm — Newton-on-vega with a bisection fallback, duplicated once
per law — became **one law-generic inverter**. Because slice 22 made the law a value with its own
`price`, inverting it is law-generic for free: the lognormal, shifted-lognormal and normal cases are
the same code, `law.defined` decides the domain, and the **shifted law gains an inverter the quarry
never had**. §3d holds by construction rather than by test — the inverse composes the very function
it inverts, so a price and its implied vol cannot drift apart.

The `option_type` parameter disappeared into `call_price_from_put`: the implied vol of a put IS its
call's at the same strike, which is the entire content of put-call parity (exact and identical in
every law here). A named identity in place of a flag threaded into a solver.

**The slice also paid off a duplication it did not create.** The bracket-expanding search was already
hand-rolled inside `vol_strip._solve_vol`; it is now `foundation/solvers.py::invert_increasing` at
L0, composed by both the strip and the new inverter — two real in-slice consumers, so the atom is
justified by existing code rather than anticipation (§6b). Stripped vols are byte-identical.

## 2. Oracle-quality audit

| Oracle | Class | Result |
|---|---|---|
| **Round-trip per law** across strike × vol × expiry, both signs of the forward | **known-answer** | vol <1e-10, price <1e-14 |
| PUT prices inverted through the parity atom | identity + known-answer | <1e-10 |
| An **independent bisection on an inline `erf`-Black** vs the production inverter | cross-impl, cross-solver | <1e-9 |
| Negative forwards invert under `Normal`/`ShiftedLognormal`; refused by `Lognormal` | law domain | asserted |
| At/below intrinsic · above the cap · `t ≤ 0` · out of domain · both L0 bracket ends | raise-not-silent (6 cases) | asserted |
| Near-intrinsic inversion recovers ~1e-6, well-conditioned <1e-12 | **conditioning, stated** | asserted |
| Strip vols + 47 legacy pricing paths | **byte-identical** | exact |

Two notes. First, the round-trip grid **filters** quotes whose time value has underflowed, and then
asserts a floor on how many cases survive the filter — a filter without that floor can quietly eat a
suite, which is the slice-23 lesson (an oracle must be able to fail for the reason you think it can).
Second, the ill-conditioning near the intrinsic is **pinned as a property**, not hidden: a price
reconstructed through parity (how a real quote arrives, carrying its own rounding) recovers the vol to
~1e-6 while the direct price gives <1e-12. Tolerances sized to the problem (§7c).

## 3. Challenge-me

- **ng has ZERO consumers for this capability today.** Stated plainly rather than dressed up. It
  lands because it **retires a module** (§4 — cross-cutting work justified by what it retires) whose
  Black inverter has **7 production consumers** in the quarry, every one of them un-crossed. It is one
  concrete function, not an abstraction layer, so §6b's rule of two does not bite — but "correct,
  oracled, and called by nothing" is a fair thing to challenge, and the honest answer is that the
  drawdown bar is what buys it.
- **I chose a free function over a law member, on my own slice-22 flag.** The inverter could have
  been `VolLaw.implied_vol` (5 args, cohesive with `price`). I declined because slice 22's checkpoint
  flagged `seed_alpha` as a fourth member already stretching the protocol, with the stated remedy
  "when a second numerical fact arrives, split them out rather than growing `VolLaw` member by
  member". **The second one just arrived.** So the honest shape may now be a `LawNumerics`-style
  sibling carrying `seed_alpha` + `implied_vol` (+ per-law bounds), leaving `VolLaw` the finance:
  `price` · `sabr_vol` · `defined`. I did **not** do that here — it touches a protocol Cowork is
  mid-ruling on (slice-22 items 1 and 2), and §6 makes a vocabulary change a stop-and-rule. **Ruling
  wanted:** split `VolLaw` into finance + numerics, or leave the inverter free-standing?
- **`call_price_from_put` means a put-price caller must convert.** Mathematically free and exact, but
  it is a convention a caller can forget — the failure mode being an implied vol computed off a put
  price fed in as a call. Mitigated by the name and the docstring, not by the type system. A
  `PutPrice`/`CallPrice` newtype would close it and is, I think, over-engineering at one consumer.
- **The `_PRICE_EPS = 1e-15` intrinsic guard is a magic constant.** It is the threshold below which a
  quote carries no vol information. Chosen as a relative price tolerance a little above double
  rounding; not derived. A consumer with genuinely noisy prices would want it configurable, and then
  it belongs on a value rather than in the module.

## 4. Smell + debt scan

- `verify.py` acyclic / fields / layers / provenance / version / **debt** green; `pyright` **0**;
  `ruff` clean; **356 tests** (+12).
- **No new ledger rows and no suppressions** — the residual is empty and nothing was deferred. First
  slice in three with nothing added to `OPEN.md`.
- **§3d:** one inverter, one parity atom, one bracket search. The slice **removed** a duplication
  (the strip's hand-rolled loop) rather than adding one; the net count of hand-rolled solvers in the
  tree went down by one.
- **L0 conformance:** `invert_increasing` is finance-free in name and vocabulary (`verify.py layers`
  greps for `strike`/`volatilit`/`implied_vol`/payoff terms literally, and passes).
- **Arg discipline:** `implied_vol` 5, `invert_increasing` 5, `call_price_from_put` 3. No new type,
  no protocol growth, no `VolLaw.price` signature change (deliberately — see challenge #2).

## 5. Drawdown (§4) — 21 → **22 / 793** (+1 TICK), residual EMPTY

Three slices, three ticks, no deferred capability on this one. `options/implied_vol.py` crosses whole;
full shed classification (Newton-on-vega → §7bb, the silent `0.5*(lo+hi)` fallback, the
`hi = forward * 5.0` bracket that is **negative for a negative forward**, the silent 500% cap, the
conflated `tol`) is in `AUDIT_implied_vol.md` §3.

## 6. Named next checkpoint

Whichever comes first (§6): **≤6 slices**, or the next capability-cluster boundary. Three retiring
slices have now landed back to back, so the §4 "breadth waits while drawdown is stuck" pressure is
genuinely released.

**Recommended next:** the **swaption / vol-cube cluster** (`options/swaption.py` + the cube modules) —
the last named residuals forward-linked to "the SABR/smile slice", and every block they need now
exists, including this slice's inverter (a cube built from prices needs exactly it, which would also
give the capability its first ng consumer). That is a genuine capability cluster, so it wants a
scoping pass before the first slice rather than an immediate build.
