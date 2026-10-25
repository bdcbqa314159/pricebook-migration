# Audit — Swaption SABR read (slice A): STOP AND REPORT, with the measurement

**Baseline:** v0.110.0 · **Mandate:** Cowork, "Swaption SABR smile, read-not-solved (cluster slice A)".
**Outcome: the slice's own stop condition fires** — *"Stop and report if `swaption_vol`'s S can
diverge from `price_swaption`'s"*. It can, by **49 basis points of swap rate**, and the divergence
**cannot be closed** inside the given `swaption_vol(index, expiry, swap_tenor, strike)` signature. No
code was written beyond this document: building the read on a premise that is provably broken would
ship exactly the class of silent error this cluster exists to retire.

## 1. The finding, measured

`price_swaption` marks `S = float_leg_pv(float_sched, float_dc, …) / rpv01(fixed_sched, fixed_dc, …)`
off the **swaption's own swap**. A `swaption_vol` given only `(index, expiry, swap_tenor, strike)` must
reconstruct that swap. Same index, same 1Y expiry, same 5Y tenor, same curves (flat 3.0% discount /
3.5% projection) — the reconstructed S depends entirely on conventions that are **not in those four
arguments**:

| underlying convention | periods | annuity | **S** |
|---|---|---|---|
| ANNUAL · ACT/365F — `test_swaption.py`, `test_audit_batch_a_l4.py` | 5 | 4.440810660 | **0.035620063** |
| SEMI-ANNUAL · ACT/365F — `test_audit_batch_c_l4.py` | 10 | 4.474386829 | **0.035308220** |
| QUARTERLY · ACT/365F (= the index tenor, the "derive it from the index" option) | 20 | 4.491238386 | **0.035153661** |
| ANNUAL · ACT/360 (the index's own day count) | 5 | 4.502488586 | **0.035132117** |

**Spread: 48.8 bp of swap rate** (1.4% relative). At a 5Y vol of ~20% with any real skew that moves
the ATM vol by vol *points*, and oracle #1 — "an ATM swaption struck at the engine's S prices with the
SABR ATM vol, the smile minimum" — fails by a wide margin. The identity is not approximately true; it
is false.

## 2. Why this is not fixable by choosing a canonical convention

The caplet analogue works because a caplet's accrual **is** the index's canonical accrual — one
period, fully determined by `(index, expiry)`, and `canonical_accrual` reconstructs it exactly. A
swaption's underlying has a **fixed-leg frequency and day count that the contract chooses and the
index does not carry**. `RateIndex` has `id`/`accrual`/`fixing`/`rfr`; there is no fixed-leg
convention on it, and there cannot be — one index underlies swaps of several frequencies.

Worse, **no hardcoded choice is even consistent with the tree as it stands**: `test_swaption.py` and
`test_audit_batch_a_l4.py` build ANNUAL underlyings, while `test_audit_batch_c_l4.py` builds
**SEMI-ANNUAL** ones (deliberately — that file's whole point is that `underlying_tenor` must be exact
for 6M/18M/60M underlyings at semi-annual frequency, audit repro E). So:

- canonical = ANNUAL ⇒ the ruling-2-analogue guard rejects `batch_c`'s 18M swaption ⇒ an existing
  oracle turns red;
- canonical = SEMI-ANNUAL ⇒ it rejects `test_swaption.py` and `batch_a` ⇒ three oracles turn red;
- canonical = the index tenor (QUARTERLY) ⇒ it rejects **all** of them.

Each violates the slice's own merge gate (*"BlackModel swaption + slices 1–24 byte-identical"*) and
its second stop condition (*"if a BlackModel-swaption number moves"*).

## 3. Three more divergence vectors in the same place

Even with the frequency and day counts settled, `swaption_vol` cannot see:

- **Collateral.** The engine discounts on `curves.discount(currency, swap.collateral)`; the vol has no
  collateral argument, so a CSA swaption's S diverges (narrower, but the same silent class).
- **Seasoning.** The engine composes `future_periods(schedule, vd)` (invariant 6); a reconstruction
  from `(expiry, tenor)` always spans the full tenor. Equal for a forward-starting swaption, not for a
  partially-expired one.
- **Notional/amortisation.** Not relevant to S today (unit-notional legs), but it is the same gap.

## 4. The candidate fixes, ranked

**(A) Thread the forward (or the swap) through the capability — RECOMMENDED.**
`swaption_vol(index, expiry, swap_tenor, strike, forward)`: the engine passes the S **it actually
priced**, so the identity holds *by construction* and every vector above closes at once — frequency,
day count, collateral, seasoning. Cost: one argument on one protocol method (5 args, inside §3b), and
`BlackModel.swaption_vol` ignores it. **This is exactly `OPEN.md` ML-D1's stated re-open trigger** —
"the first stub / non-standard optionlet consumer … the honest fix is to thread the accrual, which
*does* touch the signature". The first consumer has arrived; it is the swaption cube. Cowork deferred
that change for the caplet on the grounds that nothing in scope needed it, which was true then.

**(B) Put the quoted forward on the SABR node.** A SABR smile is only meaningful relative to the
forward it was fitted at, so `SabrParams` (or the surface) carries it: `swaption_vol` reads S rather
than deriving it. Honest, matches market practice, and it would make the *caplet* case explicit too.
Cost: a field on a ratified L1 type (§6 vocabulary stop), and the stored S goes stale when curves move
— acceptable for a calibrated cube (slice B recalibrates), but it is a staleness contract we do not
have yet.

**(C) A swap-convention registry + the guard.** The market answer: a "5Y swaption vol" quotes the
*standard* swap, and the guard enforces that this swaption's underlying IS that swap. Needs the
conventions registry (still `deferred→conventions`, zero ng consumers since retire #2) **and** it
still rejects `batch_c`'s non-standard underlying, so an existing oracle must be re-based or retired.
Most faithful to market practice, biggest surface, and it leaves (A)'s other three vectors open.

## 5. What is unaffected and ready to build once ruled

Everything else in the mandate stands and is independent of the ruling: reading
`SwaptionSurfaceKey(index, swap_tenor)` → `SabrSurface` → `at_expiry` → `SabrParams`; composing
`law.sabr_vol(S, strike, t, params)`; `SABRModel` carrying **two** opt-in capabilities (doc 22 Q1);
the structural read (wrong surface type → failure as a value); the law-mismatch guard; the Hagan
reference oracle; the negative-swap-rate normal-law oracle; and oracle #1 itself, which becomes a
genuine known-answer check the moment S is unambiguous. The slice is ~40 lines once the S question is
settled.

**Recommendation: rule (A), and fold the caplet's ML-D1 into the same change** — one signature, both
consumers, the whole divergence class closed, and the `BlackVol`→`ImpliedVol` rename of slice 22
already established that these contracts can be amended cleanly.
