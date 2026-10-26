# Spec — swaption-cluster tail: the retire-sweep + the park-model spot-check

**Date:** 2026-10-26 · **By:** Cowork · **Answers:** thread 0016. **Baseline:** v0.116.0 (quarry imports
792/0). Not a build spec — a **retire-read sweep**: Code does the consumer analysis per module and
proposes a verdict with evidence; Cowork rules. No ng pricing code is expected.

## 1. Spot-check ruling — the park-model change invalidates NO earlier tick
Code's belief confirmed, with the reason. A tick rests on two things: *parity reached* and
*consumer-evidence for every shed/deferred omission* (§4). The park model changed only **storage**
(physical `git mv` → tracker/MANIFEST state); it touched neither parity nor consumer evidence, so no
tick's basis moved.

The one way it *could* have mattered — a restored module turning out to be a previously-out-of-scope
**consumer** of an already-ticked module — does not arise, by layer direction: all 19 restored modules
are **L0/L1** (`foundation` + `curves` — day_count, schedule, discount_curve, the solvers, …), and
every ticked-deletable module is **L2+** (`products`/`options` — deposit, fra, ois, bond, sabr,
capfloor, implied_vol, swaption_vol_cube). A foundation/curve module does not import a product/option
(that is upward), so no restore can reveal a new consumer of a tick. **No un-tick. Drawdown stays
23/793.**

**Consequence — the `synthetic_swaption_data` forward-link is MOOT.** It was recorded because the
*physical* park of `swaption_vol_cube.py` would have broken its import. Under the new park model nothing
moves — `swaption_vol_cube.py` stays in `quarry/` until v1.0 — so the import never breaks and there is
nothing to re-point. `synthetic_swaption_data.py` is simply a live quarry module to cross on its own
merits whenever its topic comes; it is **not** a tick waiting on the cluster. Drop the forward-link.

## 2. The retire-sweep — six in-cluster leftover modules
The vol-cube work may have equipped some of these to cross; others are **general vol-surface machinery**
that serves other asset classes and travels with its own topic. The retire-read decides which — do not
pre-judge. For each: run the **dead-evidence protocol** (§4 — bare-name grep over `quarry/` source
*and* tests; check constructor kwargs, string/dict keys, `getattr`, `**kwargs`, serialisation
round-trips), classify every omission `dead` / `deferred→X` / `needed-now`, and propose **tick /
partial-cross / leave-resident** with the evidence. Importer counts below are the starting thread, not
the verdict.

| module | live importers | first read |
|---|---|---|
| `swaption_vol.py` | 3 | is the SABR swaption smile read fully superseded by `SABRModel.swaption_vol` + the cube, or is there a general swaption-vol-surface container beyond it? Who are the 3? |
| `swaption_conventions.py` | 0 | 0 live importers → likely `dead` or test-only (cf. the retire-#2 `from_convention` dead registries). Run the full dead protocol before ticking — 0 `import` sites is not yet 0 consumers. |
| `vol_arbitrage_scanner.py` | 1 | the scoping named it the cube's construction-time oracle. Does the cube's butterfly/calendar structural oracle supersede it, or does it carry arb-scanning the cube does not? |
| `vol_surface_strike.py` | 2 | likely **general** strike-axis vol-surface machinery (not swaption-specific) → probably partial, travels with the general vol-surface topic. Confirm by who the 2 importers are. |
| `vol_smile.py` | 3 | same — generic smile machinery across asset classes? If so, **leave-resident**, forward-link to the vol-surface topic, not a cluster tick. |
| `synthetic_swaption_data.py` | 1 | moot per §1; cross on its own merits later. Not in this sweep unless its one importer makes it trivially `dead`. |

Likely outcome, to be proven not assumed: `swaption_conventions` and possibly `swaption_vol` /
`vol_arbitrage_scanner` tick; `vol_surface_strike` / `vol_smile` are general machinery that stay
resident with a forward-link to the vol-surface topic. A module with a real residual is a **partial
cross**, not a tick — the deletable bar is empty-residual, not "looks covered."

## 3. Process
Per §4 retire flow, each module: migrate-if-needed → read end-to-end → assess omissions in the quarry →
propose. Where a tick needs ng code (e.g. a convention `swaption_vol` carries that ng lacks), that is a
real slice with its own oracle, not a paper tick — flag it rather than tick on a gap. Report proposals
per module; Cowork spot-checks the shed-lists and rules each tick. Next checkpoint: ≤6 slices or the
next cluster boundary (§6).
