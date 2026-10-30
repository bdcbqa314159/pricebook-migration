# Ruling — the XVA/exposure-risk checkpoint (`CP_xva_reporting.md`)

**Date:** 2026-10-30 · **By:** Cowork · **Rules:** thread 0075. **Baseline:** v0.143.0, drawdown 32/793.
**Verdict: checkpoint RULED, accepted.** Next unit **held** — Bernardo ruled *revisit scope/pace first*
(thread question 0075); the scope deliberation is in the thread, and no slice opens until it is ruled.

## 1. Oracle audit — ACCEPTED
Run under doc-11's lead question ("what makes this red, and can that happen?"), all anchors rung-1 /
exact / structural, no rung-4 across two consecutive runs. **The `ρ→0`-exact-by-construction anchor is
the best oracle pattern the project has produced** — an identity arranged in the code (one driver
mapping, shared seed), not a tolerance between estimators, AST-guarded against the vacuous
`if rho==0` — and I ratify Code's framing that this is the shape to reach for whenever a new capability
claims to generalise an old one. The 5.14% discounting bug is correctly named the run's real finding.

## 2. The conventions register — RULED: start it now, as a doc (not law)
Code is right that the cross-module-convention clause (ruled last round) is **not sufficient alone** —
it says *compare the modules*, not *which conventions exist*, and the discounting bug went unseen for
two slices because "profiles are PV-dimensioned" was folkloric. Code held back at "one instance, not
law yet." I go one step further *because it is documentation, not an abstraction* (§6b's rule-of-two
governs software abstractions, never enumerating facts that already exist): **start
`docs/conventions_register.md` now.** It lists each cross-module convention + the oracle that guards it
(or "oracle owed"), so the clause has something to enumerate. Seed it with the ones already in force:
profiles are **PV-dimensioned / discounted-to-today** before the XVA integral (guard: the cross-builder
gate); **vol lives on the ACT/365F measure clock**; **profiles exclude historical flows** (invariant
6); the **forward** convention `F = S·e^{(r−q)T}`; **`cva` weights by `ΔQ`, `fva` by funding-spread·Δt**.
It stays a **living doc** (like the drawdown tracker), not a §4 clause — the *obligation to maintain
it* promotes to law on the second cross-module-convention bug. Starting now is cheap prevention of a
bug that already shipped, not speculative infra.

## 3. Challenge-me + debt — ratified
- **The vector twins stay concrete — no mechanism** (`norm_ppf_vec`/`black_vec`/`bond_vec`). Three
  instances would normally trigger a mechanism, but here §6b says the opposite: a decorator/dispatch
  over three 3-line functions, each already bound to its scalar by an exact elementwise test, is more
  indirection than the thing it abstracts. §3d is satisfied by the identity tests. Code's re-open
  trigger (a twin needing *more* than `np`-substitution) is the right one. This is the rare "three
  instances, still don't abstract" — ratified.
- **FTD-BCVA stays deferred** (needs a genuine joint-default law; WWR's analytic conditioning does not
  provide it) — honest.
- **`CorrelationKey` PSD check forward-linked** — the first multi-factor consumer owes it (a keyed set
  of pairwise correlations can be non-PSD where a matrix cannot). Correct to flag now.
- **Debt count corrected to 6 live** (the 12/11 of the last two checkpoints double-counted discharged
  headers). No new gate owed — the live count is a *reporting* figure, not a correctness invariant
  (the debt gate's invariant is suppressions == ledger, which held); the fix is to **list** live items,
  as this checkpoint now does, not grep headers. That Code caught it with this run's own lens ("a count
  nobody checks is a check that cannot fail") is the discipline working. Zero suppressions in `src/`
  stands.
- **Per-path scalar loop, third instance** — the clock gate catches it; "vectorise the closed form
  before the path loop" is a build habit, recorded as a default, not a new rule. Agreed.

## 4. Next unit — HELD for Bernardo's scope ruling
The honest three-instance reading is accepted: (b) 4-then-0, (c) 1, B7 1 — each run building complete,
oracled capability while the bar barely moves, because the quarry is fat and ng is thin *by design*, so
a vertical supersedes a minority of each file. At 4.0% after 31 slices this is scope-decision-grade
evidence, and §4 ("drawdown reports, never steers") forbids the number from picking the next unit.
Bernardo ruled *revisit scope/pace first*; the three next-unit options (path-dependent payoffs · heavy
B7 vertical · B8) are recorded in `CP_xva_reporting.md` §5 and wait on that ruling. **No slice opens
until the scope frame is ruled.**
