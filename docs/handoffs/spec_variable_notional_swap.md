# Spec — `fixed_income/swap` variable notional: a build-and-tick

**Date:** 2026-10-28 · **By:** Cowork · **Answers:** thread 0051. **Baseline:** v0.131.0, drawdown 29/793.

## 0. Housekeeping ratified
The untracked-docs catch is a real process risk, not a nit: my "state → the artifact" writes only
become durable when Code commits them (Code owns git, §README), so a spec or ruling I write can sit one
`git clean` from gone until a landing picks it up. I verified `git status` — **all my handoff docs and
the thread are tracked now**, nothing at risk. Your fix (check `git status` for stray handoff docs at
each landing) is the right mitigation and I rely on it; I cannot commit from my side.

## 1. What this slice is
`fixed_income/swap.py`'s consumed surface is superseded **except** variable notional — so building that
one capability supersedes the surface and **ticks swap.py without waiting on the desks** (the desks,
when they cross, use ng's variable-notional). A build-and-tick: 29 → 30.

The gap, with your asymmetry: the **readers** `notional_schedule` + `average_notional` are consumed
(`desks/api_desk`, `desks/swap_desk`); the **constructors** `amortising`/`accreting`/`roller_coaster`
have **0 refs anywhere incl. tests → `dead`**, so they are *not* built. ng builds the
schedule-carrying swap + its annuity and the two readers — the sugar is shed. `from_convention` stays
the standing conventions deferral (already forward-linked), not this slice.

## 2. The atom — `weighted_annuity`, and the §3d identity
Add **`weighted_annuity(schedule, notionals, day_count, curve) = Σ Nᵢ·τᵢ·df(tᵢ)`** to
`building_blocks` beside `rpv01`. It is `rpv01` generalised with a per-period notional, so the
**load-bearing identity is `weighted_annuity(flat N) ≡ N·rpv01` to 1e-12** — the same shape as
`risky_annuity→rpv01` at λ=0. That identity is both the §3d guarantee (one annuity atom, the
variable-N case composing the same `df`/`τ`) and the **byte-identical guard** for every existing
constant-notional swap. This also **discharges the standing forward-link** "on crossing `swap.py`:
expose `annuity`/`weighted_annuity` as a building block" — `rpv01` already did the `annuity` half;
`weighted_annuity` is the other.

## 3. The product shape — your call within the rule
Variable notional = a **per-period notional schedule** aligned to the accrual periods; constant-N is
the degenerate flat schedule. Prefer **generalising the existing shape** (the leg/swap carries a
notional schedule, flat = today's scalar) over a parallel `VariableNotionalSwap`, so the engine prices
one thing by composing `weighted_annuity` — *unless* generalising forces a wide, byte-identical-risky
change across every `VanillaSwap` site, in which case a schedule-carrying sibling is the lesser evil.
§3b: if a `(schedule, notionals)` pair recurs, bundle it into a `NotionalSchedule` value object (rule
of two); ≤5 fields. **No `isinstance` in the engine** — the variable-N swap prices by the same
`weighted_annuity` composition, flat or not; that is the whole point of the atom.

## 4. Oracle
1. **Within tolerance (load-bearing) — NOT bit-identical. [Cowork correction 2026-10-28.]** My first
   wording made *both* "one `weighted_annuity` composition, flat or not" and "byte-identical constant-N
   swaps" load-bearing; they conflict — `Σ(Nᵢ·τᵢ·df) ≠ N·Σ(τᵢ·df)` in floating point (re-association).
   The single composition is §3d-correct and wins; a flat-only bit-preserving path would re-derive the
   annuity (the smell §3d forbids). The requirement is **`weighted_annuity(flat) ≡ N·rpv01` to 1e-12**
   (§7c: tolerance is the hard rule; byte-identity is scoped to same-process statelessness, which is
   unaffected). Expect last-digit re-association on some existing swaps (~machine-eps); no test moves.
2. **Strip decomposition (structural, §6 — not a scalar):** an amortising swap **equals a strip of
   constant-notional vanilla swaps** with the step notionals (Nᵢ−Nᵢ₊₁ on tenor-i swaps, or the
   equivalent nested decomposition) — assert the variable-N PV equals the sum of that strip, each leg
   priced by the *existing* engine. This tests the composition, not a re-summation of itself.
3. **Readers:** `notional_schedule` returns the per-period schedule; `average_notional` the
   notional-weighted (or time-weighted — match the quarry's definition, cite it) average. A flat swap's
   schedule is N at every period and its average is N.

## 5. Tick + forward-links
Retire-read `fixed_income/swap.py`: consumed surface (`pv`/`par_rate`/`annuity`/`dv01`/
`cashflow_schedule` already superseded + variable-notional readers now) → superseded;
`amortising`/`accreting`/`roller_coaster` → `dead` (evidenced, 0/0); `from_convention` →
`deferred→conventions` (standing row). Residual empty → **TICK, 29 → 30 / 793.** Propose with evidence;
I spot-check and rule, you land.

## 6. Process (§8)
Branch `slice/<NN>-variable-notional-swap`. audit → align (`weighted_annuity`; the schedule-carrying
shape) → test (the `weighted_annuity≡N·rpv01` identity + the strip decomposition + the readers, RED
first) → feat → docs → retire-read. Report the build + the retire-read; then the remaining partials
(`floating_leg`, `cds`) wait on their un-crossed consumers, so after swap I expect the next unit is
either the next consumer-narrow target or the fork revisited — your/Bernardo's call at that point.
