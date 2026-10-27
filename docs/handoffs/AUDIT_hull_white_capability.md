# Audit — Hull-White vs the `SwaptionVol` capability: ML-D1 again, at 381bp

**Baseline:** v0.124.0 · **Slice:** hull-white (B7 prerequisite) · **Trigger:** §6 immediate stop —
a contract question on a ratified protocol. Found by an oracle, measured, and **guarded** so the
slice could still land honestly.

## 1. The finding

`SwaptionVol.swaption_vol(index, expiry, swap_tenor, strike, forward)` is keyed by the *surface*
coordinates. A Black or SABR model needs exactly that: it reads a vol off a surface. **A short-rate
model does not.** HW prices a European swaption by Jamshidian — one zero-bond option **per coupon
flow** — so its price depends on the underlying's whole flow set: the fixed leg's frequency, its day
counts, its schedule. None of that is in the key, and none of it can be inferred from it.

So `HullWhite.swaption_vol` has to *reconstruct* an underlying, and the reconstruction is a guess.

**Measured** (flat 3% curve, a=0.05, σ=0.01, 2Y into 5Y, K=3.0%):

| underlying | HW Jamshidian | engine at HW's vol | disagreement |
|---|---|---|---|
| **annual** (what the reconstruction guesses) | 0.0221632563 | 0.0221632563 | **0.0 bp** |
| **semi-annual** (the actual contract) | 0.0215113028 | 0.0223309192 | **381 bp relative** |

This is **ML-D1 again**, and an order of magnitude worse: slice A measured 48.8bp for the *forward*
alone; here the whole flow set is mis-stated, so the error is 381bp. The first draft of
`_pending_swap` carried a docstring claiming "the guess cancels". It does not — the semi-annual
oracle in the same slice disproved it. Recorded because the claim was mine and it was wrong.

## 2. What landed anyway, and why that is honest

**HW's closed forms are correct and oracled** — 15 tests green: exact curve reprice to 1e-12 at every
pillar and every (a, σ); `B` identities and its Ho-Lee convergence *rate*; zero-bond call/put parity;
swaption payer/receiver parity against the linear atoms; σ→0 → intrinsic; and the §3d cross-model
identity **where HW can reconstruct** (annual: 1e-9).

**The unsound case is a failure value, not a wrong number.** The threaded forward (slice A's ruling A)
is what makes the defect *detectable*: the engine passes the contract's true `S = float_leg_pv/rpv01`,
HW computes the `S` of its reconstruction, and refuses when they disagree by more than 0.1bp. The
`PricingFailure` carries the measurement ("… 48.3bp apart"), so a caller sees why rather than just
that. The guard cannot make the capability sufficient; it keeps it honest until the question is ruled.

**Slice A's forward-threading paid for itself twice.** It was built to fix the forward; it is now also
the only reason a *different* model's mis-reconstruction is detectable at all.

## 3. Options

| # | option | what it costs | what it buys |
|---|---|---|---|
| **A** | **A second capability — `SwaptionPrice.swaption_price(swap, expiry, kind)`** returning a *price*. The engine tries the price capability first, falls back to the vol capability. | one new protocol; one structural capability check in `price_swaption` (the engine already does exactly this for `SwaptionVol`, "a protocol, not a concrete-type ladder") | HW never reconstructs anything — it receives the contract. The wrong call becomes **unwritable**, not merely guarded. Black/SABR are untouched. |
| B | **Widen `SwaptionVol.swaption_vol` to carry the contract** instead of the key | changes the protocol and both existing implementations; a surface-reading model would then receive an argument it must ignore | one capability instead of two |
| C | Leave the guard as the permanent answer | nothing | HW silently unusable for every non-canonical underlying — i.e. most real swaptions |

**My recommendation: A.** A Gaussian model naturally produces a **price**; forcing it through a Black
vol is the lossy step, and the loss is exactly the flow set. Two capabilities with structural dispatch
is the ratified pattern already in the tree (`ImpliedVol` / `SwaptionVol` are two capabilities on
models for the same reason), and it leaves `BlackModel`/`SABRModel` completely untouched. C is
rejected: a model that refuses every semi-annual swaption is not a model.

## 4. Unaffected

The curve fit, the bond, the zero-bond option, Jamshidian itself, and every limit are independent of
this question — they are the model, and they are oracled. Only the *capability wiring* is open. MC
(the next slice) consumes `HullWhite`'s dynamics, not its `swaption_vol`, so this does not block it.
