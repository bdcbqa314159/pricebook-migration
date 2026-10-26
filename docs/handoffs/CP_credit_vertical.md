# Checkpoint — the credit vertical (capability-cluster boundary, §6 hard stop)

**Date:** 2026-10-26 · **Span:** v0.118.0 → v0.121.0 (4 slices) · **Baseline:** v0.121.0
**Trigger:** capability-cluster boundary — the **vanilla credit arc is complete**: L0 identity → L1
survival curve → L3 bootstrap → L2 product → L4 mark → L5 CS01/bucketed/rec01. §6 makes that a hard
stop in its own right; Cowork named it in thread 0027, due before any index/basket/exotic work.
**Tests:** 430 green (55 of them credit), both OSes. **Drawdown: 26 / 793.** **Debt: 5 live items.**

---

## 1. Oracle-quality audit — against the amended §6

| oracle file | tests | structural / floor? | what it asserts beyond a number |
|---|---|---|---|
| `L1/test_survival_curve.py` | 13 | partly | `Q(t)=exp(−λt)` to **1e-12** (rung 1); monotone-Q and domain guards; the past-date boundary |
| `L3/test_credit_bootstrap.py` | 12 | **yes — count + floor** | **N quotes → N pillars**, one residual each; an unfittable pillar is a *named* `CalibrationFailure`; empty grid is a failure |
| `L4/test_cds.py` | 13 | **yes — non-telescoping** | the **off-par** closed-form mark (a par CDS is worth zero, so par-only telescopes); every bootstrapped pillar marks to zero |
| `L5/test_credit_risk.py` | 9 | **yes — decomposition + count** | bucketed CS01 **sums to** parallel; **N segments → N buckets**; **buckets past maturity are zero** |
| `L5/test_credit_recovery.py` | 8 | **yes — unrepresentability** | the two-R divergence is asserted *absent from the type*, not merely untested; byte-identical refactor guard |

**Rung-1 content, not self-consistency.** Four independent closed forms carry this vertical: the
analytic protection integral `(1−R)λ/(r+λ)(1−e^{−(r+λ)T})`; the continuous par spread `λ(1−R)`;
`∂PV/∂λ` differentiated by hand; and `∂PV/∂R = −protection/(1−R)`. Plus one cross-atom identity that
was not designed in and turned out exact: **`risky_annuity` at λ=0 IS `rpv01`** to 1e-12 — §3d
proving itself, since the credit annuity *is* the rates annuity when nothing defaults.

**Finding O1 — WITHDRAWN, it was wrong.** The draft claimed the survival curve had no
*interpolation* oracle. It has had one since slice 1:
`test_piecewise_constant_hazard_between_pillars_is_log_linear_in_Q` builds a **non-flat** two-segment
curve and checks an analytic intermediate `Q` strictly inside a segment, discriminating against the
wrong (linear-in-Q) scheme by **1.66e-3** at a 1e-10 tolerance. The finding came from under-auditing
the test file while writing this report; Cowork independently reached the same place from the other
direction (ruling: closable analytically, no vendor needed). Recorded rather than quietly deleted —
**an audit that invents findings costs the same credibility as one that misses them**, and the
corrective is the same: read the file, not the memory of it. `NG-DEFER-SURVIVALINTERP` is NOT
ledgered. Two modest strengthenings did land in v0.122.0 (the first segment, and a three-segment
curve probed in its middle).

**Three divergences this vertical caught, all by oracle rather than review** — worth recording
because they are the same shape: ① the protection-window day count (ACT/360 vs the curve's ACT/365F)
— caught by par-to-zero; ② recovery in two homes, ≈96bp on a par quote — caught by Cowork's review of
the slice-3 report, then measured; ③ `bumped_at` reached through a `CurveHandle` — caught by pyright.
**One was found by a human reading a report, not by a gate.** That is the honest score.

---

## 2. Drawdown reconciliation — 26 / 793

| slice | version | tick | module |
|---|---|---|---|
| 1 | 0.118.0 | 0 | `core/survival_curve.py` **partial** (9 methods residual) |
| 2 | 0.119.0 | 0 | `credit/cds.py` **partial** (20 methods); survival residual 9 → 7 |
| 3 | 0.120.0 | **+1** | **`credit/credit_risk.py` RETIRED** → 26 / 793 |
| 4 | 0.121.0 | 0 | §3d refactor; `cds.py` residual → ~14 |

**The credit bar moved once in four slices, and the reason is structural.** `quarry/pricebook/credit/`
is **94 modules**; one has crossed. The quarry's credit code is *fat* (`cds.py` alone is 1035 lines
with 20 methods on one class) while ng's equivalents are deliberately thin, so a vanilla vertical
supersedes a minority of each file it touches. The tick came from `credit_risk.py` — the one module
whose *consumed surface* (two private bump helpers) was entirely superseded. **That is the pattern to
steer by: ticks come from modules whose consumers use a narrow surface, not from modules we have
"mostly covered".**

Honest projection: at 1 tick per 4 slices, `credit/` alone is ~370 slices. The bar moves on
**consumer-narrow modules** and on the eventual retirement of fat ones once their desk residuals have
somewhere to go (L5 risk took 6 of `cds.py`'s 20 methods; L6 book and quote conventions would take
~6 more).

---

## 3. Challenge me

1. **`PremiumLeg` duplicates `FixedLeg`** — both are `(schedule, day_count, rate|spread)`. I mirrored
   deliberately, but is this the third occurrence that should become one `AccrualLeg`, or are a
   coupon and a CDS spread different ideas that must not merge (the DRY-is-about-knowledge rule)?
2. **`protection_leg` takes an `Accrual` whose day_count is only an integration basis**, never an
   accrual convention — a misleading parameter that already caused divergence ①. Should it take
   `(start, end)` plus the curve's measure instead, making the wrong call unwritable?
3. **The CDS mark reads `recovery` from the snapshot but the quarry has a `recovery_curve.py`** —
   term-structured recovery. A flat scalar is right for vanilla; is `RecoveryKey → float` a shape
   that will have to break, or does a term structure arrive as a *different* key?
4. **`IntegrationConfig` is threaded but only the CDS reads it.** One consumer. Is the arity-dispatch
   mechanism in `registry.dispatch` earning its keep, or should numerics be on the model instead?
5. **No `jump_to_default`**, deferred — but JTD is arguably the *defining* credit risk, and it is a
   one-liner on the atoms (`(1−R)·N − accrued`). Is deferring it right, or is it the cheapest real
   gap in the vertical?
6. **Credit has no L6.** `CreditBook`/`CreditPosition` are deferred, so there is no per-name netting
   or `cs01_by_name`. Does the credit cluster close without it, or is a book slice part of "vanilla
   credit complete"?

---

## 4. Smell + debt scan

**5 live ledger items**, all deferred *scope* with triggers, none hiding wrongness; `verify.py debt`
green (suppressions − entries = 0).

| item | what | trigger |
|---|---|---|
| `NG-DEFER-CREDITISDA` | no ISDA cross-check; gate met at rung 1 without it | a citable ISDA worked example |
| `NG-DEFER-DF-CONTINUOUS` | `df(date)` ⇒ day-granularity floor in time-integrals | first sub-day consumer (a protocol widening) |
| `NG-DEFER-CUBEBETA` | one β for the whole swaption cube | first per-node-β consumer |
| `NG-DEFER-CUBEORACLE` | cube round-trip is rung 4 | a citable vendor/textbook cube node |
| `NG-WATCH-TIERFLOOR` | `TEST_FLOOR` is global, not per-tier | first tier rebalance |

**Smells, none load-bearing:** `risk/credit.py` and `engine/credit.py` and `products/credit.py` and
`calibration/credit.py` are four files named `credit.py` in four packages — correct by layer, but
`from ... import credit` is now ambiguous to a reader. And `docs/handoffs/` is at 40+ files across
five naming conventions (`CP_`, `AUDIT_`, `rulings_`, `spec_`, `RETIRE_`, `record_`).

---

## 5. Named next checkpoint

**Whichever comes first (§6):** ≤6 slices, or the next capability-cluster boundary.

**Recommended next work, for the ruling:** not more credit product. The bar argument in §2 says the
next tick comes from **consumer-narrow modules**, and the §3 challenges 5 and 6 (`jump_to_default`,
the credit book) are the two cheapest real gaps in the vertical — JTD is a one-liner on existing
atoms and the book would take `CreditBook`/`CreditPosition` plus part of `cds.py`'s desk residual.
The alternative is to close credit here and open the next B-block, leaving index/basket/exotic credit
for a later pass.

**No new slice until this report is ruled (§6).**
