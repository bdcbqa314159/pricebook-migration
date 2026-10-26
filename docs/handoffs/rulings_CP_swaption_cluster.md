# Ruling — swaption/vol-cube cluster checkpoint + NG-DEFER-QUARRYIMPORT

**Date:** 2026-10-26 · **By:** Cowork · **Rules:** `CP_swaption_cluster.md` (thread 0012). **Baseline:**
v0.114.0 (checkpoint) / v0.115.0 (report landed). **Verdict: checkpoint RULED, cluster CLOSED.**

## 1. The four review inputs — ruled

**Oracle-quality audit — ACCEPTED.** Five of nine oracle files carry a genuine structural/count/parity
oracle; three are scalar with no population to floor and the report *states* that per doc 11's new
line rather than leaving it implied — which is the standard working. **O1** (the per-smile fit built
one residual per strike but never asserted `len(residuals)==len(strikes)`) was found and closed in the
same commit, `TEST_FLOOR` 374→375 — and recorded *as found*, not quietly fixed. That is the floor-rule
posture applied one level below the cube, and finding it under the amended §6 is the rule earning its
place. Accepted as closed; severity-low reasoning (the `SmileQuote` invariant structurally guarantees
the length) is honest and correct.

**Drawdown — 23/793, already Cowork-ratified** (thread 0011, stamped on the tracker's slice-B row).
The honest-pace note (2.9%; four of seven cluster slices ticked nothing — they built the capability
the later ticks spent) is accurate and is §4 working as designed; it is right to record it rather than
let "7 slices" read as 7 modules.

**Smell + debt scan — ACCEPTED**, NG-DEFER-QUARRYIMPORT ruled in §3 below. The two noted smells are
minor: fix the "S gap" two-numbers confusion (48.8bp slice-A vs 6.37–6.38bp slice-B — both correct,
different conventions/params) with a one-line note where each is cited; the four-conventions-deep
`docs/handoffs/` naming is housekeeping, not urgent.

## 2. Challenge-me — ruled, each on the merits

1. **Bare `tuple` keys over a named `CubeNode`.** Keep concrete — §6b rule of two holds at one
   consumer. The readability cost is real but does not buy a type yet. **Promote to a `CubeNode` key
   when the deferred off-pillar-interpolation consumer arrives** (it will also key by node → the second
   consumer). Forward-link on that row.
2. **`SmileQuote.forward` "in two places" — NOT a §3d violation.** Grounded by grep: the shared atom is
   `forward(curve, accrual)` (`building_blocks.py:76`), composed everywhere with the accrual each
   product defines — the opposite of F9's duplicated, disagreeing implementations. The canonical
   caplet-forward `forward(projection, canonical_accrual(expiry))` appears **once** in production
   (`sabr_calibrate.py:197`); the cube composes `float_leg_pv/rpv01`, a genuinely *different* forward.
   No atom is computed twice. **Do not add a `caplet_forward` wrapper** — it would be §6b speculative
   indirection over a one-line composition with a single consumer. If a *second* production site ever
   computes the same canonical-caplet-forward expression, rule of two trips and it is named then.
3. **β is one scalar for the whole cube — a DEFERRAL, and it must be NAMED, not left unstated.** A
   single explicit β is a legitimate simplification for the current oracle and blocks nothing, but
   real cubes fit β per node or calibrate it. **Ledger it** (OPEN.md): *cube β is a single explicit
   scalar; per-node / calibrated β deferred → first consumer that needs a non-flat β (a desk
   calibration slice, or a market with documented per-tenor β).* Honesty over a silent assumption.
4. **`build_swaption_vol_cube` returns a plain `Mapping`.** Acceptable — it is a derived intermediate,
   not snapshot/product state, so invariant 3 (frozen engine inputs) does not bind it. Minor polish:
   return it as a read-only mapping (`MappingProxyType` or a frozen wrapper) to match the tree's
   no-mutation posture. Not a blocker.
5. **Oracle 3 is self-consistency (rung 4).** Acceptable: the cube *assembles* nodes whose SABR math
   already carries the Hagan closed-form reference (slices 20/21) and the structural count (oracle 1)
   makes the round-trip non-vacuous. A published swaption-cube node (a vendor mark or a textbook cube)
   would lift it from self-consistency to a cross-check/trusted-mark oracle — **ledger as
   oracle-strengthening, deferred to the first available vendor/textbook cube.** Not required to close
   the cluster.
6. **`TEST_FLOOR` is one global number.** Acceptable now — it catches the observed failure class (the
   `--layer 0` bug: 177 < 366 would RED). Per-tier floors are the stricter form and more in the floor
   rule's spirit, but §6b says do not add the complexity without a present need. **Watch-item (ledger):
   adopt per-tier floors the first time a slice moves tests between tiers such that the total is
   preserved while a tier shrinks** — that is the case the global floor goes blind to.

## 3. NG-DEFER-QUARRYIMPORT — RULED: option 1 (atomic parking), §7c kept

**Ruling: option 1, reframed.** A park is **atomic** — a `git mv` that relocates a module out of the
live quarry package also **prunes the `__init__` re-exports it orphans**, so the quarry package stays
importable. This is *completing* the park operation (doc 13 already sanctions the `git mv`), not a new
licence to edit the quarry. §4's "never edited or deleted" protects the quarry as **source material** —
its financial content, the conventions/formulas/edge cases we mine; an `__init__` re-export is
*packaging*, carries no financial content, and the park itself is what broke it. Pruning a dangling
re-export repairs the park; it never touches what the quarry asserts about finance.

**§7c's nightly quarry regression is KEPT, not struck** (rejecting option 2). A *running* quarry is a
real oracle source — it lets a quarry fact be established by **execution** (the strong form) rather
than by reading + ng replication (§7bb's debugging technique, which the slice-B `bumped()` measurement
used as a workaround, not a standing policy). Striking a law obligation because the mechanism broke it
is backwards; fix the mechanism. Options 3 (shims into a read-only tree) and 4 (make the un-ratified
workaround standing policy) are both rejected for the reasons the report gives.

**Discharge, as the next slice (do it before the next topic park — the cost argument is right):**
- Amend CLAUDE.md §4 with the atomic-park clause (wording below; Code lands it).
- Prune the currently-dangling re-exports the T1 park orphaned (`quarry/pricebook/core/__init__.py`'s
  `discount_curve` et al.), and repoint `options/synthetic_swaption_data.py`'s import of the retired
  `swaption_vol_cube` — restoring `import pricebook.*` from `quarry/`.
- Add a CI gate asserting the quarry package **imports** (floor-rule shaped: a gate that asserts the
  property, not that a sweep merely ran) — this is the check that would have caught the T1 breakage.
- This slice is apparatus; like the floor-rule slice it ticks nothing, and is exempt from §4's
  "cross-cutting work ticks ≥1" (that rule governs ng software infra built ahead of consumers, not
  law/apparatus repair).

### CLAUDE.md §4 amendment wording (Code lands in the import-fix slice)
Add to the "Quarry is read-only" bullet:

> **A park is atomic.** Parking a module (`git mv` into `parked/`, doc 13) also prunes the `__init__`
> re-exports that move orphans, so the quarry package stays importable and §7c's nightly quarry
> regression keeps running. This is completing the park, not editing the quarry: "never edited"
> protects the quarry's *financial content* (conventions, formulas, edge cases — the material we
> mine); an `__init__` re-export is packaging, and the park itself is what broke it. A CI gate asserts
> `import pricebook` from `quarry/` succeeds (floor rule — assert the property, not that a sweep ran).

### OPEN.md entries (Code lands)
- Discharge **NG-DEFER-QUARRYIMPORT** when the import-fix slice lands.
- Add **cube-β-single-scalar** deferral (challenge-me 3) with the trigger above.
- Add **oracle-strengthening: vendor/textbook swaption-cube node** deferral (challenge-me 5).
- Add **per-tier TEST_FLOOR** watch-item (challenge-me 6) with the tier-rebalance trigger.

## 4. Named next work
1. **The import-fix slice** (NG-DEFER-QUARRYIMPORT discharge, §3) — first, before the next park.
2. Then the cluster's cheap forward-link ticks: `options/synthetic_swaption_data.py` (re-point or
   drop — its import is handled in slice 1 above, so this may reduce to the drop decision) and the
   `options/swaption*.py` family the vol-cube work has now equipped.

**Next checkpoint (§6):** whichever comes first — ≤6 slices, or the next capability-cluster boundary.
