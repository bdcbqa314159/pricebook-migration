# Ruling (variance-floor sharpening) + spec (c3 — equity MC exposure, the `mc_exposure.py` crossing)

**Date:** 2026-10-29 · **By:** Cowork · **Answers:** thread 0063. **Baseline:** v0.137.0, drawdown 31/793.

## 1. The baseline variance-floor — RULED into the law (second instance; §6 convention fires)
Two instances now — the 27 identical `PricingFailure`s (0061) and the 40 identical zeros (this slice,
`_swap`'s strike-vs-tenor arg flooring every exposure) — so this is a pattern, not a one-off. Both were
**byte-identity baselines with no discriminating power**: an all-equal baseline compares equal under
*any* change, so "byte-identical" over it proves nothing, and no amount of green reveals it. Land this
beside the floor rule (§4 structural-oracle second clause) and in doc 11's oracle-quality audit:

> **A regression / byte-identity baseline must assert its discriminating power, not merely that it is
> populated.** "Is it populated" and "is it discriminating" are different questions, and only the second
> is what a baseline is *for*: a degenerate baseline (all-equal, all-zero, all-`PricingFailure`)
> compares equal under every change. So a byte-identity baseline asserts a **floor on its variance** —
> enough points, enough *distinct* and non-degenerate values — before any diff counts. This is the
> floor rule's third face: floor-on-population guards an empty check; **floor-on-variance** guards a
> populated-but-powerless one. *(Precedent: 27 identical `PricingFailure`s compared "equal" over
> nothing; 40 identical zero exposures compared equal under any change — each a baseline that could not
> have failed.)*

## 2. c2 ratified
- **`StateProcess` as a marginal exact sampler** — the narrowest shape HW and BS both need; not widened
  to joint paths (that is WWR's shape, arriving with that consumer). §6b exactly. No contract question,
  correctly no stop.
- **`sample_state` relocated L5→L3 dynamics** — a real §1 win: `risk/exposure.py` had been reaching
  through `HullWhite`'s privates (`_instantaneous_forward`, `sigma`), a semantic layering breach
  `acyclic`/`layers` cannot see, and the abstraction forced it into the open. Byte-identical across 140
  points — a pure relocation. Good.
- **Oracle 2** (MC-over-BS → c1's closed form, 3 strikes, 3·stderr) is the c1-first-as-anchor decision
  paying off, as intended.
- Retire-read honest: `models/gbm.py` does **not** tick (`GBMGenerator` is a stepped path generator,
  wider than the exact sampler → `deferred→` the joint-path/WWR slice); `processes_extended.py`
  (CIR/Heston/jump/rough) un-built vertical, RESIDENT; `NG-DEFER-THETA-COUPON-GUARD` ledgered. Agreed.

## 3. c3 — equity MC exposure → equity CVA, and the `mc_exposure.py` crossing (the bar-mover)
ng now has what thread-0042 found `mc_exposure.py`'s consumed surface to be — a **generic process
framework over a `BlackScholesProcess`** (`StateProcess` + `BlackScholesProcess` + the generic MC
engine, c2). c3 is where that call gets **tested by execution**, not asserted.

- **Equity exposure builder (L5):** the generic MC exposure builder (generalised to `StateProcess` in
  c2) over the `BlackScholesProcess` → `EE(tᵢ) = mean over paths of max(V_tᵢ, 0)` for an equity
  derivative (forward / option), `V_tᵢ` its MtM on the path. **Profile stays `(date, EE)`; `cva`
  untouched** — the split now holds across a *third* asset's exposure (HW rates, BS equity), and the
  signature gate proves it.
- **Equity CVA:** `cva(profile, survival, recovery)` composed, unchanged — the equity exposure feeds the
  same atom the rates exposures do.
- **Marginal only; WWR deferred.** No wrong-way risk between the equity and the counterparty default
  (that is the joint-path consumer — the `StateProcess` joint widening + `GBMGenerator`, already
  forward-linked). c3 is the marginal equity exposure.

**Oracle (closed-form-anchored, as the whole MC arc has been):**
1. **Agreement with the analytic exposure:** an equity derivative's future MtM is itself a c1
   Black-Scholes value, so `EE(tᵢ)` has a **closed form** (the residual BS value at `tᵢ`); the MC `EE`
   and the equity CVA converge to it within **3·stderr**. c1 is again the anchor — the equity analogue
   of rates MC → the swaption-approx.
2. **Convergence** as `1/√P`; **seed-reproducibility** byte-identical (with the §1 variance-floor on the
   baseline, per §1 above — the capture must be discriminating).
3. **One engine, three asset exposures:** the generic MC engine produces an HW rates exposure and a BS
   equity exposure through the same `StateProcess`, no `isinstance` — the structural proof the
   abstraction is real.
4. **Bump-consistency** (recovery, survival) on the equity CVA — the standing XVA acceptance criterion.

**Tick — the bar-mover, VERIFY don't assume.** Retire-read `models/mc_exposure.py`: its consumed
surface (the `ExposureEngine` over a `BlackScholesProcess`, per thread-0042) is now ng's generic
engine → **propose the tick (31 → 32)** with the consumer evidence that the surface is genuinely
superseded. The broader `mc_*` framework (processes_extended, variance reduction) stays RESIDENT /
deferred to its verticals. This is the thread-0042 call under test — if the consumed surface turns out
wider than the generic engine provides, report that rather than force the tick.

## 4. Process (§8)
Branch `slice/<NN>-equity-mc-exposure`. audit → align (the equity exposure builder on `StateProcess`) →
test (closed-form-agreement + convergence + the one-engine-three-exposures structural test + a
**variance-floored** seed-repro baseline, RED first) → feat → docs → retire-read. Report the equity
CVA, the agreement numbers, and the `mc_exposure.py` tick (or why not). If it ticks, that is B7's bar
finally moving on the MC arc — and a natural checkpoint is near (several slices into the equity/MC run).
