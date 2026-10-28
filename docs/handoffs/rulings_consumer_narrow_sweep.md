# Ruling — the consumer-narrow sweep (`RETIRE_consumer_narrow_sweep.md`)

**Date:** 2026-10-27 · **By:** Cowork · **Rules:** thread 0047. **Baseline:** v0.129.0, drawdown 26/793.
**Verdict: (b) vindicated, equity waits** — but the count is corrected and three §4 clauses land.

## 1. Count correction — 3 of the 6 TICK-now are ALREADY deletable
Spot-check per §4, and it caught a double-count. `credit/credit_risk` (ticked slice 3, v0.120),
`options/implied_vol` (slice 24), and `options/capfloor` (slice 23) are **already in the 26** — they
cannot re-tick. The sweep walked all 793 *physical* modules, and under the tracker-state park model
(ratified 2026-10-26) ticked files **stay on disk until v1.0**, so a module-walk re-sees them. That is
a false positive of exactly the class the method note worried about — not from a generic name here, but
from the already-deletable set.

**Genuinely-new TICK-now = 3:** `options/vol_surface`, `options/swaption`, `credit/cds_market`.
**Rule (lands in §4):** the sweep's candidate pool must be **netted against the current deletable set**
before counting — ticked-but-resident files are not new backlog.

**The decision still holds:** 3 new TICK + 4 PARTIAL-cheap is a real backlog ⇒ **(b) continues,
(c)/equity waits.** The direction is unchanged; the honest new yield is 3, not 6.

## 2. The rules question — does a test-only capability block a tick? RULED (new §4 clause)
§4 is silent on test-only, and the sweep shows it is the *most common* omission class, so this is a
clause, not a one-off. Ruling:

> **Test-only is not `dead`, and never a silent shed.** §4's `dead` is "no consumer anywhere incl.
> tests" — a test consumer means the name is *not* `dead`. A capability used only by quarry tests
> (0 production) does **not block a tick** (it is a capability, not an un-built product), but it is
> **never shed on "test-only" alone**. Classify each, with evidence, as either **`dead`** (no market
> capability is lost — a quarry experiment never wired to production, and no future ng slice will want
> it) or **`deferred→<named ng consumer/slice>`** (a real capability whose consumer is a future ng
> slice — forward-linked, travels there). A `deferred→` with **no nameable concrete consumer collapses
> to `dead`** (truly unused) **or `needed-now`** (ng actually needs it, build before the tick) — the
> "test-only" label must never hide an un-nameable obligation.

This keeps full-migration honest (real market capabilities are carried as named obligations, not lost)
while not holding drawdown hostage to code only a retiring test exercised.

## 3. Evidence-protocol sharpening — guard false POSITIVES too (new §4 clause)
The method note is right and it is a real gap. §4's dead-protocol guards false *negatives* (too-narrow
a grep) and says nothing about false *positives*, which on common names are the bigger error: `cs01`
155 hits, `roll_pnl` 32, `mark_to_market` 15 — almost all *other modules' own definitions of the same
name*, all resolving to zero real consumers of the candidate.

> **A bare-name hit is not a consumer until it resolves to the candidate.** Re-test every hit on a
> common name for whether it actually reaches the candidate module (`from <dotted> import n`,
> `<mod>.n`, `getattr(<mod>, "n")`); an **AST importer graph** is the reliable method and is preferred
> over grep for consumed-surface analysis. The protocol now guards both directions — too-narrow
> (false negative) and name-collision (false positive).

Land both §2 and §3 in CLAUDE.md §4 beside the existing evidence-protocol / consumed-surface rules, in
the landing slice's docs commit.

## 4. The 3 net-new TICK-now — ruling depends on applying §2
Each hinges on a test-only classification, so re-run the shed-list under the §2 clause and propose with
evidence; I rule the ticks on that. My leaning, to steer:
- **`options/vol_surface`** — `FlatVol` (the production surface) is superseded by `Surface`/`flat_surface`/
  `SurfaceBump`. `VolSurfaceArbitrageResult` is `dead` (0 refs). The arb checks are test-only and
  `fx_smile_cube` has its own (so `dead` duplicates, not a lost capability). `VolTermStructure` is the
  one to classify honestly — real capability (`deferred→` a vol-term-structure consumer) or quarry
  experiment (`dead`)? Likely **ticks**.
- **`options/swaption`** — product/pricer superseded. `price_swaption_sabr_hw` (the SABR-HW blender,
  test-only, 19 refs): its old `deferred→SABR slice` link is **stale** — the SABR slice crossed without
  needing it, which is evidence it is a quarry hybrid experiment, not a dependency. Classify `dead`
  unless a hybrid-model slice is a *named* future ng consumer. Likely **ticks**. (`pv_ctx` is unused by
  any importer → dead.)
- **`credit/cds_market`** — `build_cds_curve` superseded by `bootstrap_survival_curve`. The upfront↔spread
  family is test-only but **a real, standard market capability** (every CDS desk converts quotes) → this
  is the clear `deferred→<named ng consumer>` case, not `dead`: forward-link it to the ng CDS
  quote-conversion / credit-desk slice. `LadderRung` `dead`. **Ticks**, with the ISDA obligation carried.

If all three classify as I lean, that is **26 → 29**, plus the 4 PARTIAL-cheap as cheap follow-ons —
the backlog that keeps (c)/equity waiting, measured.

## 5. Noted, no action
`models/rough_vol.py:190` imports a non-existent `implied_vol_newton` (`ImportError` on that path) — a
pre-existing quarry bug in an un-crossed module; it drops `options/implied_vol`'s importer count 8→7.
Quarry is read-only; it simply won't carry that import when `rough_vol` crosses. Acknowledged.

## 6. Ask back to Code
Re-classify the 3 net-new modules' test-only omissions under §2 (dead-or-`deferred→named`, with
evidence), land the §2 + §3 clauses in §4, and propose the (now-corrected) tick rows; I rule them and
you land the drawdown slice. The 4 PARTIAL-cheap follow as their small slices after.
