# Artifact #11 — Checkpoint & Review Cadence (Ratified)

**Status:** Ratified. Extends the handoff protocol (#08). Makes the build → Cowork
review a **planned rhythm**, not an ad-hoc "I felt it was necessary." Governs when Claude Code
stops and what the review must interrogate.

**Stance: full migration, corrected.** Every quarry module crosses — but *realigned* to the
better design and clarity as it does (copy-ADAPT, shed debt). Nothing is archived-instead-of-
migrated; "done = quarry empty = v1.0" is taken literally. Time is not the constraint; quality
and legibility are.

---

## 1. When the build stops (checkpoint triggers)

Claude Code stops and writes a checkpoint report at the **first** of:

- **Cadence ceiling:** every **≤ 6 slices** (versions) since the last checkpoint. Never run
  more than 6 unreviewed. (The L5 run went ~18 and let L6 drift — that is the anti-pattern.)
- **Capability-cluster boundary:** a coherent unit completes — an asset class, a risk/greek
  family, a layer vertical, a calibration family. Stop even if < 6 slices.

**Plus mandatory *immediate* stops (any one, mid-cluster):**
- Any **design drift** beyond the ratified guardrails / a contract or measure question.
- Any **new cross-cutting abstraction or vocabulary type** introduced (rule-of-two moment).
- Any **debt logged** (`OPEN.md` gains an entry) or **suppression** added.
- An **oracle weaker than closed-form/cross-check** is the best available for a slice.
- A **quarry entry resists clean realignment** (can't be adapted to the spine without a smell).

The build **names its next checkpoint** at the end of every report (predicted boundary +
trigger), so the next stop is planned one hop ahead.

## 2. What the checkpoint report must carry (extends #08 §format)

Beyond the #08 sections (slices landed, ledger deltas, oracles, ready-for-next), every report
adds the four mandatory review inputs:

1. **Oracle-quality audit** — for each slice, state the oracle and classify it: closed-form >
   external cross-check (QuantLib/ISDA) > self-consistency (reprice-to-par) > trusted mark.
   Flag any slice whose oracle is *only* self-consistency — that is the "no real oracle" risk.
   **For any slice whose content is a structure, confirm an oracle tests the structure (count /
   finer-grid / atom-parity), not only a scalar; for any filtered grid, confirm a survivor floor**
   (the structural-oracle rule, CLAUDE.md §6, ratified 2026-10-24).
2. **Quarry-drawdown reconciliation** — modules crossed this checkpoint + cumulative:
   `<N> / 768 migrated (<x>%)`, and which quarry subpackages advanced. Keeps v1.0 countable.
3. **Design choices to challenge** — an explicit *"challenge me"* list: the non-obvious calls
   made since last checkpoint, each with its rationale, surfaced for Cowork to push back on
   *before* they harden. (This is where the build answers for what it chose.)
4. **Smell + debt scan** — new smells (oversized signatures caught by `PLR0913`, primitive
   obsession, god-objects, duplication), suppressions, shims, TODOs — each with the build's
   proposed disposition.
5. **Spine-conformance audit** *(added after the `foundation/black.py` drift)* — every module
   **created or moved** since the last checkpoint, justified against its **layer's definition**
   (not merely against the acyclic check, which cannot see semantic misplacement). Explicitly
   confirm: **L0 holds no finance** (strikes/vols/payoffs/discounting), analytic blocks of a
   dynamics sit at **L3** (A4.3), products are pure data at L2, pricing composition at L4, state
   only at L6. `verify.py layers` mechanises the L0 rule; the rest is reviewed.
6. **Deferred-ledger sweep** *(added after the foundation-audit closure, V3)* — re-read **every**
   `AC-*` / `NG-*` entry in `OPEN.md`'s audit-closure ledger and ask of each: *has its trigger
   fired?* If so, it is now scoped work, not a deferral — promote it. **No automated gate watches
   these** (they are deliberately outside the `verify.py debt` balance — a deferred capability
   suppresses nothing), so this human re-read is the only thing that catches them. Six triggers are
   **condition-driven, not topic-driven** (AC-T4.7/8/9/11/17/18 — a future calendar/consumer, an
   external weekend-rule change, error-message quality, a fourth consumer): no roadmap progress will
   ever fire them, so they need this calendar-based sweep, not a trigger. A ledgered item a
   checkpoint cannot account for is a forgotten item with paperwork (CLAUDE.md §5).

## 3. The Cowork review ritual (what happens here on receipt)

Per checkpoint, Cowork runs the same pass, in order:
1. **Reconcile** — apply ledger deltas; update the drawdown number.
2. **Challenge** — interrogate the §3 choices list; push back, ratify, or send back.
3. **Smell/debt hunt** — rule each item: fix-now / debt-ledger / accept-with-rationale.
4. **Oracle audit** — any self-consistency-only oracle gets a real reference value demanded
   or a re-open trigger logged.
5. **Reshape** — if a pattern is emerging (a recurring value object, a boundary), amend the
   spine/vocabulary now, before more slices build on the un-named pattern.
6. **Retune & release** — issue the rulings as a `rulings_<id>.md` hand-back; the build resumes
   to the named next checkpoint.

No forward slice begins until the checkpoint is ruled.

---

## 4. Forward checkpoint map (planned ahead)

Indicative, not binding — each report re-confirms the next. Ordered by the current design
priorities (A6: L6 before more depth), then the systematic quarry drawdown.

| # | Cluster | Trigger | Focus of the Cowork review |
|---|---|---|---|
| **CP-1** | measure-consistency oracle + first L6 vertical (Trade/Book/benefit table) + `xva_report` | cluster (A6) | A3 realized-vs-mark proven end-to-end; the binding measure oracle |
| **CP-2** | general-curve (bootstrapped) HW; lift the flat-curve ceiling | ≤6 or cluster | modelling honesty under the XVA stack |
| **CP-3** | breadth: commodity (+ inflation) on the A5 keyed snapshot | cluster | confirm "keys not fields" pays off; no new greeks |
| **CP-4** | quarry drawdown — `fixed_income` (130) systematic crossing | ≤6 rolling | copy-ADAPT realignment quality; oracle coverage |
| **CP-5** | quarry drawdown — `credit` (93) + `models` (90) | ≤6 rolling | de-duplication vs quarry sprawl |
| **CP-n** | … `options`, `structured`, `desks`, `regulatory`, `crypto`, `viz`, `ts` … | ≤6 rolling | until 793/793 crossed → **v1.0** |

The long tail (CP-4 onward) is the real bulk: full migration means each quarry subpackage is
mined to empty, realigned, oracle-gated. Drawdown % is the honest progress bar.

---

## 5. Relationship to the other artifacts
- Extends **#08** (report format) and **#06** (a checkpoint is not a release; releases are
  per-slice).
- Feeds **#05/#09** — smells/debt found here land in `OPEN.md`; oracle audit enforces the
  green-oracle gate retroactively.
- The **spine amendments** (A1–A6…) are the output of the "reshape" step — this cadence is how
  they keep getting made deliberately instead of discovered late.

---

## Oracle-quality audit — added line (2026-10-26 — ruling: `handoffs/rulings_floor_rule.md`)

The oracle-quality audit (first of the four review inputs) gains:

> **Confirm every gate asserts a floor on what it collected or resolved, not merely that it ran
> green.** For each gate, name the population it examined and the floor it held that population to.
> A gate that reports "ok" without a count or a dereference is a proxy, and a proxy that can pass
> while its target is empty, truncated, or dangling is not a gate (CLAUDE.md §6, the floor rule).

Precedent for why this is a standing checkpoint question rather than a one-off fix: three instances
of the same shape reached ratification unnoticed — audit #10, `--layer 0`, `provenance`.

---

## Oracle-quality audit — second added line (2026-10-26 — ruling: `handoffs/rulings_CP_credit_vertical.md`)

A **third structural face**, beside the count and the finer-grid/parity cross-check:

> **Single-source / bump consistency.** For any market input a model both *fits* and *prices* with,
> **bumping it at its snapshot home must preserve reprice-to-par.** A second copy of that input fails
> the check by construction: the bump moves the snapshot's copy, the pricer reads the other one, and
> par breaks. Ask it of every input that appears in both a calibration and a mark.

**Why it is a standing question and not a one-off fix.** The law already said *"if risk bumps it, it
lives in the snapshot"* and *market is reached through the model* — and recovery still ended up in two
homes (the L2 product and the bootstrap spec) for two slices, where a curve fitted at R=0.40 and a CDS
marked at R=0.30 priced a **par** quote to ≈96bp of notional, silently. **No existing gate shape could
see it:** it is not a truncated population (so not a count) and not a coarse grid (so not a
finer-grid check) — "the same quantity in two places" has no floor to assert. It was caught by a human
reading a checkpoint report, which is exactly the kind of catch a gate should be making instead.

Promotion to CLAUDE.md §6 on a second instance (the floor rule's own precedent: audit #10 stood alone
until `--layer 0` and `provenance` made it three).

## Oracle-quality audit — the powerless-check lens (2026-10-30 — rulings: `handoffs/rulings_CP_equity_process.md`, thread 0072)

**The audit's FIRST question is now:** *for each oracle and each gate — what makes it red, and can
that actually happen?* "A check that cannot fail" is this project's named defect class, and by the
equity/process checkpoint it was measurably **more common than wrong numbers**. Green never reveals
a powerless check, so power is **asserted, not observed**.

The five structural rules all guard this one class, and each came from an instance of it:

| rule | the powerlessness it guards |
|---|---|
| structural-oracle (§6) | a self-consistency oracle that reprices what it just built |
| floor-on-population (§6) | a check that examined an empty or truncated set |
| resolve-don't-just-exist (§6) | a presence check that never dereferenced what it named |
| **floor-on-variance** (§4) | a *populated* baseline with no discriminating power (all-equal, all-zero, all-`PricingFailure`) |
| **aggregate-consumes-members** (§4) | a consumed-surface read that stopped at the bound name |

**The cross-module case (ruled 2026-10-30, thread 0072).** *A convention shared across modules
needs a cross-module oracle.* §3d guarantees a shared **atom** structurally — by composition, so it
cannot be violated — but a shared **convention** has no structural guarantee at all. A per-module
oracle that is internally self-consistent is therefore **blind** to a convention mismatch, and every
module can be individually correct while the system is wrong. So at least one oracle must **compare
the modules**.

*Precedent:* exposure profiles must be discounted to today, because `cva` weights by `ΔQ` and
discounts nothing. Three builders did; the equity one did not. **Equity CVA was 5.14% too large for
two slices**, and every oracle passed — the martingale oracle asserted `EE = V₀/df`, which is
precisely what an undiscounted profile gives, so it validated the builder against itself. Nothing
compared the builders to each other. The guard is now
`test_every_exposure_profile_is_PV_DIMENSIONED_the_convention_cva_requires`, with the rates builder
as the control that was always right. Promote to §4 law on a second instance.

**A third shape, recorded for the pattern rather than ruled:** a test can be powerless because its
*fixture* cannot discriminate, even with correct data and a reachable red. On a **flat** curve a
clock-advance and an expiry bump agree to the last bit (`df(T)/df(Δ) = e^{−r(T−Δ)} = df(T−Δ)`), so
the test separating them passed whichever construction had been implemented. Fixed by sloping the
curve; the degeneracy is asserted alongside so the reason cannot rot.
