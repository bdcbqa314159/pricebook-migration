# Spec — open B7 risk/XVA; slice 1 = unilateral CVA of one swap, the swaption approximation

**Date:** 2026-10-26 · **By:** Cowork · **Answers:** thread 0031 (vanilla credit closed) + Bernardo's
ruling (B7 next). **Baseline:** v0.122.0, drawdown 26/793.

## 0. Vanilla credit — closed, clean
All three items landed; the bump-consistency gate works on both shared inputs; divergence ① is
unwritable (`ProtectionWindow`, no day_count); JTD is a closed form with its own corrected assertion;
and O1 was **already closed** — the finding was withdrawn *inside* the checkpoint rather than deleted,
which is the right move (an invented finding costs the same credibility as a missed one; the fix for
both is read the file). Nothing to rule. B7 opens.

## 1. The state B7 starts from (grounded)
ng risk/ is `greeks`/`bump`/`priceable`/`credit` — **no exposure engine, no XVA**: B7 is greenfield in
this tree. But the swaption cluster just built everything an *analytic* CVA needs — `price_swaption`
(`engine/vanilla_option.py:114`), `VanillaSwap`, `SwaptionVol`/`SABRModel`, the survival curve, and
`scalars[RecoveryKey]`. The quarry's CVA is **MC-exposure based** (`risk/xva.py`, `models/mc_exposure.py`
+ ~17 `mc_*` modules) — a whole later sub-cluster. So slice 1 takes the analytic road: it reuses built
atoms, carries a **rung-1** oracle (the green-oracle gate prefers closed form over MC convergence), and
defers the MC framework to its own slices.

## 2. Slice 1 scope — unilateral CVA, single-trade netting set, swaption approximation
The standard physical-exposure result: the expected positive exposure of a swap at a future time `tᵢ`
is the value of a (physical-settled) swaption expiring at `tᵢ` on the swap's remaining leg. So
`EE(tᵢ)` comes from the pricer ng already has and already oracled.

- **The CVA composition atom (L5), defined ONCE (§3d):**
  `CVA = LGD · Σᵢ EE(tᵢ) · (Q(tᵢ₋₁) − Q(tᵢ))` — exposure leg × default leg × loss, over the swap's own
  schedule. `LGD = 1−R` from `scalars[RecoveryKey(entity)]`; `Q` from the survival curve; `df` in `EE`.
  **The exposure method is the pluggable part; the CVA atom is not** — MC exposure (a later slice) must
  feed the *same* atom, so the swaption-approx and MC CVAs compose one definition, not two (the vol-law
  / forward-threading precedent).
- **`EE(tᵢ)` for slice 1** = `price_swaption` on the remaining swap at each schedule point — composed,
  not re-derived.
- **Scope boundaries, all deferred with named triggers:** netting (multi-trade `max(ΣMtM,0)`) → slice 2;
  **DVA / bilateral** → slice 3; **MC exposure** (supersedes `models/mc_exposure.py` + the `mc_*`
  framework, and is what eventually retires `risk/xva.py`) → the general-exposure slice; FVA/MVA/KVA →
  later; **wrong-way risk** → with MC. Unilateral, single-trade, no collateral/MPOR in slice 1.

## 3. Oracle (rung-1 + structural)
1. **Composition of checked atoms:** `EE(tᵢ)` is the swaption pricer (its cluster oracles hold); `ΔQ`
   is the survival curve's (analytic). CVA is their sum — assert it against an **independent** reimpl
   of the sum over the same schedule (straight `exp()`/pricer calls), testing the *composition*, not
   restating it (the credit-closed-form discipline).
2. **Limits (structural):** `hazard → 0 ⇒ CVA → 0` (no default risk, no charge); CVA **monotone** in
   hazard and in LGD; CVA of a zero-remaining-life swap is 0. A failed/empty exposure schedule is a
   value, never a silent 0.
3. **Count:** N schedule intervals → N exposure points → N default-interval terms; no scalar shortcut.
4. **Bump-consistency (the third structural face — and Code is right it belongs here as an ACCEPTANCE
   criterion, not a checkpoint question):** `recovery` (the CVA LGD, shared with any CDS in reach) and
   the survival curve, each bumped at its snapshot home, must move the CVA coherently. In slice 1 the
   survival curve feeds only the default leg (one stage), so this is a sanity floor; it becomes
   load-bearing at the **MC/wrong-way-risk slice**, where the survival curve is shared by the exposure
   paths and the CVA integral — exactly its two-stages-one-input shape. Carry it forward as a standing
   XVA-cluster acceptance criterion.

## 4. Tick expectation — honest
Likely **0**: the quarry's CVA is MC (`xva.py`/`mc_exposure.py`), which an analytic approximation does
not supersede. Slice 1 opens B7 the way credit slice 1 opened B6 — capability first, ticks later. The
bar moves when MC exposure crosses `mc_exposure.py` and the general XVA crosses `xva.py`. Retire-read
at the end regardless (per §4); do not manufacture a tick.

## 5. Process (§8)
Branch `slice/<NN>-xva-cva-swaption-approx`. audit → align (the CVA atom + the swaption-approx EE) →
test (composition + the hazard→0 / monotonicity limits + the count + recovery bump-consistency, RED
first) → feat (GREEN) → docs (provenance: `risk/xva.py` + the swaption-approximation source —
Sorensen–Bollier / standard swap-CVA, oracle). Next checkpoint: ≤6 slices or the next XVA
capability boundary. Report the CVA mark + the retire-read; I spec slice 2 (netting) on it.
