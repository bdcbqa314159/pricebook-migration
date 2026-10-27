# CLAUDE.md — Pricebook build guardrails

These are **guardrails, not suggestions.** They are the ratified output of the design
phase (`docs/01`–`05`). When a change conflicts with this file, this file wins.
The design *rationale* lives in `docs/`; this is the enforceable subset.

The build proceeds by **migration, one thin slice at a time, bottom-up**, starting with
Slice 0. Do not rewrite; do not chase feature parity; do not price outside the engine.

---

## 0. The one idea

**Functional core, imperative shell.** Pricing is a pure function
`price(product, model, numerics) → result` — no state. The **model is calibrated to a
`MarketSnapshot` and carries it**; market is upstream of the model
(`market → calibrate → model → price`), never a separate peer input to the engine. Linear
products use a thin `DiscountingModel` that wraps the curve. Everything that persists (a
booked trade, its life, the database) lives in a thin shell around the core and only calls
into it. The core never remembers; the shell never computes.

---

## 1. The spine (layers — dependencies point DOWN only, never up)

```
L6  LIFECYCLE / BOOKING / PORTFOLIO   (stateful shell: trade=book of products, benefit table, P&L, desks)
L5  RISK & CAPITAL                    (greeks · XVA · RWA — on the engine + Priceable protocol)
L4  ENGINES                           (the stateless heart: bind product+model → mark = future PV + accrued)
L3  MODELS + CALIBRATION              (dynamics; calibrated to a MarketSnapshot, carry it)
L2  PRODUCTS                          (pure-data product descriptions: legs, cashflows, payoffs)
L1  MARKET DATA                       (immutable MarketSnapshot · quotes · fixings · curves · vols)
L0  FOUNDATION                        (time & conventions · value types · finance-free numerics)
     DATA SPINE (side)                (SQLite→DuckDB ingestion → feeds L1; never imported by core)
```

**The law:** a lower layer must never import a higher one. This is enforced by the
per-commit acyclic check (Tarjan SCC on the import graph) — keep it green. If a change
needs an upward import, the design is wrong; fix the layering, not the check.

**Layer conformance is SEMANTIC, not just acyclic.** The acyclic check proves dependency
*direction*; it cannot tell you a module sits in the *wrong layer*. A module must match its
layer's **definition** — notably **L0 is finance-free** (no strikes, vols, payoffs, call/put,
discounting in code) and a closed-form analytic block of a dynamics belongs at **L3 models**
(A4.3), not L0. Enforced by `verify.py layers` and reviewed at every checkpoint (5th review
input). *Precedent: `foundation/black.py` (Black-76) passed `acyclic` while violating L0's
finance-free definition — semantic drift the dependency check cannot see.*

**Three structural fixes to honour as entries migrate:**
- `risk` lands at **L5** (above the engine), depends only on the engine + a `Priceable`
  protocol — **no `isinstance`-on-instrument ladders.**
- Calibration lands as a **unified front at L3** over per-family solvers.
- The engine registry lands **inside L4** (no leaky top-level `registry.py`).
- `pe` lands in the **L6 shell** (not L0); `Cashflow` lands at **L0** (not inside an asset class).

---

## 2. The stateless-engine contract (L4) — five invariants

```python
result = engine.price(instrument, model, numerics)  # -> PricingResult
```
The **model carries the `MarketSnapshot` it was calibrated to** (`model.market`); the
engine reads curves/vols through the model, never from a separate `market` argument. For
linear products the model is a `DiscountingModel` wrapping the curve. Market is never a
peer input — this makes model/market mismatch structurally impossible.

1. **Referential transparency** — identical inputs ⇒ identical output, always.
2. **No ambient state** — no thread-locals, globals, or clock reads; "today" is
   `model.market.valuation_date`.
3. **No mutation** — `instrument`, `model` (and the `MarketSnapshot` it carries) are
   frozen; never mutated in place.
4. **Failure is a value** — return `PricingFailure`, never raise-and-hope or emit silent
   `NaN`.
5. **Config is explicit** — all reproducibility knobs (seeds, MC paths, PDE grid, tol)
   arrive in an explicit numerical-config value, decomposed by method family (≤5 fields
   each); never a hidden default. *(The concrete type lands with the first engine that reads
   it — Phase 4 deleted the speculative `NumericalConfig` with its guessed knob names; the
   principle stands, the type returns shaped by a real consumer.)*
6. **Valuation-date-aware** — cashflows on or before `valuation_date` are historical:
   **excluded from PV** (handled by the L6 shell via fixings/settlement), never discounted
   with a non-positive `t`. Future cashflows discount from `valuation_date`. Clean/dirty
   and accrued interest are explicit, not incidental.

**Products are pure data.** Frozen dataclasses that *describe* (legs, cashflows); they
do **not** price themselves. No `pv()`/`pv_ctx()` on products — pricing lives in L4.

**Trade vs mark vs realized.** A **trade** (L6) holds a *collection of products* + a start
date + lifecycle. At the valuation date its economics split three ways: **realized P&L**
(cashflows that already paid — the **benefit table**, actual cash, recorded in the L6 shell,
never discounted), **accrued** (earned-but-unpaid slice of the current period — part of the
*mark*), and **future PV** (remaining flows, discounted). The **engine computes the mark**
(future PV + accrued); the **shell remembers realized P&L**. Total economics = realized +
mark; dirty = clean + accrued.

---

## 3. Vocabulary (the stable types every layer speaks — ratified)

- **Time:** `Date` (stdlib), `DayCountConvention`+`year_fraction`, `Calendar`,
  `Frequency`/`Schedule`, `CompoundingMethod`, `RateIndex`. `Tenor` stays a string +
  helpers; `Rate` stays a float.
- **Money:** `Money(amount, Currency)` **at boundaries** (cashflows, PVs); plain floats
  inside hot numerical loops. Currency-mixing must be a type error where it matters.
- **Instrument atom:** `Cashflow` (at L0), `Leg` = ordered cashflows + convention.
- **Market (L1):** `Quote`/`QuoteId`/`QuoteKind`, immutable `MarketSnapshot` (carries the
  `valuation_date`). **All market data is first-class in the snapshot** (rule: *if risk bumps
  it, it lives in the snapshot*), shaped as **closed shapes × open keys** (doc 19 §2,
  superseding A5): a finite field set — `curves` (term structures) · `surfaces` · `scalars` ·
  `series` · `schedules` — each an open map whose keys carry the asset dimension
  (currency · collateral · index · entity · underlying · pair). A new asset class adds *keys,
  not fields*; greeks are generic (`bump_spot`/`vol_vega`…), not per-asset. Curves are
  reached through typed `CurveSet` accessors and a **`CurveHandle`** protocol (`df`,
  `survival`) — depend on the capability, not the concrete curve; **never mutated in place.**
  A curve/model may expose closed-form **building blocks** (`df`, `RPV01`, `B(t,T)`,
  zero-bond-option) reused upward; the **L4 engine composes them to price the product** —
  "pricing lives in L4" governs *product* pricing, not every scalar of math.
- **Models (L3):** a model is a **`CalibratedModel` bound to the `MarketSnapshot`** it was
  calibrated to (`model.market`). `DiscountingModel` wraps a curve for linear products. The
  engine depends on the model; market is reached through it, never passed alongside.
- **Time semantics:** valuation partitions cashflows into historical (`date ≤
  valuation_date`, excluded from PV) and future (discounted from `valuation_date`).
  Clean vs dirty price and accrued interest are explicit value concepts, not by-products.
- **Engine I/O:** an explicit numerical-config value (see invariant 5 — deferred to its first
  engine); `PricingResult` is a **decomposition** — `pv` · `accrued` · `clean` ·
  `basis: Currency | None`, not a scalar; `PricingFailure`. *(Phase 4 deleted the speculative
  `sensitivities`/`cashflow_breakdown`/`diagnostics` fields — risk output returns with L5,
  shaped by it; cashflow breakdown with the L4 engine that produces it.)* The economy a model
  is built on = **curves + fixings**, reached through the **`FixingSource`** protocol
  (`FixingHistory` is its trivial implementation); fixings are first-class in the
  `MarketSnapshot`, needed to resolve current-period amounts.
- **Identity/state (Product → Trade → Book):** `Product` = the priceable atom (**frozen**,
  L2, needs a model). `Trade` (**frozen** description, L6) holds ≥1 products + a start date;
  `BookedTrade` = trade + lifecycle events + its **benefit table** (realized-cash P&L).
  `Book` = collection of trades (L6). `PricingContext` is **frozen** and kept as the
  engine's built-market-state input (reached through `model.market`).

---

## 3b. Signature discipline

- **Max 5 arguments** per function/method in `src/pricebook/**` (ruff `PLR0913`,
  `max-args=5`; the quarry `quarry/pricebook/**` is exempt).
- A signature over the limit is **un-bundled vocabulary**, never a reason to raise the
  limit. The fix is ALWAYS to group cohesive parameters into a frozen value object, or
  fold them into an existing ratified type: market state → `MarketSnapshot`;
  reproducibility knobs → the numerical-config value (deferred to its first engine);
  `amount`+`currency` → `Money`; ICMA coupon anchors → `CouponPeriod`;
  calendar/convention/eom → `RollRule`; schedule terms → `ScheduleTerms`.
- New grouping types obey the rule of two (≥2 real consumers) — no speculative wrappers,
  and no 9-field "god dataclass" that just relocates the smell.
- **Never suppress.** No `# noqa: PLR0913`. A genuinely irreducible mathematical
  signature (a closed-form formula) is the sole exception and goes in `OPEN.md` with a
  rationale and a re-open trigger.
- **The limit also applies to dataclass fields** (products & value types), because a frozen
  product with 8 loose primitives is the same un-bundled-vocabulary smell as an 8-arg
  function — `PLR0913` just can't see it. A `products/` or `foundation/` value dataclass has
  **≤5 fields**; bundle primitives into ratified value objects (`Money` for amount+currency,
  `Accrual` for start+end+day_count, `ScheduleTerms`, …). Enforced by **`verify.py fields`**.
  Legitimately-wide types carry an explicit `# fields-exempt: <reason>` marker — an *explicit*
  exemption, never silent tolerance. **The exemption is for genuinely irreducible aggregates and
  output records** (`MarketSnapshot` — the closed-shapes×open-keys shape, doc 19 §2; `XvaReport` — N independent results).
  **It is NOT for configs.** A config groups naturally by method family and must decompose —
  e.g. a numerical config as `(monte_carlo, lattice, integration, solver)`, each sub-config ≤5.
  If you are reaching for the marker on a config, you have not decomposed it yet.

## 3c. Onboarding a new asset class — where do its "fundamentals" go?

The recurring question. The L0 membership test alone does not settle it; use this procedure for each
candidate:

```
1. Is it VALUATION?                          → L3/L4. Never L0.
2. Is it market state that RISK BUMPS?       → L1 snapshot (A4.2)
3. Is it CONTRACT DESCRIPTION?               → L2 product data
4. Is it STATE / LIFECYCLE?                  → L6 shell
5. Is it an IDENTITY or CONVENTION spoken
   by ≥2 layers?                             → L0
6. Otherwise                                 → its natural layer, NOT L0
```

**Corollary: L0 grows only by identity/convention siblings, never by asset-specific machinery.**
A new asset should add roughly *one* L0 object — its identity, as a sibling under the general
index/underlying concept. Wanting to add more is a smell; stop and rule it.

*Worked example (credit) — the SHAPE credit will follow, not a type that exists yet:* a reference-
entity identity → **L0** (survival curves are keyed by it, CDS references it, credit risk bumps by it
— multi-layer identity). Hazard/survival curve and recovery → **L1** (risk bumps them). Credit-event
definitions, restructuring clause, seniority → **L2** product data. CDS IMM rolls → already L0.
*(Phase 4 deleted the speculative `ReferenceEntity` sibling; per this rule it returns as L0 when the
credit topic builds it, shaped by a real consumer — the `Underlying` protocol and `AssetClass` enum
it slots into were kept.)*

## 3d. Building-block discipline — shared primitives across the spine

The §3 vocabulary is not only a set of TYPES; it is a set of **atoms and relationships**, and the
relationships must survive the whole pricing spine — **market data → model → calibration → engine.**
Ratified:

**An atom is defined ONCE and every stage COMPOSES it — no stage gets its own dialect.** The linear
atoms are `df(t)`, `forward(index, start, end)`, `RPV01 = Σ τᵢ·df(tᵢ)`, `B(t,T)`, `zero_bond_option`.
Market data (L1) *exposes* them; the model (L3) *carries or derives* them under the same signature and
semantics (`DiscountingModel` passes `df` through; a dynamics model derives it from parameters);
calibration *composes* them to **fit** (`residual = par_rate − quote`); the engine (L4) *composes the
same ones* to **price**. Four layers, one language.

**The invariant is the RELATIONSHIP, not the function call.** `calibrate-to-par` and
`price-to-zero-NPV` are the *same fact* only because the identities among the atoms hold —
`RPV01 = Σ τ·df`, par-float telescoping, `forward` consistent with `df`. Composition is how the
identity is *guaranteed*: an identity never re-derived cannot be broken.

**Worked example — the annuity (`RPV01`).** The calibrator forms `par_rate = (df₀ − dfₙ)/RPV01`; the
engine forms `PV = N·(par_rate − K)·RPV01` (K the swap's fixed coupon) — the *same* `par_rate`
and `RPV01` the calibrator just used. If each rolls its own annuity loop and they differ in
*any* detail — accrual vs payment dates, ACT/360 vs 30/360, log-df vs zero-rate interpolation — the
calibrator solves so the swap is par while the engine prices that same swap to a **non-zero** NPV:
calibrates perfectly, prices wrong, and the par-swap reprice test is blind to it (par swaps telescope).
**The fix is not a test; it is one `rpv01(schedule, curve)` both layers call.** The engine MUST NOT
hand-roll a discount/annuity loop the curve or calibrator already exposes.

**Exception-count is a design-health gauge (5th-review / checkpoint).** An exception is countable: an
`isinstance`/type-switch on a product or model *inside* the engine or calibrator; a `# special-case`
that changes the composition; a residual that cannot be formed from the exposed capabilities; an atom
**re-derived** in one stage instead of shared. One exception may be tolerable; a **cluster** is a
stop-and-rule signal:

- **it recurs and carries a reusable relationship ⇒ a building block was missing.** Name it; build it
  when its second consumer arrives (§6b rule of two). *Exotic pricing needs a `StateProcess`+`Payoff`
  block; the exceptions clustered at the exotic boundary, so the block was named and deferred — the
  gauge worked.*
- **it is a one-off patch bearing no reusable relationship ⇒ the design is faulty** — a layer is
  forcing stages to diverge. Fix the layering, never add the patch.

**An exception is NOT a building block.** A block is *named, reusable, shared*; an exception is an
*unnamed special-case*. Promote exceptions to blocks when they recur, eliminate them when they signal
bad layering — **never let them accumulate**; accumulated exceptions ARE the un-maintainable design.
This is §3b's "a signature over the limit is un-bundled vocabulary" generalised from one signature to
the whole spine, and a sibling to §1's no-`isinstance` law.

---

## 4. Migration rules (quarry → new tree)

- **Quarry is read-only.** The old tree is never edited or deleted. Done = quarry empty.
- **A park is a tracker/MANIFEST state, NOT a physical move** (ratified 2026-10-26; ruling
  `docs/handoffs/rulings_quarry_park_model.md`). A crossed module is ticked *deletable* in
  `quarry_reconciliation.md` and recorded on its MANIFEST row; **its file stays in `quarry/`** until
  the whole quarry is deleted at v1.0. The quarry therefore stays **importable** throughout, and
  §7c's nightly quarry regression runs against it. *"Quarry empty = v1.0"* means every module ticked
  deletable and the tree cleared **once, at the end** — the physical emptying moves from per-park to
  once; drawdown (/793) is unchanged.
  *Precedent: the Topic-0 (v0.74.0) and Topic-1 (v0.98.0) physical parks `git mv`'d 19 modules out of
  the live package, which broke `import pricebook` for **265 of 583** quarry modules — 294 live modules
  import those 19 **directly**, so no `__init__` re-export fix could reach it. §7c promised a nightly
  quarry regression that could not run for ~40 versions. Both parks are reverted; a CI gate
  (`verify.py quarry`) now walks the tree and holds a floor on the importable count.*
- **"Crossed" = quarry-deletable, not concept-adapted.** A quarry module counts as migrated
  only when its ng counterpart reaches *realigned parity* and the quarry module could be
  deleted — a simplified skeleton (e.g. flat-curve HW standing in for the general model) is a
  *partial* cross with a recorded **parity gap**, not a cross. Drawdown (`deletable / <current
  quarry total>`, the total per the tracker's stated convention) is the honest progress bar; it
  is refreshed at every checkpoint
  (`docs/handoffs/quarry_reconciliation.md`).
- **Copy-ADAPT, never copy-paste.** Every crossing conforms to a layer, speaks the
  vocabulary, moves behaviour into the engine, or sheds debt. A byte-for-byte copy is a
  **failed** migration.
- **Mine the quarry for CONTENT, never for STRUCTURE.** The quarry answers *what is true*
  (conventions, formulas, edge cases, market practice — it is a working library, that is the
  material). The design answers *how it is shaped* (layer, types, purity, signatures). **A quarry
  file's organisation carries no authority in ng.** Reading a module and inheriting its shape is how
  the old design re-enters through the back door. Per-file transformation gate:
  `docs/13_topic_migration_and_parking.md` §5.3. If a file cannot be expressed in the ratified
  shape, that is an **immediate-stop trigger** — the design is wrong or incomplete and Cowork rules;
  it is never resolved by bending ng to the quarry's shape.
- **Green-oracle gate — nothing crosses grey.** No entry lands until a red/green oracle
  proves it against a known value: closed form > QuantLib/ISDA cross-check >
  self-consistency (reprice to par / zero NPV) > trusted mark. "Runs and looks right" is
  not an oracle.
- **Structural-oracle rule (ratified 2026-10-24).** A self-consistency oracle cannot see a wrong
  *decomposition*, only a wrong number: it reprices the very object it just built, so a flat input
  strips flat whatever the structure's shape. Therefore, **where a slice's content IS a structure — a
  ladder, a grid, a schedule, a decomposition — at least one oracle must test the structure itself**,
  not a scalar off it: a *count* (a 5Y cap strips 19 caplet pillars, not 4), a *finer-grid*
  cross-check, or *parity composed from the atoms alone*. Second clause — **the floor rule, and it binds the
  verification apparatus itself** (amended 2026-10-26; ruling:
  `docs/handoffs/rulings_floor_rule.md`). A gate's green is evidence only if the gate also asserts a
  floor on *what it examined*; green over an unknown, empty, or truncated population is not green.
  Two faces: **floor-on-population** — any check that filters, collects, or iterates a set asserts a
  minimum count of survivors (a slice's oracle grid *and* CI's test collection — a count, not
  "green"); and **resolve-don't-just-exist** — a presence check must dereference what it names (a
  provenance header must *resolve to a file*, not merely exist). *(Precedent — three instances of one
  shape: audit #10, a flat cap-vol curve and a reprice-what-you-stripped oracle blind to the
  caplet-grid≠quote-grid bug for three slices, caught by a count; `--layer 0`, CI silently gating 177
  of 366 tests for six slices while every report read "gates green"; `provenance`, four lines asserted
  present while 17 of 45 `quarry:` paths dangled, two wrong since the day they were written. Each
  asserted existence or greenness and no floor.)*
- **Domain build order (supersedes demand-driven).** Migration proceeds **block by block in
  financial-engineering dependency order** — B0 conventions → B1 curves → B2 linear products →
  B3 curve construction → B4 models → B5 non-linear+engines → B6 credit → B7 risk/XVA →
  B8 portfolio/lifecycle. **A block completes before the next opens.** **Drawdown is reporting,
  never steering.** Domain architecture (currencies, curve framework, xccy) is settled **up
  front** — §6b's rule-of-two governs *software abstractions*, never *domain decisions*.
  Full detail: `docs/12_domain_build_order.md`.
- **Provenance.** Each landed entry records: quarry path, the paper/book/model it
  implements, and its oracle. (Educational constraint — keep it legible.)
- **Deletable-bar rigor.** A parity slice ends by **reading its quarry counterpart end-to-end**
  and listing the residual gap in `quarry_reconciliation.md`. A module ticks to *deletable*
  (drawdown +1) **only when the genuine residual is empty** — never asserted from "looks covered."
- **"Deletable" = SUPERSEDE, not clone.** ng is deliberately minimal (copy-ADAPT sheds debt, §6b
  forbids speculative fields), so ng ≠ quarry by design. A quarry feature ng omits is *shed debt*,
  not residual — **but only with evidence.** Every omission is classified in the module's `shed:`
  list by grepping the quarry for consumers:
  - **`dead`** — no consumer anywhere in the quarry (incl. its tests) ⇒ genuinely shed, no obligation.
  - **`deferred→X`** — consumed by quarry module(s) X not yet crossed ⇒ shed now; the feature
    **travels with X's crossing slice** (a named future trigger, never a vague "later").
  - **`needed-now`** — an ng module already requires it ⇒ **not shed**; a genuine residual that must
    be built before the tick.
  A module ticks deletable only when the genuine residual is empty **and** every omission is
  classified with evidence. Cowork spot-checks `shed:` calls at each checkpoint and may **un-tick**
  (drawdown −1); the quarry is git-tracked, so a reversal is cheap and nothing is lost.
- **The consumed surface decides the tick — and steers the targeting** (promoted 2026-10-27, §6
  second-instance convention; ruling `docs/handoffs/rulings_CP_credit_vertical.md` → thread 0042). A
  module ticks when **the names its importers actually use** are superseded, never when the file
  "looks mostly covered"; re-derive by asking *which names the importers use*, never by
  feature-diffing the file. Twice a tick expectation was overturned exactly here —
  `options/vol_arbitrage_scanner.py` (ng had no arb machinery at all, and its consumer was live) and
  `models/mc_exposure.py` (consumed as a **generic process framework** over a `BlackScholesProcess`,
  not as rates netting; `ExposureResult` had 0 consumers anywhere). **Steer by
  consumed-surface-narrowness:** target modules whose importers use a narrow surface; a fat file with
  a wide consumed surface does not tick until that surface is superseded or its consumers cross.
- **A residual needs consumer evidence too (symmetric to `dead`).** A quarry feature ng lacks is a
  *genuine* residual only if **something consumes it** — same evidence protocol as below.
  Feature-diffing a quarry module against its ng counterpart **overstates** residuals: a "gap" that
  nothing uses is shed debt, not a blocker. Re-derive a module's residual by **consumer analysis at
  retire time**; never plan cross-cutting work from a feature-diffed gap list. (Retire #2: "conventions"
  looked like a shared residual across the rate vanillas, but the quarry `Deposit` class had **zero
  production instantiations** — the real residual was serialisation. Building conventions would have
  been speculative infra with no ng consumer.)
- **Evidence protocol for a `dead` claim** (a narrow grep produced a false negative on retire #1):
  search the **bare name** across `python/` source *and* tests — never just `\.name` — and explicitly
  check **constructor kwargs**, **dict/string keys**, `getattr`, `**kwargs` forwarding, and
  **serialisation round-trips**. Anything reachable dynamically is **not** `dead`. The shed-list
  records *how* it was verified (patterns + hit counts), not just the verdict.
- **A TEST-ONLY omission never blocks a tick, but is never silently shed either** (ruled 2026-10-27;
  ruling `docs/handoffs/rulings_consumer_narrow_sweep.md`). Test-only is **not `dead`** — a quarry test
  is a consumer by the definition above — and it is not a verdict: it is a **prompt to classify**. Each
  test-only name resolves to `dead` (no market capability lost, evidenced) or
  `deferred→<named ng consumer/slice>` (a real capability, forward-linked on that row). A `deferred→`
  with no nameable consumer collapses to `dead` or `needed-now`. *(The sweep that forced this found
  test-only to be the single most common omission class, not an edge case — §4 defined `dead` and
  `deferred→X` and was silent on the majority case.)*
- **The evidence protocol guards false POSITIVES as well as false negatives.** The bare-name grep above
  catches too-narrow searches; on a **common name it over-reports instead**, because sibling modules
  define the same name. A bare-name hit is **not a consumer until it resolves to the candidate module**
  (`from <dotted> import n`, `<mod>.n`, `getattr(<mod>, "n")`). The instrument is an **AST importer
  graph**, not grep: it sees multi-line parenthesised imports and attributes each name to the module it
  actually comes from. *(Precedent: the consumer-narrow sweep measured `cs01` at 155 quarry hits,
  `roll_pnl` at 32 — every one of them another module's own definition; all resolved to zero against the
  candidate. Ungarded, ~5 modules would have been recorded RESIDENT on borrowed evidence.)*
- **Net the candidate pool against the deletable set before counting** (same ruling). A park is a
  tracker state, not a `git mv` (above), so **every ticked module is still physically on disk** and any
  tree-walking sweep re-discovers it. Asserting the netting is the §6 floor rule applied to a sweep's
  own population: reconcile the deletable list to the tracker's stated count *before* classifying.
  *(Precedent: the consumer-narrow sweep reported 6 TICK-now and 4 PARTIAL-cheap; 4 of those 10 were
  already deletable — netting gave the honest 3 and 3.)*
- **Forward-link every `deferred→X`.** The obligation is written on **X's row** in
  `quarry_reconciliation.md` ("on crossing: add …"), not only on the retired module's entry — the
  retired entry is never re-read; X's row is read the moment X is picked up.
- **A `deferred` capability must never *block* a tick.** If a module is otherwise deletable, tick it
  and forward-link the deferred capability. Building a deferred capability early is allowed as an
  explicit *policy* (e.g. serialisation added per-product while already inside the module, to avoid a
  mass retrofit later) — but it is never re-labelled a "residual" to justify itself, and drawdown is
  never held hostage to it.
- **Deferred *capability* ≠ deferred *product*.** A method/analytic on a product ng **has** (bond's
  yield analytics, swap's `par_rate`) may be deferred and the module ticks. **A whole instrument ng
  has never built (e.g. `InflationLinkedBond`) BLOCKS the tick** — ticking would delete the definition
  of a product that never migrated, and under full-migration `quarry empty = v1.0` must mean every
  product actually crossed. Either build it or hold the module a partial cross.
- **Retire flow (per module, just-in-time):** migrate → read the old module end-to-end → assess each
  omitted feature's status *in the quarry* (a fact, not a taste judgment) → **then** tick. The
  assessment is the evidence for the tick, so it completes before it.
- **Cross-cutting work is justified by what it retires.** Shared capabilities (conventions,
  multi-curve, serialisation…) may be built when residuals cluster, but **every such slice must
  tick ≥1 quarry module to deletable** — infrastructure is never built speculatively ahead of the
  module that needs it. Breadth (new asset classes) waits while drawdown is stuck at 0.

Per-entry checklist: `AUDIT → ALIGN → ORACLE → DEPS → PROVEN → PROVENANCE → MARK`.

---

## 5. Debt rule

**No debt is silenced silently.** Every suppressed warning, `# type: ignore`, empty
`except`, skipped test, shim, or load-bearing TODO goes into the debt ledger (`OPEN.md`)
with a rationale and a re-open trigger — or it does not exist.

- Debt may **never** buy a green oracle. A slice that can't go green honestly is not done.
- Debt is allowed only for *deferred scope*, never for *hidden wrongness*.
- **Invariant (CI-checkable):** suppressions − ledger entries = 0.

---

## 6. Slice discipline

- One **vertical** cut through only the layers it needs. Nothing speculative.
- **Ships with a named oracle**, green, before it counts as done.
- Small enough to check against its oracle **in one pass** — if it isn't, split it.

**Slice 0 (first build task):** a single fixed cashflow discounted on a flat curve, priced
end-to-end L0→L6 through the stateless engine. Oracle: `PV = notional·exp(−r·t)` to
<1e-12; analytic vs finite-difference DV01 to <1e-6; repricing is byte-identical
(statelessness). See `docs/04_slice_plan.md`.

**Checkpoint cadence (hard stop — planned, not ad-hoc):** stop and write a checkpoint report
at the **first** of: **≤6 slices** since the last checkpoint, **or** a capability-cluster
boundary (asset class / risk family / layer vertical / calibration family) — **whichever comes
first**. Plus **immediate** stops on: any design drift or contract/measure question; any new
cross-cutting abstraction/vocabulary type; any debt logged or suppression added; any slice whose
best oracle is only self-consistency; any quarry entry that resists clean realignment. Every
report carries the four review inputs — **oracle-quality audit, quarry-drawdown reconciliation
(`N / <tracker total>`, single source: `docs/handoffs/quarry_reconciliation.md`), a
"challenge-me" list of design choices, and a smell+debt scan** — plus the **named
next checkpoint**. Do not begin the next slice until the checkpoint is ruled. Full detail:
`docs/11_checkpoint_and_review_cadence.md` (extends `08_handoff_protocol.md`).

**Migration stance:** full migration, corrected. Every quarry module crosses, *realigned* to
this design (copy-ADAPT, shed debt) — nothing archived-instead-of-migrated. `done = quarry
empty = v1.0`, taken literally; drawdown % is the progress bar.

---

## 6b. Simplicity — solve the real problem, not the imagined one

- Build for the problem the slice actually presents. **Nothing speculative.**
- **No abstraction without two present, real consumers.** Introduce it when the second
  arrives, not in anticipation (rule of two). One caller ⇒ write it concrete.
- **No hooks, config knobs, or extension points for hypothetical futures.** Every
  abstraction is complete and exercised by real code, or it does not exist. No half-built
  generality "for later" — a partial abstraction is debt, finished within the slice or
  not introduced.
- **Depth of abstraction is a cost, not a virtue.** Prefer concrete, legible code over
  configurable cleverness. The library is also a teaching text: legible beats clever.
- If a design adds a layer of indirection, it must justify it with a present need, not a
  possible one. When in doubt, do the simpler thing and let the second real use force the
  generalisation.

## 7. Release & versioning

- **New tree starts at `0.0.0`.** `0.x` = migration in progress; **`1.0.0` is reached
  exactly when the quarry is empty.** True semver after 1.0: MAJOR = public-API or
  serialisation-schema break, MINOR = new capability, PATCH = fix/numerical correction.
  `pricebook.__version__` is the single source of truth.
- **`RELEASE_NOTES.md` is frozen** (quarry record — read-only, never appended). The new
  tree logs to **`CHANGELOG.md`** (Keep-a-Changelog format).
- **Every landed slice = one version bump + one `CHANGELOG.md` entry**, carrying the same
  provenance the ledger requires (what changed, oracle, quarry path). CI asserts
  `__version__` matches the top changelog entry.

---

## 7b. Verification & audit (one tool, staged)

- The new tree's entire audit setup is a **single `verify.py`** — `acyclic`,
  `tests --layer N`, `debt`, `provenance`, `version`, `all`. No audit framework; a flat
  script of small functions. The quarry's `L*_DEPS.md`, regenerated `ARCHITECTURE.md`,
  and `AUDIT_PLAN.md` are **not carried forward** (frozen quarry history).
- **Staged tests:** each slice runs only its layer tier (`verify.py tests --layer <L>`),
  not the full suite. Merge gate = layer tier green + `acyclic` + `debt` + `version`.
  Full sweep runs nightly / at layer checkpoints.
- **Provenance header enforced:** every `src/pricebook/` module carries four lines —
  `quarry:` path, `source:` paper/book, `oracle:`, `slice:` — or `verify.py provenance`
  fails CI.
- **Pre-commit stays surgical** (fast auto-fixes only); heavy checks live in CI.

## 7bb. Numerics dependencies (ratified)

- **Python may use `numpy` and `scipy` freely.** This tree is the *understanding-and-correctness*
  environment, not the performance target; scipy's numerics are battle-tested and precise, and the
  library's teaching value is in the **finance** (curve construction, measure, XVA), not in Brent's
  internals.
- **The C++ port hand-rolls its own** (fit and performance), oracled against Python with
  **tolerance, not bit-equality** — same rule as cross-OS (§7c).
- **Thin adapters, not scattered calls.** `foundation/{interpolation,solvers,distributions}.py`
  wrap scipy behind our own API + provenance headers. One place to pin behaviour, and **one swap
  point for the C++ port** — do not call scipy directly from engines/models.
- **Own what scipy lacks or what is finance-specific** — e.g. **Hagan–West monotone-convex**
  interpolation (absent from scipy *and* from both trees).
- **No duplicates.** Adopting scipy *replaces* the hand-rolled `bisect_root`/`nelder_mead`/
  `norm_ppf`; it never sits beside them.
- **Two safeguards:** (a) oracles must test the **finance** (reprice-to-par, closed-form PV), never
  scipy's numerics — that is what keeps oracle ownership; (b) **pin `numpy`/`scipy` versions in CI**
  — a scipy upgrade can shift convergence, so the version is part of the reproducibility contract.
- **Debugging technique (not a permanent parallel build):** when a number looks wrong, write a
  minimal independent hand-rolled implementation to cross-check it.

## 7c. CI & cross-platform (Linux + Windows)

- **CI matrix:** `ubuntu-latest` + `windows-latest`, Python `3.12`, one workflow file.
  Per-PR runs `verify.py acyclic/debt/version/provenance` + the slice's layer tier on
  both OSes; merge gate = green on both. Full sweep + quarry regression nightly — **achievable
  again as of 2026-10-26**: the quarry imports (792 modules), asserted per-commit by
  `verify.py quarry` against a committed floor.
- **Tolerance-based oracles are a HARD rule.** `exp/log/pow/trig` differ 1–2 ULP between
  glibc and the MSVC runtime, so oracles assert tolerances (closed-form `1e-12`; MC/PDE
  their convergence tol), never `==` on transcendental results. The statelessness
  byte-identical check is same-process only, not a cross-OS claim.
- **Hygiene:** `.gitattributes` normalises to LF; UTF-8 forced (`PYTHONUTF8=1`, explicit
  `encoding="utf-8"`); `pathlib` everywhere, no hardcoded separators.
- **Tracking:** `OPEN.md`, `CHANGELOG.md`, `CLAUDE.md`, `docs/` are tracked so CI has
  `verify.py`'s inputs.

## 8. Branching & commits

- **One branch per slice:** `slice/<NN>-<short-kebab-title>`, off `main`. `main` is
  protected and green-only — it advances solely by whole, oracle-passed slices.
- **A slice is several meaningful commits, never one.** Commits follow the checklist:
  `audit → align → test (oracle RED) → feat (oracle GREEN) → docs (provenance)`, and that
  **sequence is the evidence** the discipline was followed — it is not presentation.
- **Red before green is a hard rule:** the failing reference-value test is committed
  *before* the code that satisfies it. (Carve-out: a pure refactor guarded by an already-
  green oracle need not re-introduce a red, but must run that oracle.) The proof of this
  rule is that the RED commit and the GREEN commit are two commits, in that order — which
  is why the sequence must survive the landing (next rule).
- **Land with SQUASH-and-merge** (amended 2026-10-24, superseding "rebase-and-merge").
  `main` takes one commit per slice, carrying the `(#NN)` PR reference; the slice's own
  commit sequence stays on the PR (`refs/pull/<NN>/head`, which outlives the branch) and is
  the durable record of `RED → GREEN`. The version bump + `CHANGELOG.md` entry is still the
  slice's final `chore(release):` commit, i.e. the tip the squash is named after.

  **Why, so this is never "simplified" back:** commit signatures are cryptographically bound
  to the exact commit bytes — tree, parent, author, committer, message. GitHub's
  rebase-and-merge *re-creates* every commit (new parent, and the committer line replaced by
  the merging account at merge time), which invalidates the signature; it cannot re-sign,
  because the private key never leaves the author's machine. So rebase-and-merge yields an
  **Unverified** `main` — observed, not theorised (`reason: "unsigned"` on every landed
  commit up to v0.110.0). Of GitHub's three methods only **squash** leaves `main` both
  linear *and* verified, because GitHub authors the squashed commit and therefore signs it.
  A merge commit also verifies but forfeits linear history. Verified history won; the
  commit sequence was preserved by moving it to the PR rather than by giving it up.
- **Merge gate:** land only when the oracle is green *and* the layer-scoped test tier
  passes.
- **History before v0.110.0 is Unverified on `main`** and stays that way — re-signing it
  would mean rewriting published history. The guarantee starts at the first squash landing.

---

*Design rationale and full detail: `docs/01_scope_contract.md` … `07_branching_and_commit_policy.md`.
Bottom-up worklist: `docs/L0_ledger.xlsx`.*
