# Checkpoint — the XVA / exposure-risk family (CVA → DVA → FVA → BCVA → WWR)

**Date:** 2026-10-30 · **By:** Code · **Baseline:** v0.142.0 · **Tests:** 600 green, both OSes,
ruff + pyright clean, zero suppressions. **Drawdown: 32 / 793.** **Debt: 6 live ledger items** (see §4 — the count itself needed correcting).

**Slices since `CP_equity_process`: 3** (v0.140.0 → v0.142.0). *Correction to the ask: thread 0074
said six. `CP_equity_process` covered v0.129.0 → v0.138.0 and was itself written in v0.139.0, so
the window is three. The **≤6-slice cadence has NOT fired** — the valid trigger is the
**capability-cluster boundary**, the XVA/exposure-risk family closing. Recorded because a
checkpoint that misstates its own window is the wrong artifact to start an audit with.*

---

## 0. What this family is, now that it is whole

One `cva`, one integral, one profile shape — across four asset-class paths and five adjustments:

```
exposure_integral(profile, weights)         ← the ONE integral
   ├── cva   : weights = LGD · ΔQ(counterparty)
   ├── dva   : the SAME call, ENE profile + own curve        (no new formula)
   ├── fva   : weights = funding spread · Δt                 (not survival-weighted, on purpose)
   └── (kva) : weights = hurdle · Δt                         (the shape already fits — deferred)

bcva = cva − dva                                            (pure combination, no new input)

(date, EE) profile  ← ONE shape, produced by four builders and WWR's conditional form,
                      whose ρ=0 degeneracy IS the marginal one
```

**The family's single most useful property is that nothing in it is a special case.** DVA is `cva`
at different arguments; BCVA is subtraction; WWR is the same profile conditionally computed; KVA
already has its weight shape. Three times this run, a quantity that looked like new work turned
out to be an existing atom at different arguments — and each time a test asserts the equality
exactly, so it cannot drift into two definitions later.

---

## 1. Oracle-quality audit

Run under doc 11's first question — *what makes this red, and can that happen?*

| oracle | rung | what makes it red |
|---|---|---|
| `EPE(tᵢ) − ENE(tᵢ) = V₀` | **1** | an identity (`max(V,0)−max(−V,0) ≡ V` + the martingale); **non-vacuous because a forward's ENE is non-zero**, which a long option's never is |
| a long option's ENE ≡ 0 | structural | the sign-confusion case the forward test would pass on symmetry |
| `DVA == cva(ene, own, …)` | exact | a second DVA definition appearing |
| `cva`-via-the-shared-atom == `cva` | **ULP** | the integral diverging between CVA and FVA (the `rpv01` lesson) |
| `survival_weights` sum to `1 − Q(tₙ)` | **1** | levels substituted for increments |
| flat-spread FVA closed form; `s_f → 0 ⇒ 0` | **1** | FVA picking up a survival weight it must not have |
| BCVA sign flip when own credit dominates | structural | the classic bilateral sign error, invisible to magnitude checks |
| **`ρ → 0` reproduces the marginal CVA, `0.00e+00`** | **1 / exact** | nothing — *by construction*, one driver mapping and a shared seed stream |
| no `rho` branch (AST) | structural | an `if rho == 0: return marginal`, which would make the line above vacuous |
| wrong-way raises / right-way lowers; monotone in ρ | structural | a sign or direction error (0.01× → 3.77× across ρ) |
| the conditional **profile** moves with ρ | structural | conditioning leaking in through the survival weights instead |
| every profile is PV-dimensioned | **cross-module** | a builder disagreeing with `cva`'s convention — see §3 |

**No rung-4 self-consistency oracle anywhere in this family either**, which now holds across two
consecutive runs. Every anchor is a closed form, an exact identity, or a structural invariant.

**The ρ→0 anchor is the best oracle this project has produced**, and worth naming why: it is not a
tolerance between two estimators but an *identity* arranged in the code — the marginal and
correlated samplers compose the **same** driver mapping, so agreement is structural rather than
numerical. The AST guard is what keeps it that way. That is the pattern to reach for whenever a
new capability claims to generalise an old one.

---

## 2. Quarry-drawdown reconciliation — 32 / 793, and B7's cheap mass is spent

| version | Δ | what, and why it did or did not tick |
|---|---|---|
| 0.140.0 | **+1** | `XvaReport` → **`models/mc_exposure.py` retires** (31 → 32). All ten `to_dict` names superseded |
| 0.141.0 | 0 | FVA/BCVA: `xva.py`'s **features** crossed, the **module** did not — `kva` and `repo_gap_risk` are consumed and ng has neither |
| 0.142.0 | 0 | WWR: `gbm.py`'s `generate` is consumed by **path-dependent payoffs**, not WWR |

**The honest read, which is the input to the next-unit decision.** Every remaining B7 tick now
needs a **heavy new vertical**:

| blocked module | gated on | weight |
|---|---|---|
| `risk/xva.py` (783L, 9 importers) | `kva` → a **capital/RWA** concept ng has none of · `repo_gap_risk` → the **repo** family (~18 un-built modules) | both heavy |
| `models/gbm.py` (126L, 4 importers) | `generate` → **joint paths over a grid** for Asian / Bermudan-LSM payoffs | heavy (a new numerics family) |

So the pattern that held through (b) and (c) holds again: **the cheap mass is spent at every
level we have reached.** (b)'s measurement harvest gave four ticks and stopped; (c)'s asset class
gave one; B7's family gave one. 32/793 = **4.0%** after 31 landed slices.

**What is NOT true:** that the work was unproductive. The three families built since the restart
(credit, equity, XVA/exposure) are each *complete and oracled*, and the tree is now genuinely
cross-asset on one vocabulary. The bar measures quarry deletion, not capability — and §4 is
explicit that drawdown reports and never steers. But three consecutive runs ending at "the next
tick needs a heavy vertical" is itself evidence about scope, and it belongs in front of Bernardo
rather than inside a slice.

---

## 3. Challenge me

1. **The 5.14% discounting bug is the finding of this run, not WWR.** For two slices equity CVA and
   every `XvaReport` adjustment were too large, because three builders discounted and one did not
   while `cva` discounts nothing. **Every oracle passed** — the martingale oracle asserted
   `EE = V₀/df`, exactly what an undiscounted profile gives, so it validated the builder against
   itself. *Challenge:* is the cross-module clause enough? **My answer: not on its own.** The clause
   says compare the modules; it does not say *which* conventions exist. A conventions register —
   "profiles are PV-dimensioned", "vol is on the ACT/365F clock", "profiles exclude historical
   flows" — would make them enumerable instead of folkloric. I am not proposing it as law yet (one
   instance), but it is the shape I would reach for on a second.
2. **`norm_ppf_vec`, `black_vec`, `bond_vec` — three vector twins now.** Each is bound to its
   scalar by an exact elementwise test, so §3d holds. *Challenge:* three is the threshold where a
   pattern should become a mechanism. **My answer: not yet, and here is the trigger** — the twins
   share no code, only a shape, so a mechanism would be a decorator or a dispatch layer over
   functions that are three lines each. Revisit when a twin needs *more* than `np` substitution.
3. **WWR conditions analytically rather than simulating joint paths.** Exact, and it dissolved the
   joint-path requirement. *Challenge:* does that leave first-to-default BCVA further away?
   **Yes, honestly** — FTD needs a genuine joint *default* law across two entities, which neither
   this nor the deferred path-grid work provides. It stays deferred and unaffected.
4. **`CorrelationKey` holds one pair, not a matrix.** Right for one driver and one factor; the
   widening trigger is named. *Challenge:* a second factor forces a decision about correlation
   *consistency* (a keyed set can be non-PSD where a matrix cannot). Flagged now so it is not
   discovered later: **the first multi-factor consumer owes a PSD check.**

---

## 4. Smell + debt scan

- **6 live ledger items — and the count in the last two checkpoints was WRONG.** `OPEN.md` has 13
  `**NG-` headers, but four items are closed or discharged and each keeps a second header line for
  the record (`NG-WATCH-CLOCK`, `NG-DEFER-QUARRYIMPORT`, `NG-DEFER-PROV`, `NG-DEFER-1`). Grepping
  headers therefore double-counts the dead ones: `CP_equity_process` said 12 and the one before it
  said 11, both measuring lines rather than live items. **Live:** `NG-DEFER-CUBEBETA` ·
  `NG-DEFER-CUBEORACLE` · `NG-WATCH-TIERFLOOR` · `NG-DEFER-THETA-COUPON-GUARD` ·
  `NG-DEFER-CREDITISDA` · `NG-DEFER-DF-CONTINUOUS`. All deferred scope with named triggers; none
  buys a green oracle. *(This is a small instance of the lens this run put at the top of the audit:
  a count nobody checks is a check that cannot fail. The debt gate verifies suppressions **equal**
  ledger entries, so it never cared how many there were — only that the two sides matched.)* **Zero suppressions in `src/`** — twice this run a `# noqa` or
  `# type: ignore` was the easy path and was fixed instead (the 7-arg signature folded into
  `ProtectionWindow`; four ignores typed away; `SLF001`'s single hit fixed by passing the rule set
  in rather than ledgering it).
- **`NG-DEFER-THETA-COUPON-GUARD`** remains the weakest guarantee in the tree — a documented
  precondition on a public function. Trigger unchanged and still correct.
- **The per-path scalar loop has now fired three times** (73 s rates MC, 59 s equity exposure,
  and a WWR copula that did not finish in 120 s). The clock gate catches it, but Cowork's note is
  right: *vectorise the closed form before writing the path loop* needs to be a build habit, not a
  gate's job. Recorded here as a build-time default rather than a new rule.
- **`risk/` is at eight modules** (`exposure`, `mtm`, `greeks`, `equity`, `credit`, `xva`,
  `xva_report`, `wwr`, `bump`, `monte_carlo`, `priceable`). The `exposure`/`mtm` split held; no
  module is over ~340 lines. Next pressure point is `xva.py` + `xva_report.py` + `wwr.py` all being
  "XVA" — if a fourth arrives, they want a subpackage, not another sibling.
- **Gate inventory, for the record:** `acyclic` · `layers` · `fields` · `debt` · `version` ·
  `provenance` · `quarry` · `slow` · `tests` (floored at 600) · ruff (`PLR0913`, `SLF001`) ·
  pyright 1.1.411. Four of these exist because a defect got through: `slow`, `SLF001`, the test
  floor, and the provenance resolution check.

---

## 5. The next unit — a milestone-grade fork, surfaced not chosen

Three options, with what each actually costs:

| option | what it buys | what it costs |
|---|---|---|
| **(i) a heavy B7 vertical** — capital/RWA (→ KVA) or repo | retires `xva.py` (783L, the single largest resident module) | capital/RWA is a new regulatory concept tree; repo is ~18 modules |
| **(ii) path-dependent payoffs** — joint paths + LSM/Asian | retires `gbm.py`; unblocks Bermudan/American, a large exotic family | a new numerics family (path grids, regression, variance reduction) |
| **(iii) B8 portfolio/lifecycle** — the next block in the ratified build order | the only block never opened; `pe`, benefit table, P&L already have L6 homes | breadth again, and B8 does not retire B7's residents |

**My reading, offered as input and not as a decision:** (ii) is the most *unblocking* — path
dependence is what Asian, Bermudan, callable and LSM all wait on, which is the largest single
cluster of un-built quarry modules. (i) retires the most lines. (iii) follows the ratified build
order and is the only block untouched. **Per §4 the drawdown number must not pick between them**,
which is exactly why this belongs in front of Bernardo with the scope question already open.

---

## 6. Named next checkpoint

**`CP_next_vertical`** — at the first of: 6 slices after the next unit opens, or that unit's own
capability-cluster boundary. Immediate-stop triggers unchanged. If Bernardo's scope ruling changes
the migration stance (full-migration vs something narrower), the **next checkpoint is that
ruling's record**, not a slice count.
