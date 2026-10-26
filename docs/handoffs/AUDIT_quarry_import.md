# Audit — the quarry-import fix: STOP. Pruning re-exports cannot discharge it (measured)

**Baseline:** v0.115.0 · **Mandate:** `rulings_CP_swaption_cluster.md` §3 (option 1, atomic parking)
**Trigger:** §6 immediate stop — the ruling's prescribed fix is **insufficient**, measured by
executing it. Found before the slice's first law edit.

## 1. The prescribed gate is itself a proxy

The ruling asks for *"a CI gate asserting `import pricebook` from `quarry/` succeeds."* **That gate
passes today, with the quarry broken:**

```
import pricebook               OK
import pricebook.core          ModuleNotFoundError: No module named 'pricebook.core.discount_curve'
import pricebook.curves        ModuleNotFoundError: No module named 'pricebook.curves.bootstrap'
import pricebook.options       OK
import pricebook.fixed_income  OK
```

The top package's `__init__` does not eagerly import the broken sub-packages, so the shallow check
resolves a name and proves nothing. **Any gate here must walk the package tree and hold a floor on
the module count** — the floor rule applied to this gate, exactly as §6 now requires. Recording it
because it is the same defect the floor-rule slice existed to remove, found in the very next mandate.

## 2. The prune is necessary but NOT sufficient — executed and measured

`core/__init__.py` carries **7** dangling re-exports (`discount_curve`, `schedule`, `day_count`,
`calendar`, `currency`, `interpolation`, `solvers`); `curves/__init__.py` carries **1** (`bootstrap`).
I pruned all 8 exactly as §3 prescribes and re-walked the tree:

| state | importable | failing | of 583 |
|---|---|---|---|
| baseline (v0.115.0) | 318 | **265** | 45% broken |
| after pruning all 8 re-exports | 329 | **281** | still 48% broken |

The prune gains **11 modules** and then the failures *reshape* onto
`ModuleNotFoundError: No module named 'pricebook.core.day_count'` (280 modules). **Reverted** — the
tree is back at the 318/265 baseline while this is ruled.

## 3. Why: the live quarry imports parked modules DIRECTLY, not through the re-exports

| parked module | live quarry modules importing it directly |
|---|---|
| `discount_curve` | **223** |
| `day_count` | **221** |
| `serialisable` | 92 |
| `schedule` | 79 |
| `interpolation` | 52 |
| `calendar` | 50 |
| `solvers` | 39 |
| `bootstrap` · `data_registry` · `notional` · `serialization` · `currency` · `rate_index` · `global_solver` · `numerical_config` | 9 · 8 · 4 · 4 · 3 · 2 · 2 · 1 |

**294 live quarry modules import at least one parked module directly.** The re-exports were never the
load-bearing path; the parks removed content that **half the quarry depends on by direct import**.
No `__init__` edit can restore that, because there is no `__init__` in the failing path.

## 4. The tri-lemma this exposes

Three ratified commitments cannot all hold simultaneously:

1. **Parking physically relocates modules** (doc 13 §9; the Topic-0 park at v0.74.0 moved 13, the
   Topic-1 park at v0.98.0 moved 6).
2. **The quarry is read-only** — §4 protects its content; the ruling narrows this to *financial*
   content, which is the right narrowing but does not reach §3's problem.
3. **§7c's nightly quarry regression runs** — kept, not struck, by this ruling.

(1) and (3) are in direct conflict and have been since **v0.74.0** — so §7c has promised an
unachievable sweep for ~40 versions, not since the T1 close as NG-DEFER-QUARRYIMPORT first recorded.

## 5. Options, re-derived at the measured scope

| # | option | effect | cost / tension |
|---|---|---|---|
| A | **Park is a tracker state, not a physical move** — restore the 19 parked modules to their original paths; `parked/*/MANIFEST.md` keeps recording what crossed | quarry imports fully; §7c runs | reverses doc 13 §9's physical park *event*; "quarry empty = v1.0" becomes a tracker claim, not a directory fact |
| B | **Keep physical parking; scope §7c to the importable subset**, with a floor on its count (329 after the prune, or 318 today) | §7c runs, over a stated subset that **shrinks at every park** | weakens the guarantee the ruling just refused to weaken — but states the weakening instead of leaving it latent |
| C | **Parked modules remain importable from `parked/`** — the park rewrites the import path (a `parked/__init__` package per topic, or path injection) | quarry imports fully; physical park preserved | this is the ruling's rejected option 3 (shims), at 294-consumer scale rather than 8 |
| D | **Accept it; delete §7c's nightly quarry regression** | zero work | the ruling's rejected option 2 |

**My reading, for the ruling:** **A**. It is the only one that keeps all three commitments honest,
and the physical move is the youngest of the three — it was adopted for directory tidiness at a topic
close, whereas §7c is a verification guarantee and §4 is the migration's foundation. The park's
*meaning* (this module crossed; it is deletable) is fully carried by the tracker + MANIFEST, which is
already the single source for drawdown. A park would become: tick the tracker, record the MANIFEST
row, leave the file until the quarry retires whole at v1.0 — which is also what "done = quarry empty"
literally describes.

**If A is taken, the atomic-park clause from §3 is unnecessary** (nothing is orphaned because nothing
moves), and NG-DEFER-QUARRYIMPORT discharges by *restoring* 19 files rather than by pruning 8 lines.

## 6. What is unaffected

No ng code, no oracle, no pricing logic is involved; this is quarry packaging and the law that governs
it. 375 tests green at v0.115.0, drawdown 23 / 793 unchanged. The slice-B and floor-rule work stands.
