# Ruling (HW capability) + spec (MC exposure) — B7

**Date:** 2026-10-27 · **By:** Cowork · **Answers:** thread 0037 (`AUDIT_hull_white_capability.md`).
**Baseline:** v0.125.0, drawdown 26/793.

## 1. HW capability — RULED: option A, a `SwaptionPrice` capability
A `SwaptionVol` surface answers `σ(coordinates, strike, forward)` — a vol keyed by surface
coordinates. A Gaussian short-rate model answers a **price**, and by Jamshidian that price depends on
the underlying's whole **coupon flow set** (frequency, day counts, schedule), which the key cannot
express — so forcing HW through `swaption_vol` *requires* a reconstruction, and the reconstruction is
the 381bp. These are genuinely different capabilities.

**Add `SwaptionPrice.swaption_price(swap, expiry, option_type) → price`** — taking the **actual swap**
(the real flow set), so HW's Jamshidian prices the contract it is handed, with **no reconstruction**.
The 381bp is eliminated *by construction*, not guarded; **HW's forward-reconstruction guard is then
retired** (it was the honest bridge while HW was wrongly on `swaption_vol`). The engine's
`price_swaption` tries `SwaptionPrice` first, falls back to the `SwaptionVol`+law path — structural
protocol-membership dispatch, the ratified `ImpliedVol`/`SwaptionVol` pattern, **no `isinstance`**.
`BlackModel`/`SABRModel` keep `SwaptionVol`, untouched and byte-identical. §3d holds: `swaption_price`
composes the swap's real `S = float_leg_pv/rpv01` from the shared atoms; HW's closed-form swaption is
a model building block (§3 lists `zero_bond_option` as exactly that) the engine invokes.

Rejected: **B** (widen `swaption_vol` to carry the contract) makes every surface model accept an
argument it ignores and conflates "read a vol" with "price a contract"; **C** (permanent guard) — a
model that refuses every semi-annual swaption is not a model. Option A is also minimal-risk: the
existing oracled vol path is untouched, the new capability serves the new need (doc 22 F2 — a model is
a bundle of capabilities).

**Sequencing:** the `SwaptionPrice` slice is small, independent, and **not on MC's critical path** (MC
consumes HW's *dynamics*, not its swaption pricing). Do it whenever; I scope **MC first** below since
it is the bar-mover Bernardo chose. HW's swaption guard stays until the `SwaptionPrice` slice retires
it — correct-but-limited (fail-as-value), ledgered, not blocking.

**HW retire-read — NO TICK, partial: ratified.** ng supersedes HW's analytics (A/B, bond, closed-form
Jamshidian swaption where the quarry used a tree); the tree numerics
(`_evolve_state_prices`/`tree_zcb`/`build_tree_alphas`/`tree_european_swaption`) defer to the
**lattice slice** (American/Bermudan exercise) and simulation to **MC** (§6b). Honest partial;
26/793.

## 2. MC exposure — scope (MC slice 1: single-trade, the analytic-agreement anchor)
MC is ng's first simulation; introduce it minimally (§6b) and oracle it against the closed form, so
the methodology is proven on the clean case before netting/heterogeneity.

- **HW path simulation (L3/L4 numerics).** HW's `r(t)` is Gaussian with an exact transition, so step
  it **exactly** (sample `r(tᵢ)` from its closed-form Gaussian law — **no Euler discretization bias**,
  which keeps the oracle clean). Paths from `numpy` RNG, **seeded**.
- **The `mc` numerical sub-config** (invariant 5 — explicit, never a hidden default; ≤5 fields):
  `paths`, `seed`, the exposure time grid. Variance reduction (antithetic/control-variate) **deferred**
  (§6b, a performance consumer). This decomposes the numerical-config family beside `IntegrationConfig`.
- **The MC exposure profile builder (L5).** For each path, each exposure date `tᵢ`: the swap PV under
  HW (discount the remaining cashflows with HW's `P(tᵢ,T)` given the path's `r(tᵢ)` — composing HW's
  bond building block + the swap's flows, §3d); `EE(tᵢ) = mean over paths of max(PV(tᵢ), 0)`. **Output
  stays `(date, EE)`** (ruled in 0036) — netting path-wise is slice 2's concern; `cva` **untouched**.

**Oracle — analytic agreement anchors MC (the §4 green-oracle gate: MC convergence alone is rung-3, so
anchor it to the closed form):**
1. **Agreement where both apply:** the MC `EE(tᵢ)` → the slice-1 analytic **swaption-approximation**
   `EE(tᵢ)` within **3·stderr** (the swaption-approx EE is itself the swaption price on the remaining
   swap — a closed-form reference). The MC CVA → the analytic CVA likewise.
2. **Convergence:** stderr falls as `1/√P` — assert the rate (quadrupling paths ≈ halves stderr), not
   a fixed tolerance.
3. **σ→0 degeneracy:** zero HW vol → deterministic paths → MC `EE` == the deterministic forward
   exposure == analytic-at-zero-vol (an independent cross-check at the boundary).
4. **Reproducibility (invariant 1):** same seed ⇒ same paths ⇒ **byte-identical** CVA; the seed is in
   the explicit `mc`-config, no hidden default.
5. **Structural:** `EE(tᵢ) ≥ 0`; `hazard→0 ⇒ CVA→0` on the MC profile; **bump-consistency** (recovery,
   survival) on the MC CVA.

## 3. Then MC slice 2 (netting + heterogeneous) — named, where the bar moves
Path-wise `max(Σ MtM, 0)` netting across a set, **including the heterogeneous set (multi-index/
schedule) that `PricingFailure`s analytically** — which under MC must **succeed and agree with analytic
where both apply** (Code's input 2). Profile still `(date, EE)` (netting inside the builder). This is
the slice that crosses `models/mc_exposure.py` + the MC-driven part of `risk/xva.py` and **moves the
bar** — retire-read it there. (WWR — the profile widening to conditional exposures — is a later slice
still; not here.)

**Split rationale (§6):** slice 1 proves MC exposure against the closed form on one trade (checkable
in one oracle pass); slice 2 adds netting and the heterogeneous case (and the tick). One methodology
step per slice.

## 4. Process (§8)
Branch `slice/<NN>-mc-exposure`. audit → align (HW path sim + the `mc`-config) → test (analytic
agreement + convergence rate + σ→0 + seed-reproducibility, RED first) → feat (GREEN) → docs
(provenance: `models/mc_exposure.py`, source, oracle). Report the MC CVA + the agreement numbers; I
spec MC slice 2 (netting) on it. Next checkpoint: ≤6 slices or the XVA-cluster boundary — we are
several into B7, so it is near.
