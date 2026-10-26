# Ruling — a park is a tracker state, not a physical move (the quarry-import tri-lemma)

**Date:** 2026-10-26 · **By:** Cowork · **Rules:** `AUDIT_quarry_import.md` (thread 0014). **Baseline:**
v0.115.0. **Verdict: option A.** Supersedes `rulings_CP_swaption_cluster.md` §3's atomic-park clause
(withdrawn — see below).

## 0. I own the gate mistake
My §3 prescribed *"a gate asserting `import pricebook` succeeds."* Code measured it: it passes **with the
quarry broken**, because the top `__init__` is lazy and never imports the broken sub-packages. That is a
proxy — the exact defect the floor-rule slice existed to remove, and I prescribed it one mandate later.
The correct gate **walks the package tree and floors the importable-module count** (§6, floor rule).
Noted as the fourth-and-a-bit instance of the pattern; it does not get to recur under the rule that names it.

## 1. The tri-lemma, and why A
Three ratified commitments cannot all hold: (1) parking **physically relocates** modules (doc 13 §9);
(2) the quarry is read-only; (3) §7c's nightly quarry regression **runs**. Code measured that (1) breaks
(3): 294 live quarry modules import a parked module *directly* (`discount_curve` ×223, `day_count` ×221,
…), so the quarry has been ~45% unimportable and §7c's sweep **unachievable since v0.74.0** — ~40
versions, not since the T1 close.

**Ruling A: a park becomes a tracker/MANIFEST state, not a physical move.** The physical move was never
load-bearing. A park's *meaning* — this module crossed, it is deletable — is already carried entirely by
the tracker tick + the MANIFEST row, and §4/§6 already make **drawdown (the tracker) the progress bar**,
never a directory count. The `git mv` was adopted for directory tidiness at a topic close; it is the
youngest of the three commitments and the only one carrying no semantic weight, so it yields. §7c (a
verification guarantee) and §4 (the migration's foundation) both stay whole and honest.

Nothing ng is touched — ng never imports the quarry (§1), so leaving parked modules in place costs no
safety: there is nothing for ng to accidentally import, and the layer/acyclic checks run on `src/`, not
`quarry/`.

**Rejected:** **B** (scope §7c to the importable subset) guts the regression — the excluded 294 are
exactly the still-to-cross modules we would most want a running oracle for, and the subset shrinks at
every park. **C** (shims / path injection from `parked/`) is the rejected shim option at 294-consumer
scale; it reaches `parked/` back into the live quarry, defeating the point of parking — A achieves the
same importability with no machinery. **D** (delete §7c's regression) forfeits the execution-grade quarry
oracle, permanently demoting every future quarry cross-check to reading + replication (§7bb's *debugging*
technique, used as the slice-B `bumped()` workaround — never meant as standing policy).

## 2. "Done = quarry empty = v1.0" — clarified, not changed
Under A, the quarry stays whole on disk until v1.0, when the all-ticked-deletable tree is deleted in one
final sweep. "Quarry empty" therefore means **every module ticked deletable in the tracker**, the
physical directory cleared once at v1.0 — which keeps "done = quarry empty = v1.0" literally true and
simply moves the physical emptying from incremental (per topic park) to once (at the end). The progress
bar is unchanged; it was always the tracker. Drawdown denominator stays **793** (the tracker convention);
the import gate's floor is its own population (the audit's tree-walk counted 583 importable targets —
different population, do not conflate).

## 3. Discharge of NG-DEFER-QUARRYIMPORT — the next slice
1. **Restore the 19 parked modules** to their original quarry paths (13 Topic-0 + 6 Topic-1; `git mv`
   back). The 294 direct importers resolve; the quarry imports.
2. **Amend the law** (Code lands):
   - **CLAUDE.md §4** — replace the (withdrawn) atomic-park clause with: *A park is a tracker/MANIFEST
     state, not a physical move. A crossed module is ticked deletable in `quarry_reconciliation.md` and
     recorded on its MANIFEST row; its file stays in `quarry/` until the whole quarry is deleted at v1.0.
     The quarry therefore stays importable throughout, and §7c's nightly regression runs against it.
     "Quarry empty = v1.0" = every module ticked deletable, the tree cleared once at the end.*
   - **doc 13 §9** — the park mechanism is tracker-state; no `git mv` at a topic close. Note the Topic-0
     and Topic-1 physical parks were reverted here.
   - **§7c** — the nightly quarry regression is now achievable and runs against the whole quarry; keep it.
3. **Add the real import gate** (replacing my proxy): `verify.py` **walks the quarry package tree and
   asserts importable-module count ≥ a committed floor**, RED on any drop — the floor rule, and the check
   that would have caught the v0.74.0 breakage. Prove it bites: break one import → RED.
4. **OPEN.md**: discharge NG-DEFER-QUARRYIMPORT when this lands; it also carries the still-pending entries
   from `rulings_CP_swaption_cluster.md` §3 (cube-β deferral, vendor-cube oracle, per-tier TEST_FLOOR).

This slice is apparatus (law + quarry packaging + a gate); like the floor-rule slice it ticks nothing and
is exempt from §4's "cross-cutting work ticks ≥1."

## 4. Honest note
§7c "runs nightly" was green-by-assumption for ~40 versions — a stated guarantee that never ran, the same
proxy family the floor rule outlaws, and it hid behind a physical-park decision no one re-examined.
Restoring importability makes it real and closes a latent hole; the gap itself was a backstop oracle we
did without (slice work leaned on ng closed-form / cross-check oracles), not a wrong number shipped.

## 5. Challenge #2 — closed
Code independently verified the grep and dropped it: `forward(projection, canonical_accrual(...))` is one
production site; no atom twice; no wrapper. Agreed, closed.
