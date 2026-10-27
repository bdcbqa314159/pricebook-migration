# Checkpoint — the XVA / MC-exposure arc (capability-cluster boundary, §6 hard stop)

**Date:** 2026-10-27 · **Span:** v0.123.0 → v0.127.0 (5 slices) · **Baseline:** v0.127.0
**Trigger:** due on all three counts — 4 slices since `CP_credit_vertical`, the MC-exposure
capability arc **complete** (CVA → analytic netting → HW → MC → MC netting), and the **zero-tick B7
finding** is checkpoint-grade. **Mandate:** thread 0042.
**Tests:** 510 green, both OSes, pyright clean. **Drawdown: 26 / 793.** **Debt: 5 live items.**

---

## 1. Oracle-quality audit — against the amended §6

| oracle file | tests | structural / floor? | what it asserts beyond a number |
|---|---|---|---|
| `L5/test_cva.py` | 13 | **yes** | composition vs an independent re-summation; **`hazard→0 ⇒ CVA→0`**; count; last profile point exactly 0 |
| `L5/test_cva_netting.py` | 13 | **yes — decomposition** | degenerate **byte-identical**; netted ≤ Σ **with** the no-benefit/strict-benefit pair; perfect offset → 0 with each leg non-zero |
| `L3/test_hull_white.py` | 15 | **yes — identity** | curve reprice **1e-12 at every pillar and every (a, σ)**; two parities; Ho-Lee **convergence rate**; the 381bp capability guard |
| `L5/test_mc_exposure.py` | 12 | **yes — mechanism** | closed-form agreement (CVA **9.5 bp**); **1/√P rate**; the **sampler's own mean/variance** vs `f(0,t)`; seed byte-identity |
| `L5/test_mc_netting.py` | 16 | **yes** | analytic agreement where both apply; **heterogeneous success + convergence**; the netting identities; the three-method `cva` gate |

**Three oracle shapes this arc added, worth naming because each catches something the obvious test
cannot:**

1. **The forward-measure sampler oracle.** `E^{tᵢ}[r(tᵢ)] ≡ f(0,tᵢ)` is an identity (the curve-fitting
   `α` shift and the forward-measure drift cancel), checked **directly on the sampler's** mean and
   variance rather than through a price. Dropping the drift adjustment — the classic HW-MC error —
   biases every exposure by `σ²B(0,t)²/2`, which a convergence test is **blind to**: a biased sampler
   still converges, just to the wrong number. *Test the mechanism, not only the aggregate.*
2. **Convergence as a RATE, not a tolerance.** Twice now (Ho-Lee's `O(a·dt²)`, MC's `1/√P`) the right
   assertion was the rate. A fixed tolerance at one parameter value either passes vacuously or fails
   on correct mathematics — my first Ho-Lee test did the latter.
3. **The signature gate.** `cva`'s signature is asserted unchanged, and has now survived **three**
   exposure methods (swaption-approx, analytic netting, MC netting). A design decision expressed as a
   test, so it fails loudly instead of eroding.

**Finding O1 — the `cva` atom's own composition is never checked against a published CVA.** Every
oracle here anchors MC to *our* closed form, and the analytic closed form to *our* atoms. That chain
is sound and rung-1 at each link, but the whole has no external reference: a shared misconception in
the CVA *definition* (e.g. a discounting convention, or EE-vs-EPE) would pass everything.
`NG-DEFER-CREDITISDA`'s trigger (a citable worked example) would close this too — recorded so the two
discharge together rather than as a new ledger entry.

**No oracle in this arc rests on self-consistency alone**, and the one gap above is named rather than
implied.

---

## 2. Drawdown reconciliation — 26 / 793, and B7's zero-tick analysis

| slice | version | tick | why |
|---|---|---|---|
| CVA | 0.123.0 | 0 | opener; ng supersedes 1 of `risk/xva.py`'s 13 functions |
| analytic netting | 0.124.0 | 0 | the quarry's netting lives inside its MC path, not separately |
| Hull-White | 0.125.0 | 0 | ng supersedes the **analytics**; the trinomial tree is the bulk |
| MC exposure | 0.126.0 | 0 | single-trade; `mc_exposure.py`'s surface is netting + framework |
| MC netting | 0.127.0 | **0 — expected, and disproved** | see below |

**B7: five slices, zero ticks.** That is real §4 pressure and it is stated rather than explained away.
But the *reason* is now precisely known, which is the useful output of the arc:

`models/mc_exposure.py`'s **consumed surface is a generic multi-asset process framework**, not rates
netting. `ExposureResult` has **0 consumers** anywhere (source or the 952 test files); `ExposureEngine`
has exactly **one** production consumer, using it for *"Equity exposure + CVA/DVA/FVA"* over a
**`BlackScholesProcess`**. ng's MC exposure is deliberately HW-specific (§6b), so the surface actually
consumed has no ng counterpart.

**So B7's bar moves on a generic process abstraction — which is the equity gateway, not a rates
slice.** That is a doctrinal tension (§4's "breadth waits while drawdown is stuck" vs the bar-mover
*being* new breadth) and it is a milestone fork, so it goes to Bernardo rather than being settled
here. Cowork is surfacing it on this report.

**What the arc did buy, since "0 ticks" understates it:** the exposure/atom split (one CVA definition
across three exposure methods, gated), the first simulatable dynamics in the tree, exactly-sampled MC
with no discretisation bias, path-wise netting that prices sets the analytic proxy must refuse, and a
measured capability defect (381bp) that is now a failure value rather than a wrong number.

---

## 3. Challenge me

1. **`HullWhite` carries `currency` to find its own discount curve.** Is that right, or should a
   rates model be keyed by the curve it is calibrated to (so a two-currency HW is two models, not one
   with a field)?
2. **`_pending_swap` still exists** — HW guesses an underlying, detects the guess via the threaded
   `S`, and fails. Once `SwaptionPrice` lands it should be **deleted**, not kept as a fallback. Should
   the capability slice assert its absence (the `ProtectionWindow` pattern — make it unwritable)?
3. **MC uses marginal-per-date draws, not joint paths.** Correct for `EE` and for netting; wrong for
   WWR. Is recording that in the docstring enough, or should the profile type itself carry "these are
   marginals" so a WWR slice cannot silently consume them as paths?
4. **`cva` takes `recovery: float`, not the entity.** It is the one XVA function that does not reach
   the snapshot itself — deliberate (it takes a profile, so it is model-free), but it means a caller
   *could* pass a recovery inconsistent with the curve. Is the three-layer `book_mc_cva`/`swap_cva`
   wrapping enough, or does the bump-consistency gate need extending to the atom?
5. **No DVA, FVA, MVA, KVA, or collateral/MPOR.** All deferred with triggers. Does the XVA cluster
   close without bilateral CVA, or is DVA part of "XVA exists"?
6. **`risk/exposure.py` is now four builders** (swaption-approx, analytic-netted, MC, MC-netted) in
   one module. Is that the right home, or does the MC half belong beside the model that simulates it?

---

## 4. Smell + debt scan

**5 live ledger items**, all deferred *scope* with triggers; `verify.py debt` green (suppressions −
entries = 0). Unchanged this arc: `NG-DEFER-CREDITISDA`, `NG-DEFER-DF-CONTINUOUS`,
`NG-DEFER-CUBEBETA`, `NG-DEFER-CUBEORACLE`, `NG-WATCH-TIERFLOOR`.

**Pending, not debt — the ruled-but-unbuilt `SwaptionPrice` capability.** Ruled in thread 0038
(option A), deferred to after MC slice 2 by thread 0040. HW's S-identity guard holds until it lands,
so nothing is wrong — but it is an open *ruling* rather than an open *question*, and it should not
drift. It also unblocks the later lattice/Bermudan swaption work.

**Smells, none load-bearing:**
- **Four files named `credit.py`** (products/engine/calibration/risk) and now two XVA entry points in
  the shell (`book_cva`, `book_mc_cva`). Correct by layer; ambiguous to a reader.
- **`risk/exposure.py` holds four exposure builders** — see challenge 6.
- **`docs/handoffs/` is at ~48 files across six naming conventions** (`CP_`, `AUDIT_`, `rulings_`,
  `spec_`, `RETIRE_`, `record_`). Navigable via `docs/README.md`; the convention count is the smell.
- **The clock is an ungated gate.** MC's first implementation took 73s for one test file (would have
  made the suite ~75×  slower); it was caught by noticing, not by a check. `TEST_FLOOR` counts tests,
  not seconds. A wall-clock ceiling in CI would be the floor-rule analogue — noted, not proposed as a
  slice.

---

## 5. Named next checkpoint

**Whichever comes first (§6):** ≤6 slices, or the next capability-cluster boundary.

**The direction fork goes to Bernardo** (Cowork surfaces it with this report), because it is
milestone-level and carries a doctrinal tension:

- **(c) generic-process framework + equity** — the actual bar-mover for B7 (`mc_exposure.py` crosses
  only with a `BlackScholesProcess`-shaped abstraction), and it opens a new asset class. Tension: §4
  says breadth waits while drawdown is stuck, but here the bar-mover *is* breadth.
- **(b) `SwaptionPrice` + consumer-narrow ticks** — moves the bar within what is already built, honours
  §4 literally, discharges a standing ruling, unblocks lattice/Bermudan. Smaller upside per slice.
- **hold B7** — close the XVA cluster as "analytic + MC exposure complete" and pick a different block.

**My recommendation: (b) then (c).** `SwaptionPrice` is ruled, small, and deletes a measured defect
rather than guarding it; and the consumer-narrow rule now in §4 gives a way to *target* ticks
deliberately for the first time, which is worth one slice of trying before accepting that only new
breadth moves the bar. If a consumer-narrow sweep yields little, that is itself the evidence for (c).

**No new slice until this report is ruled (§6).**
