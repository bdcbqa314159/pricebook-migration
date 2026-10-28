# Spec — the consumer-narrow sweep (fork (b), the evidence that gates (c)/equity)

**Date:** 2026-10-27 · **By:** Cowork · **Answers:** thread 0045. **Baseline:** v0.129.0, drawdown 26/793.

## 0. `SwaptionPrice` slice — ruled items
- **AST-allowlist widening — ratified.** `SwaptionPrice` is a `CalibratedModel` capability protocol
  beside `ImpliedVol`/`SwaptionVol`; the no-law-switch law is "no branching on a *concrete model or vol
  law*", not "no `isinstance` against a protocol". Adding it to the allowlist is correct, not a
  loosening. The 381bp test now an equality (defect unwritable), `_pending_swap`/guard/`_S_IDENTITY_TOL`
  deleted, Black/SABR 32/32 byte-identical — clean.
- **The runtime-protocol-inheritance defect — noted, no action.** `_is_runtime_protocol` inherited from
  `CalibratedModel` made the runtime probe report a property the class did not itself have, while
  pyright was right — a production `TypeError`-at-first-dispatch fault the static gate caught. The
  lesson: *a structural-property probe can be fooled by inheritance; trust the static checker.* Worth
  carrying; not a ledger item on one instance.
- **`hull_white.py` retire-read (0 ticks, partial) — ratified.** Residual is the trinomial tree,
  consumer-backed (3 live quarry consumers → lattice slice), forward-linked. ng is *ahead* on the
  analytics it covers (Jamshidian, `zero_bond_option` — the quarry lacks both), so this is
  "analytics yes, numerics no", a clean partial.

## 1. What the sweep is, and what decides (c)
Bernardo ruled (b): before opening equity, **measure** whether B7's bar can move inside what is already
built. The sweep is that measurement — the first deliberate use of §4's new consumed-surface steering
rule. **Its output is the evidence that gates (c):**
- a **real backlog** of tick-now + cheap-partial modules ⇒ (b) is vindicated; harvest them, the bar
  moves inside what's built, and (c)/equity waits until that backlog is exhausted.
- **≈ 0** tickable within what's built ⇒ that is the measured evidence that only breadth moves the bar;
  **(c)/equity opens**, with §4's objection answered by measurement rather than overridden.

This is a **scoping pass**: Code classifies with evidence, Cowork rules the proposed ticks (spot-checks
the shed-lists, as with the swaption-cluster tail). No code; no tick lands until ruled.

## 2. Scope — targeted, not the whole quarry
Only modules whose **consumed surface could plausibly be superseded by what ng has built**:
rates-linear + curves, options/vol (swaption cube done), credit-vanilla (survival/CDS/CS01/rec01/JTD),
HW analytics, XVA analytic + MC exposure. Concretely, sweep the **neighbours of the already-crossed
modules** in: `curves/`, `fixed_income/` (the linear/vanilla family — deposit/FRA/OIS/swap/bond/leg
are done, so their siblings), `options/` (the vol/swaption family), `credit/` (the CDS/survival
family), `risk/` (xva and first-order risk), `models/` (HW/black/sabr neighbours).

**Explicitly OUT of scope** (known un-built — do not sweep, they are future verticals or deferred): the
exotic-credit families (CDO/CLN/CLO/bespoke/hybrid/credit_exotic), `structured/`, the other asset
classes (`equity/`, `fx/`, `commodity/`, inflation beyond ZCIS), the `mc_*` general framework, and the
lattice/tree numerics. The sweep tests "can we tick within the built surface", so un-built areas are
not its question.

## 3. Method — per candidate module
Per the §4 consumed-surface rule and the dead-evidence protocol:
1. List the module's **live (non-test) production importers** and, for each, **the names it actually
   uses** (bare-name grep over `quarry/` source; check kwargs, string/dict keys, `getattr`,
   `**kwargs`, serialisation — a name reachable dynamically counts).
2. Ask: **is every used name superseded by what ng provides today?** (curves, linear products,
   swaptions/cube/SABR, credit survival+CDS+CS01/rec01/JTD, HW analytics, CVA/netting/MC-exposure.)
3. Classify:
   - **TICK-now** — consumed surface fully superseded, residual empty (§4 deletable bar).
   - **PARTIAL-cheap** — superseded but for a *deferred capability* with a named consumer (a small
     follow-on, not a blocker).
   - **RESIDENT** — fat or un-built consumed surface; records *why* (which used names ng lacks).
   Zero-consumer / test-only names are `dead` (the usual evidence note).

## 4. Output + the decision
A table: module · live importers · used names · verdict (TICK/PARTIAL/RESIDENT) · evidence. Plus the
**headline counts**: how many TICK-now, how many PARTIAL-cheap, how many RESIDENT.
- TICK-now + PARTIAL-cheap a **real backlog** (enough for several bar-moving slices) → **(b) continues**;
  Cowork rules the ticks, Code lands them, and the bar moves. (c)/equity is revisited when the backlog
  is spent.
- TICK-now + PARTIAL-cheap **≈ 0** → the measured case for **(c)**; Cowork surfaces equity to Bernardo
  with the sweep as the evidence.

No arbitrary N — the enumerated set *is* the measurement, and its size speaks for itself; Cowork reads
it at ruling time. Do not tick during the sweep; propose with evidence.

## 5. Process
This is a read/analysis pass, not a slice — no version bump, no tracker edit (the proposals are
Cowork's to rule, then Code lands the ticked rows in a landing slice as with the swaption tail). Write
the findings to `handoffs/RETIRE_consumer_narrow_sweep.md`; point me at it. I rule the ticks and the
(c) decision on it.
