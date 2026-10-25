# Quarry census — a defensible denominator (2026-10-24, v0.110.0)

**What this is.** A one-off classification of **every** remaining quarry file, so the migration can be
stated as *"N migrated, M−N not, and here is the shape of the remainder"* instead of a bare drawdown
number. Built from a **real AST import graph** over `python/pricebook/**` and `python/tests/**`, not
from greps.

**What this is NOT** (§4): it is **reporting, never steering**, and **it grants no ticks**. A tick
still requires the just-in-time retire-read with §4's full evidence protocol — bare-name search across
source *and* tests, plus constructor kwargs, dict/string keys, `getattr`, `**kwargs` forwarding and
serialisation round-trips. §4 is explicit that cross-cutting work must never be planned from a
feature-diffed gap list; the buckets below say *where to look*, not *what to do*.

## 0. The denominator, confirmed

**774 resident + 19 parked = 793.** Matches the tracker's pinned convention (every `.py` in the
original quarry, `__init__.py` markers included). Resident LOC: **220,835**.

## 1. The headline

| | files | LOC | share |
|---|---|---|---|
| **MIGRATED (deletable)** — 19 physically parked + 3 ticked awaiting the batch park | **22** | — | **2.8%** |
| NOT migrated | 771 | ~219,800 | 97.2% |

The 2.8% is correct and stays the official bar. The rest of this document is about what the 771 are.

## 2. The 771, classified

| bucket | files | LOC | what it means |
|---|---|---|---|
| **E — to build (core spine areas)** | **376** | 101,262 | real capability ng needs: `fixed_income` 128 · `models` 88 · `options` 56 · `risk` 52 · `curves` 27 · `core` 12 · `pricing` 7 · `calibration` 4 · `market_data` 1 |
| **C — deferred → a named topic** | **307** | 101,375 | credit 92 · desks 49 · equity 31 · commodity 23 · structured 23 · FX 22 · regulatory 22 · crypto 15 · viz 13 · time-series 7 · data-spine 6 · PE 4 |
| **D — policy-shed (§7bb)** | **47** | 13,564 | `numerical/` + `statistics/` — scipy replaces these by ratified policy, not by port |
| **`__init__.py` markers** | **25** | 508 | package markers; they inflate the denominator and retire with their package |
| **B — dead candidates** | **9** | 1,618 | **zero** consumers anywhere — not even a test |
| **A — claimed but UNTICKED** | **7** | 1,449 | an ng module's `quarry:` header already claims them; candidate ticks |
| M — ticked, awaiting the batch park | 3 | 1,059 | `options/{sabr,capfloor,implied_vol}.py` |
| **total** | **774** | 220,835 | |

**A fairer "real" denominator.** Excluding what will never be ported as-is — policy-shed (47), `viz`
(13), dead (9) and the `__init__` markers (25) — the migration's genuine universe is about **680
files**, against which 22 ticked is **3.2%**.

## 3. The finding I did not expect — the remainder is leaf-shaped

Of the **683** files that represent real work (buckets E + C):

- **456 are leaves** — *no other quarry module imports them*;
- only **36 are load-bearing** (≥5 production importers).

That changes the character of what is left. The spine is built, and the remaining mass is
overwhelmingly **standalone feature modules**: they can be crossed, shed or deferred largely
independently, with no untangling, and the ordering constraint that dominated B0–B3 is mostly gone.
The 36 load-bearing modules **are** the remaining sequencing constraint, and they are a short list.

### The 36, head of the list (crossing these unblocks the most)

| prod importers | LOC | module | note |
|---|---|---|---|
| **107** | 234 | `models/black76.py` | also bucket **A** — partial cross (we took `black76_price` + `bachelier_price`; vega/theta remain) |
| 58 | 271 | `core/survival_curve.py` | B6 credit's foundation |
| 45 | 250 | `models/mc_migrate.py` | the MC cluster — **ng has no Monte Carlo engine at all** |
| 30 | 375 | `core/pricing_context.py` | **ng has no `PricingContext`**, though CLAUDE.md §3 ratifies the type |
| 26 | 477 | `models/mc_engine.py` | MC cluster |
| 22 | 137 | `core/trade.py` | bucket **A** — claimed by `shell/booking.py` + `shell/portfolio.py` |
| 21 | 809 | `models/mc_processes.py` | MC cluster |
| 19 | 1035 | `credit/cds.py` | B6 |
| 19 | 437 | `fixed_income/bond.py` | B2 gap (ng has no bond product) |
| 10 | 419 | `fixed_income/swap.py` | partially superseded by ng `products/swap.py` |
| 10 | 299 | `models/hull_white.py` | B4 gap |
| 9 | 783 | `risk/xva.py` | B7 |

Two structural gaps this makes explicit: **no MC engine** (four modules, 102 importers between them)
and **no `PricingContext`** (30 importers) — the latter is ratified vocabulary in CLAUDE.md §3 that
was never built, which is worth a deliberate decision rather than a silent absence.

## 4. Bucket A — the candidate ticks, with the ng module that claims each

The strongest query in the census: every ng module carries a `quarry:` provenance line and
`verify.py provenance` **enforces** it, so the ng tree is a machine-readable record of what has
crossed. It claims **43** distinct quarry paths; **10** are still resident; **3** of those are ticked.
The other **7 are claimed-but-unticked** — nobody ran their retire-read, because §4's flow is
just-in-time and these crossed as a side effect of other slices:

| quarry module | LOC | prod | tests | claimed by | first read |
|---|---|---|---|---|---|
| `pricing/market_data_provider.py` | 309 | **0** | 1 | `market/snapshot.py` | **cheapest** — no production consumer |
| `risk/greeks.py` | 79 | 2 | 3 | `risk/greeks.py` | cheap — small, 2 consumers |
| `core/fixings.py` | 253 | 2 | 3 | `shell/benefit.py` | already noted `reassigned→market-data` in the T1 MANIFEST |
| `fixed_income/fixed_leg.py` | 132 | 3 | 3 | `foundation/cashflow.py` | retired pre-replan under the old `/768` convention — needs re-ticking under `/793` |
| `options/vol_calibration.py` | 305 | 1 | 2 | `calibration/vol_strip.py` | likely partial (the strip crossed; the surface/cube build did not) |
| `core/trade.py` | 137 | 22 | 29 | `shell/booking.py`, `shell/portfolio.py` | likely partial — 22 consumers |
| `models/black76.py` | 234 | **107** | 114 | `models/black.py`, `bachelier.py`, `black_model.py` | certainly partial — the most load-bearing module in the quarry |

**Expected yield: 2–4 ticks** from one retire-read slice (the top four), which would move drawdown
**22 → 24-26 / 793** with little or no new code. The bottom three are partial crosses whose residual
must be built or forward-linked first.

## 5. Bucket B — the 9 dead candidates

Zero consumers anywhere, not even a test: `credit/loan_portfolio.py` (224) ·
`data/rate_database.py` (335) · `equity/dividend_strategies.py` (**0 LOC — an empty file**) ·
`equity/variance_swap_instrument.py` (112) · `fixed_income/esg_bonds.py` (235) ·
`models/composite_convention.py` (208) · `options/inflation_smile.py` (103) ·
`regulatory/repo_capital.py` (225) · `risk/repo_xva.py` (176).

**Candidates only.** §4's `dead` verdict needs the dynamic-reachability checks (kwargs, string keys,
`getattr`, serialisation) that an import graph cannot see — the retire-#1 false negative. The import
graph says "nothing imports it", which is necessary but not sufficient.

## 6. Limits of this census, stated

- **Import graph ≠ reachability.** Dynamic access is invisible to it. Every bucket-B entry and every
  `dead` call still needs the §4 protocol.
- **"Leaf" ≠ "unused".** 480 resident modules have no *quarry* consumer but do have test consumers:
  they are the library's public surface, exercised by tests and by notebooks/users outside the repo.
  Leaf means *independently crossable*, not *free to drop*.
- **Bucket C is assigned by directory**, cross-checked against the MANIFESTs' forward-links. It is a
  coarse "belongs to a topic not yet opened", not a per-file reading.
- **Bucket E is not a work plan.** It is "these areas are in the core spine and ng does not cover
  them yet". What actually crosses, and what is shed, is decided per module at retire time.
- **LOC is a size signal, not an effort estimate** — copy-ADAPT sheds debt, so ng counterparts are
  routinely a fraction of the quarry's line count (7,627 ng source lines currently supersede ~20,000
  quarry lines).

## 7. The statement this supports

> **22 of 793 quarry modules are migrated (deletable) — 2.8%, or 3.2% of the ~680 that will genuinely
> be ported.** Of the 771 remaining: **376** are core-spine capability still to build, **307** are
> deferred to named topics not yet opened (credit alone is 92), **47** are replaced by scipy under
> §7bb policy, **25** are package markers, **9** are dead candidates and **7** are already claimed by
> ng code and merely await their retire-read. The B0, B1 and B3 blocks are complete; B2, B4, B5, B7
> and B8 are partial; B6 is untouched. **456 of the 683 real-work files are dependency leaves**, so
> the remainder is parallelisable; the sequencing constraint is a list of **36** load-bearing modules,
> headed by `models/black76.py` (107 importers), the Monte Carlo cluster (102 between four modules)
> and `core/pricing_context.py` (30).

## 8. What I would do next with it

1. **A retire-read slice over bucket A's top four** (`market_data_provider`, `risk/greeks`,
   `core/fixings`, `fixed_income/fixed_leg`) — mostly evidence work, 2–4 ticks, little code.
2. **Rule the two structural absences** — the MC engine and `PricingContext`. Both are load-bearing in
   the quarry and both are *decisions*, not oversights, once named.
3. **Keep retiring in the leaf-rich areas** once the swaption cluster unblocks; order matters far less
   than the drawdown bar implies, which is itself a useful thing to know.
