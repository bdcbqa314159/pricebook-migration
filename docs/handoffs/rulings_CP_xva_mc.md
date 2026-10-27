# Ruling — the XVA / MC-exposure checkpoint (`CP_xva_mc.md`)

**Date:** 2026-10-27 · **By:** Cowork · **Rules:** `CP_xva_mc.md` (thread 0043). **Baseline:** v0.128.0,
drawdown 26/793. **Verdict: checkpoint RULED.** Fork decided by Bernardo (b).

## 1. Oracle audit — ACCEPTED
The three shapes named are real and worth keeping: the **forward-measure sampler oracle** (test the
sampler's own mean/variance against `f(0,t)` — catches the dropped-drift `σ²B²/2` bias a convergence
test is blind to), **convergence-as-a-rate** (not a tolerance; twice correct now), and the **signature
gate** (`cva` unchanged across three exposure methods). No oracle rests on self-consistency alone.

**O1 (no external CVA reference) — the deferral is correct; I checked it is not vendor-free-closable.**
Unlike the credit-vertical O1 (log-linear-Q had an analytic piecewise-hazard characterisation, so I
rejected its deferral), the CVA *definition* has no external closed form that isn't our own
construction — the swaption-approximation CVA *is* ours. A genuine external check needs a published
number, so O1 legitimately rides `NG-DEFER-CREDITISDA`. Named, not hidden; accepted.

## 2. Drawdown — 26/793, B7 zero-tick ACCEPTED
Five B7 slices, zero ticks, and the reason is precisely known (the consumed surface of
`mc_exposure.py` is a generic process framework, not rates netting) — that precision is the arc's
useful output, and it is what the fork turns on. Accepted.

## 3. Challenge-me — ruled
1. **`HullWhite.currency` — fine.** The model carries its snapshot and selects its discount curve by
   currency key (the ratified access, §2). A two-currency HW *is* two models (two calibrations, two
   curves) — correct, not a field to generalise. Not keyed-by-curve; the snapshot+key is the access.
2. **`_pending_swap` — delete it with `SwaptionPrice`, and assert its absence.** Yes, the
   `ProtectionWindow` make-it-unwritable pattern: once HW is on `SwaptionPrice` it receives the real
   swap and never reconstructs, so the reconstruction+guard must GO, with a test asserting the
   reconstruction path cannot return. Folded into the `SwaptionPrice` slice (§6 below).
3. **Marginal draws vs joint paths — docstring suffices now.** The profile is `(date, EE)` — EE is an
   aggregated expectation, not paths, so a WWR slice *cannot* silently consume it as joint paths (there
   are no paths in it to misread). WWR will build a **distinct** joint-path sampler + conditional
   exposure type deliberately (the profile-widening I deferred). Do not build a `MarginalDraws` vs
   `JointPaths` distinction speculatively now (§6b); introduce it with WWR, its consumer.
4. **`cva(profile, survival, recovery)` stays model-free — correct.** Its purity is what lets MC and
   analytic share one definition; it must *not* reach the entity. The single-source guarantee lives one
   layer up, in the wrappers (`swap_cva`/`book_cva`/`book_mc_cva`) that read recovery AND survival from
   the same snapshot keyed by the same entity — and the **bump-consistency gate already tests that
   wrapper path**. A direct-`cva` call with a mismatched recovery is caller error on an atom, not a
   `cva` bug. Enough as is; do not extend the gate into the atom.
5. **DVA — not required to close the exposure arc.** The arc this checkpoint covers (CVA + netting + MC
   exposure) is complete; DVA/FVA/MVA/KVA are further XVA capabilities, each its own slice. DVA is a
   cheap analytic increment available as one of the (b)-path candidates, not a precondition.
6. **Four exposure builders in `risk/exposure.py` — right home.** All four produce an *exposure
   profile* (one L5 concept); they differ by method, not by layer. The MC builders take the HW model as
   an input but are risk-layer logic, not model dynamics — keep them at L5 together. Splitting exposure
   across layers by method would be worse.

## 4. Smell + debt — ACCEPTED
- **`SwaptionPrice` is pending-ruling, not debt — and it becomes the next slice** (fork (b)), so it
  stops being "pending". Good that it was flagged not to drift.
- **The ungated clock** (MC's 73s first draft) — one instance, so §6's convention says watch, not gate.
  **Ledger `NG-WATCH-CLOCK`** (trigger: a second slice where test wall-clock balloons → propose a CI
  wall-clock ceiling, the floor-rule analogue). Tracked with a trigger, not lost, not built on one case.
- Naming smells (four `credit.py`, four exposure builders, ~48 handoffs files / six conventions):
  noted, none load-bearing, navigable via `docs/README.md`. If `docs/handoffs/` keeps growing, a
  one-line index per convention is the cheap fix — not now.

## 5. Fork — RULED BY BERNARDO: (b), SwaptionPrice + a consumer-narrow sweep, then equity on evidence
The reasoning that won it (Code's, ratified): the consumer-narrow rule now in §4 lets us *target*
ticks deliberately for the first time, so one sweep is a cheap test of whether B7's bar can move inside
what is already built. **If the sweep yields little, that is the measured evidence for (c)** — and (c)
(generic-process + equity) then proceeds with §4's breadth objection *answered by measurement* rather
than overridden. This settles the doctrinal tension instead of waving it through. Equity is **not**
opened yet; it is the evidence-gated next step.

## 6. Next slice — `SwaptionPrice` (the ruled capability, option A from thread 0038)
- Add **`SwaptionPrice.swaption_price(swap, expiry, option_type) → price`**, taking the **actual swap**.
  `HullWhite` implements it (Jamshidian on the real flow set — no reconstruction). The engine's
  `price_swaption` tries `SwaptionPrice` first, falls back to `SwaptionVol`+law — structural
  protocol-membership dispatch, no `isinstance`. `BlackModel`/`SABRModel` untouched, **byte-identical**.
- **Delete `_pending_swap` and the S-identity guard; assert the reconstruction path is gone**
  (challenge-me 2, make-it-unwritable).
- **Oracle:** the **semi-annual swaption that was 381bp wrong now prices correctly** off HW's Jamshidian
  (the defect eliminated by construction, not guarded); HW-vs-cube agreement where both apply; a test
  asserting `_pending_swap`/reconstruction is absent; Black/SABR byte-identical.
- **Tick:** retire-read `hull_white.py` again — `SwaptionPrice` lets HW's closed-form swaption fully
  cross, but the trinomial-tree numerics remain (→ lattice slice), so likely still **partial**. Honest
  retire-read; do not manufacture a tick.
- Then the **consumer-narrow sweep**: a scoping pass (like the swaption-cluster tail) over the modules
  B7's work has touched (`risk/xva.py`, the credit/CDS desk residuals, anything whose *consumed
  surface* is now narrow), proposing tick/partial per module with consumer evidence. That sweep's yield
  is the evidence that decides (c).

## 7. Process
`SwaptionPrice` branch `slice/<NN>-swaption-price-capability`: audit → align → test (the 381bp case
green + reconstruction-absent + Black/SABR byte-identical, RED first) → feat → docs. Next checkpoint:
≤6 slices or the next capability-cluster boundary.
