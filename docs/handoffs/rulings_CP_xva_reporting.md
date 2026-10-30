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

## 4. Next unit — scope RULED (Bernardo, 2026-10-30): full migration stands (Path 1)
Bernardo revisited the scope/pace frame and **reaffirmed full migration unchanged** — `done = quarry
empty = v1.0`, every module crosses, drawdown the progress bar. **No CLAUDE.md amendment: the §4/§6/§7
stance stands exactly as written.** Recorded here so the question is not re-litigated without knowing
it was deliberated and settled: the three-instance "next tick needs a heavy vertical" evidence was put
in front of him in full, and the ruling is to press on with the whole migration.

With the frame settled, the next unit returns to a **build-order** call (§4: the domain build order
drives, not drawdown, not preference). Of the three options in `CP_xva_reporting.md` §5, the
build-order-earliest unfilled position is the **B5 non-linear tail — path-dependent payoffs** (Asian /
Bermudan / American / callable / LSM), ahead of B7's capital/repo residual and B8. It is also the most
unblocking (the largest single un-built cluster, across every asset class) and reuses the MC machinery.
**Ruled: path-dependent payoffs next**; first slice the **Asian option** (geometric closed-form anchor),
scoped in `spec_asian_pathdependent.md`. The `Payoff` block (§3d's named-and-deferred `StateProcess` +
`Payoff`) lands at its **second** consumer (Bermudan/LSM), not the Asian first slice (§6b rule of two).
