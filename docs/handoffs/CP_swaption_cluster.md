# Checkpoint — the swaption / vol-cube cluster (capability-cluster boundary, §6 hard stop)

**Date:** 2026-10-26 · **Span:** v0.106.0 → v0.114.0 (9 versions) · **Baseline for ruling:** v0.114.0
**Trigger:** capability-cluster boundary — the cluster is complete (smile read + calibration + tick),
which §6 makes a hard stop in its own right, over and above ~4 slices since `CP_implied_vol.md` and
two immediate-stop triggers consumed this round (the B4 contract question; debt logged as
NG-DEFER-QUARRYIMPORT). **Mandate:** thread 0011.
**Tests:** 374 green, both OSes. **Drawdown: 23 / 793.** **Debt: 1 live item** (below).

---

## 1. Oracle-quality audit — against the AMENDED §6

This is the first audit run under the floor rule (`rulings_floor_rule.md`), and under doc 11's new
standing question: *for each gate, name the population it examined and the floor it held it to.*

| oracle file | tests | structural / floor oracle? | what it asserts beyond "a number matched" |
|---|---|---|---|
| `L4/test_capfloor.py` | 11 | **yes — count** | a 2Y cap has **7** caplets, first excluded; every ladder caplet carries the canonical accrual; ladders of different maturities are **prefixes** (audit #10's fix) |
| `L3/test_vol_strip.py` | 11 | **yes — count + finer grid + §3d identity** | the strip builds the **ladder**, not one caplet per quote; strip and pricer use the **same** ladder; each cap reprices on a **finer** caplet grid |
| `L3/test_swaption_cube_calibrate.py` | 8 | **yes — count + floor + non-vacuity** | every quoted node appears; a poisoned node is a **counted failure**; an empty grid is a failure, not an empty cube; and oracle 2's own non-vacuity is tested |
| `L4/test_swaption_sabr.py` | 10 | **yes — structural** | ATM payer on a **non-canonical** underlying prices at the marked S (the S-identity, not a scalar) |
| `L3/test_capfloor_sabr.py` | 6 | **yes — count** | `sorted(surface.params) == expected_expiries` — one fit per **ladder** expiry (line 141) |
| `L3/test_sabr_calibrate.py` | 9 | **NO — see finding O1** | round-trip, reprice identity, failure values. No assertion on its own collected population |
| `L3/test_implied_vol.py` | 12 | **n/a — scalar** | a scalar inversion collects/filters nothing, so the floor clause has no population to bind. Stated, not assumed |
| `L4/test_sabr_caplet.py` · `L4/test_multilaw_caplet.py` | 3 · 8 | **n/a — scalar**, +1 structural | per-strike reprices; `test_pricer_has_no_law_switch` asserts the absence of a type ladder (§1) |

**Finding O1 — the per-smile SABR fit is the one cluster gate with an unasserted population.**
`calibrate_sabr_smile` builds one residual per quoted strike and then accepts or rejects on
`max(abs(r) for r in residuals)`. Nothing asserts `len(residuals) == len(smile.strikes)`. If the
residual list were ever short, the 1bp gate would pass on the subset while the remaining strikes went
unfitted — the floor-less-filter shape, one level below the cube.

**CLOSED IN THIS COMMIT** — `test_the_fit_produces_one_residual_PER_QUOTED_STRIKE`
(`TEST_FLOOR` 374 → 375). Recorded as found rather than quietly fixed, because the *pattern* is the
review input, not the one test.

**Severity: low, and stated honestly rather than inflated.** It cannot happen today: `residual`
zips `strikes` with `vols`, and `SmileQuote.__post_init__` already guards their equal length, so the
population is *structurally* guaranteed. The gap is that it is guaranteed by an invariant and never
*asserted* — which is exactly the posture the cube deliberately took the other way (the type makes a
drop unrepresentable **and** the oracle asserts it anyway). One cheap test closes it.

**Everything else in the cluster carries a genuine structural oracle**, and three of them were
written *because* audit #10 taught the lesson. The cluster is in good shape by the standard that did
not exist when most of it was built.

---

## 2. Drawdown reconciliation — 23 / 793

Single source: `quarry_reconciliation.md`. Cluster ticks, in order:

| slice | version | module retired | tick |
|---|---|---|---|
| 20 | 0.106.0 | — (SABR caplet smile, read-not-solved) | 0 |
| 21 | 0.107.0 | — (SABR smile calibration) | 0 |
| 22 | 0.108.0 | `options/sabr.py` | 19 → 20 |
| 23 | 0.109.0 | `options/capfloor.py` | 20 → 21 |
| 24 | 0.110.0 | `options/implied_vol.py` | 21 → 22 |
| A (25) | 0.111.0 | — (`swaption_vol_cube.py` **partial** — read only) | 0 |
| B | 0.114.0 | `options/swaption_vol_cube.py` **closes** | 22 → **23** |

**Cowork ratified the slice-B tick** (thread 0011, stamped on the tracker row): retire-read
spot-checked per §4, every omission evidenced, all three deferrals are **capabilities not products**,
resident-importer precedent (`sabr.py` @ 25 importers) sound. 19 of the 23 are physically parked; 4
are ticked and awaiting the batch `git mv` at the topic close.

**Honest note on the pace:** 23 / 793 is **2.9%**. Four of this cluster's seven slices ticked nothing
— they built the capability the later ticks spent. That is the design working (§4 forbids
speculative infra, so the blocks land with their consumer), but it should not be read as 3% of the
work being done: the retired modules are among the quarry's smaller ones, and the un-crossed
remainder includes whole asset classes.

---

## 3. Challenge me — design choices worth attacking

1. **`NodeQuote = tuple[SwaptionSurfaceKey, SmileQuote]` and `CubeOutcomes` keyed by a 2-tuple.** I
   chose bare pairs over named types on §6b (one consumer ⇒ concrete). The cost is a public return
   type whose meaning is not readable from its signature. Is the rule of two right here, or is a
   `CubeNode` key the §3 vocabulary this cluster is missing?
2. **`SmileQuote.forward` pushed reconstruction to every consumer.** B4 deleted one shared
   reconstruction and `calibrate_capfloor_sabr` now rebuilds the caplet forward at its own call site.
   That is *correct* (each product's forward is its own), but it is also **one atom computed in two
   places** — the §3d smell the cluster already has twice (audit F9). Should `forward(projection,
   index.canonical_accrual(expiry))` be a named caplet-forward atom before a third consumer arrives?
3. **β is one scalar for the whole cube.** Explicit (F8) but not per-node. Real desks fit β per
   expiry/tenor or calibrate it. Is a single β a deferral worth naming, or an unstated assumption?
4. **`build_swaption_vol_cube` returns a plain `Mapping`, not a frozen value.** Everything else in
   the tree is frozen. Deliberate (it is a derived intermediate, not snapshot state) or drift?
5. **Oracle 3 is self-consistency** (round-trip a synthetic SABR smile). It is non-vacuous only
   because oracle 1 supplies the floor. Is that enough, or does the cube want a published-number
   oracle — a vendor cube node, or a Hagan table — at rung 2 rather than rung 4?
6. **`TEST_FLOOR` is one global number.** It catches total shrinkage but not a *tier* emptying while
   another grows. Per-tier floors would be stricter; is the global one the right simplicity?

---

## 4. Smell + debt scan

**Debt ledger: one live item.** `NG-DEFER-PROV` discharged this round (all 17 provenance paths now
resolve, and the gate asserts resolution). `verify.py debt` green; suppressions − ledger entries = 0.

### NG-DEFER-QUARRYIMPORT — folded in per thread 0011, with its options

**The fact:** `import pricebook.*` from `quarry/` raises `ModuleNotFoundError`.
`quarry/pricebook/core/__init__.py` imports `pricebook.core.discount_curve`, which was physically
parked to `quarry/parked/topic-01-yield-curve/` at the T1 close — doc 13 parking is a `git mv`, and it
left the package's own `__init__` re-exports dangling.

**Why it is checkpoint-grade rather than a side-ruling:**
- **§7c's "full sweep + quarry regression nightly" is currently unachievable.** It is written in the
  law as a standing obligation and cannot run.
- **A quarry module's behaviour cannot be established by execution** — only by reading it, or by
  replicating its arithmetic against ng. The slice-B audit did the latter to measure `bumped()`
  (5.43–6.19×) and the double ATM atom; that worked, but it is a workaround, and §7bb sanctions it as
  a *debugging technique*, not as the way oracles are established.
- **It will recur at every topic park.** Each park orphans more re-exports, so the condition worsens
  monotonically unless the mechanism changes.

**Options, with what each costs:**

| # | option | cost | tension |
|---|---|---|---|
| 1 | **Parking also prunes the `__init__` re-exports it orphans** | small, mechanical, at each park | changes "the quarry is read-only, never edited" (§4) — the quarry becomes *append-pruned* |
| 2 | **Accept read-only-by-reading; strike §7c's nightly quarry regression as unachievable** | zero code | the law loses a stated guarantee; every future quarry claim rests on reading + ng cross-check |
| 3 | **Restore the parked modules as import shims** (`core/discount_curve.py` re-exporting from `parked/`) | small, but adds files to the quarry | shims in a read-only tree; arguably worse than option 1 |
| 4 | **Leave it; establish quarry facts only by replication** | zero | makes the slice-B workaround the standing policy, un-ratified |

**My reading, for you to rule:** option 1 is the honest fix — parking is *already* an edit to the
quarry (a `git mv`), so §4's "never edited" has in practice meant "never edited **in substance**".
Pruning a re-export the park itself broke is repairing the park, not editing the content. Option 2 is
the honest fallback if §4 is to stay literal, but it should then say so in the law rather than leave
§7c promising a sweep that cannot run.

### Smells noted, none load-bearing
- `AUDIT_slice_B_forward_threading.md` cites "48.8bp" from slice A; the slice-B grid measured
  **6.37–6.38bp**. Both are correct (different conventions and parameters) but the cluster now carries
  two different numbers for "the S gap" and a reader could conflate them.
- `docs/handoffs/` is at 25 `CP_*` + 5 `AUDIT_*` + 2 `rulings_*` + 2 `spec_*` + 1 `record_*`. Still
  navigable via `docs/README.md`, but the naming is now four conventions deep.

---

## 5. Named next checkpoint

**Whichever comes first (§6):** ≤6 slices, or the next capability-cluster boundary.

**Recommended next work, for your ruling:** the cluster's own forward-links are now the cheapest
ticks — `options/synthetic_swaption_data.py` (re-point or drop; it is the resident importer holding
`swaption_vol_cube.py`'s physical park) and the `options/swaption*.py` family that the vol-cube work
has now equipped. The alternative is to spend this checkpoint's ruling on
**NG-DEFER-QUARRYIMPORT first**, since option 1 would change §4 and every later park inherits the
decision — doing it before the next park is cheaper than after.

**No new slice until this report is ruled (§6).**
