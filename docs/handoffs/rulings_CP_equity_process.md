# Ruling — the equity + process-framework checkpoint (`CP_equity_process.md`)

**Date:** 2026-10-30 · **By:** Cowork · **Rules:** thread 0067. **Baseline:** v0.139.0, drawdown 31/793.
**Verdict: checkpoint RULED, accepted.** Two points ruled specifically; next slice = XVA-reporting.

## 1. Oracle audit — ACCEPTED
Every slice anchored rung-1 on a closed form, no rung-4 self-consistency anywhere, and c1-as-anchor
paid off for c2 and c3 exactly as the arc intended. The honest log of the three powerless checks (all
Code's, all caught) is the point, not a blemish — see §2.

## 2. Point 1 — "a check that cannot fail" is the named defect class; RULED into doc-11
Agreed, and it is the most valuable thing this run produced. Three checks this run **could not have
failed** (27 `PricingFailure`s; 40 zeros; the flat-curve fixture where a clock-advance and an expiry
bump agree exactly), and the through-line — *green never reveals a powerless check* — is the same one
behind audit #10, `--layer 0`, `provenance`, and the two-R. The five rules the project has accreted all
guard this one class: structural-oracle, floor-on-population, resolve-don't-just-exist, variance-floor,
aggregate-consumes-members.

**Ruling:** the per-checkpoint oracle-quality audit's **first question becomes "for each oracle and
gate: what makes it red, and *can that happen*?"** — a check with no reachable path to red (a degenerate
baseline, a flat fixture, a truncated population, an existence-not-resolution probe, an unfollowed
aggregate) is powerless, and green over it is not evidence. Land this as doc-11's lead review lens,
naming the class and the five rules as its guards. Code's claim that a powerless check is now more
common than a wrong number — among the project's *meta*-findings — matches the record; the audit should
spend its attention there first.

## 3. Point 2 — the honest bar reading; §4 already answers the steering question
Accepted and important: 31/793 = 3.9%; the (b) harvest's four ticks came from *measurement* and are
spent; this run's one tick was the theta *build*, not the equity asset class. Code is right that
**opening another asset class is not supported as a drawdown move** — greenfield builds capability
before it retires anything.

But the framing resolves cleanly against the law, so this is not a new dilemma:
- **§4: "drawdown is reporting, never steering," and the domain build order drives.** So "should we
  open FX/commodity to move the bar?" is the wrong question — we do not steer by drawdown. **No; do not
  open another asset class now.**
- **Equity was build-order-correct, not a breadth-for-drawdown bet that failed.** It was opened as the
  rule-of-two *second process consumer* needed to justify `StateProcess` and unblock the generic MC
  framework — B7's machinery. It delivered exactly that. Few ticks is the *expected* shape of a
  greenfield vertical, not a miss.
- **Where the bar moves next is B7's own resident mass, now that the machinery exists:** `risk/xva.py`
  (783 lines, 9 importers, partially crossed) retires as the XVA family lands — XVA-reporting (now),
  then DVA (slice 3), then FVA/MVA/KVA/collateral/WWR. That is the build order, and the bar is the
  *report* of following it. So the next ticks are earned by finishing B7, not by breadth.

**Surfaced to Bernardo (his call, not steering):** the pace is genuinely slow (3.9%, and the earlier
"~370 slices for credit alone" projection), and that is a *scope* question only he owns — is
full-migration-at-this-fidelity still the frame, or does he want to revisit scope? I am **not**
reopening the ratified full-migration doctrine on my own; I am flagging the accumulating evidence so he
can weigh it. Nothing blocks on it — XVA-reporting is next regardless.

## 4. Challenge-me — ratified
1. **`StateProcess` marginal-not-path** — right; the joint matrix is `compute`'s internal mechanism,
   not the consumed surface, so the deferral cost nothing (my own 0066 correction confirms it).
2. **`black_vec` a bound twin** — **one atom, ratified.** `test_black_vec_IS_black_elementwise` binds
   it to `black` at `rtol=0.0, atol=0.0` across the grid — a *bit*-identity, stronger than
   `weighted_annuity ≡ N·rpv01`'s tolerance. A twin guaranteed bit-identical by a test is two call
   shapes of one atom, not a second dialect (§3d). The alternative (array-capable `norm_cdf`) risks
   tree-wide byte-identity — worse. Keep it; keep the identity test as the guarantee.
3. **Greeks by bump** — accepted cost, one differentiation mechanism, the priced-is-the-marked. (Equity
   rho needing no code is the dividend.)
4. **`currency` a field** — already ratified (make-it-unwritable).
5. **Theta coupon precondition deferred** — already ruled; the guard lands with its first possible
   violator (`NG-DEFER-THETA-COUPON-GUARD`).

## 5. Smell + debt — ACCEPTED
12 live items, all deferred scope with triggers, none buying a green oracle; `NG-WATCH-CLOCK` closed
by promotion to the gate. **`exposure.py` split ratified at its self-set trigger** — the *next*
exposure builder splits the module (four rates builders + equity + a `singledispatch` table is the
ceiling). `NG-DEFER-THETA-COUPON-GUARD` is the weakest guarantee in the tree (a documented
precondition) but trigger-timed right; watch it.

## 6. Next
**XVA-reporting** — the marginal `XvaReport` (ENE · PFE profile · peak EE · effective EPE · DVA · FVA,
all from the marginals ng samples), which retires `mc_exposure.py`, **31 → 32**. A `fields-exempt`
`XvaReport` per §3b (N independent results). Then B7 continues per the build order (DVA, then
FVA/MVA/KVA/collateral, and WWR/joint-paths when its consumer arrives). Next checkpoint `CP_xva_reporting`
as Code named.
