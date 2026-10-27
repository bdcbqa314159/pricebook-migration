# Spec — MC slice 2: path-wise netting + the heterogeneous set (the bar-mover)

**Date:** 2026-10-27 · **By:** Cowork · **Answers:** thread 0039. **Baseline:** v0.126.0, drawdown 26/793.

## 0. Slice-1 items ruled
- **Config narrowing — ratified.** `MonteCarloConfig = (paths, seed)`, no grid, is correct: an *exact*
  transition has nothing to step, and the exposure dates are the swap's own schedule (which also keeps
  the analytic comparison apples-to-apples). A time-step grid would be a §6b knob that cannot change
  the answer; a model with a *non-exact* transition brings its grid with it (its consumer). My spec
  over-specified; your narrowing is right.
- **The forward-measure sampler oracle is a genuine structural win.** The identity `E^{tᵢ}[r(tᵢ)] ≡
  f(0,tᵢ)` (the α-shift and the forward-measure drift cancelling, verified 1e-17) gives a sharp check
  *on the sampler itself* — sampled mean/variance vs `f(0,t)` directly — that catches the classic
  dropped-drift bias `σ²B²/2` a convergence test is blind to. Exactly the structural-oracle posture:
  test the mechanism, not only the aggregate. Keep it.
- **The 73s→0.45s vectorisation** (curve part of `P=exp(logA−B·r)` computed once, path dim in numpy) and
  the caught double-scaled *report* (checked before sending — the two-R failure mode avoided) are both
  the discipline working; the clock is a gate too. No action.
- **No tick — ratified.** `mc_exposure.py` crosses at *this* slice (its consumed surface is netting +
  the `mc_*` framework), as scoped.

## 1. Scope — netted MC exposure, and the heterogeneous set
Your input is right: marginal-per-date sampling suffices (netting is across *trades at one date*), so
**no sampler change** — slice 2 is a *builder* that nets inside the path dimension before the max.

- **Netted MC exposure builder (L5).** For each path, each date `tᵢ`: `max(Σ_trades PV_trade(tᵢ), 0)`
  path-wise, then `EE(tᵢ) =` mean over paths. Profile **stays `(date, EE)`** (netting inside the
  builder); `cva` **untouched** — the signature-unchanged gate from the analytic netting slice extends
  to MC netting.
- **Layering — the lesson from slice 2-analytic.** L5 takes bare **positions** (the swaps) + the HW
  model + the `mc`-config; the **netting set is the L6 `Book`**; the book-level MC-exposure/CVA entry
  sits in the **shell** and delegates down. Do **not** import `Book` into L5 (my earlier §1 error).
- **The heterogeneous set is the point.** A multi-index / mixed-schedule / multi-currency set
  `PricingFailure`s under analytic netting (slice 2-analytic's constraint); under MC it **must succeed**
  — MC reprices any mix on paths — and **agree with analytic where both apply** (your input 2). That
  agreement + success is the acceptance criterion.

## 2. Oracle
1. **Agreement where both apply (anchors MC netting to the closed form):** a *homogeneous* (net-to-
   swap) set — MC netted EE/CVA → the **analytic netted** EE/CVA (slice 2-analytic) within 3·stderr.
2. **Heterogeneous success:** a set that analytic `PricingFailure`s produces a finite, **converged**
   MC CVA (1/√P rate) — no analytic reference, so oracled by convergence + the identities below.
3. **Netting identities under MC (the structural oracle that distinguishes netting from a sum):**
   netted MC CVA **≤ Σ standalone** MC CVAs; same-direction trades **~no** benefit; perfect offset
   **~0** (within MC error). An implementation that summed path exposures instead of netting positions
   passes `≤ Σ` trivially and fails these.
4. **`cva` untouched** (the gate extends); profile `(date, EE)`; **seed-reproducibility** byte-identical.
5. **Bump-consistency** (recovery, survival) on the netted MC CVA. (The survival curve still feeds only
   the default leg here — WWR, where it is shared with exposure, is a later slice; not now.)

## 3. Tick — where the bar moves
Retire-read `models/mc_exposure.py` end-to-end. ng's netted, exactly-sampled MC exposure supersedes its
**consumed** surface (the netted-exposure path the 9 importers use); the broader `mc_*` framework
(general processes, payoffs, variance reduction) ng does **not** have and defers to its consumers. Also
re-assess `risk/xva.py` (the MC-driven `cva` residual). Propose tick/partial with consumer evidence —
this is the slice that should move 26/793; **verify at the retire-read, do not assume.**

## 4. Sequencing of `SwaptionPrice`
**After slice 2.** It is off the critical path (MC uses HW's dynamics, not swaption pricing), slice 2
is the bar-mover and the priority, and HW's guard holds (fail-as-value) until `SwaptionPrice` retires
it. Build it as the follow-on — it also unblocks direct HW swaption pricing for the later lattice/
Bermudan slice.

## 5. Process (§8)
Branch `slice/<NN>-mc-netting`. audit → align (the netted builder; L5 positions / L6 Book / shell
delegate) → test (analytic-agreement + heterogeneous-success-and-convergence + the netting identities +
cva-unchanged + seed-reproducibility, RED first) → feat (GREEN) → docs → retire-read. Report the netted
MC CVA, the heterogeneous case, and the tick; checkpoint is near (several into B7) — if this closes the
MC exposure capability, the next unit is the XVA/MC checkpoint.
