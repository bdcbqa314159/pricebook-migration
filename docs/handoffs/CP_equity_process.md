# Checkpoint — the equity + process-framework run (c1–c3)

**Date:** 2026-10-30 · **By:** Code · **Baseline:** v0.138.0 (gate work in this slice) ·
**Slices since `CP_xva_mc`:** 8 (v0.129.0 → v0.138.0) · **Trigger:** both — the ≤6-slice cadence is
exceeded *and* this is a capability-cluster boundary (a new asset class plus a cross-cutting
abstraction). **Tests:** 568 green, both OSes, ruff + pyright clean. **Drawdown: 31 / 793.**
**Debt: 12 live items** (one closed this slice).

---

## 0. The headline, stated against the plan rather than the work

The run did what it set out to do **technically** and did **not** do what it set out to do on the
**bar**. Both halves are the point of this checkpoint.

- **Done:** equity opened end-to-end (product → pricer → full first-order greeks → MC exposure →
  CVA), the `StateProcess` abstraction landed with both consumers at birth, and equity CVA now
  flows through the **unchanged** `cva` atom — the profile/atom split holding across a *third*
  asset class.
- **Not done:** the bar moved **once** in eight slices (30 → 31), and the slice explicitly
  designated the bar-mover (c3, `mc_exposure.py`) **did not tick**. Two further slices projected
  ticks and delivered none.

**Three consecutive tick projections were overturned.** Not by sloppiness in the projections but
by the *same* discovery each time: the consumed surface was wider than a name-level reading
showed. That is a pattern about the method, and §1 below treats it as the run's main finding.

---

## 1. Oracle-quality audit

| slice | oracle | rung | note |
|---|---|---|---|
| c1 equity vanilla | **BSM spot form**, 1e-10, 5 strikes × 2 types × 2 dividend yields | **1** | the reference never forms `F`, so it is an independent arrangement, not the composition restated |
| c1 | put-call parity `C − P = df·(F − K)` | **1** | model-free; checks the forward against the discount |
| greeks | delta vs `e^{−qT}N(d₁)`; vega vs ng's own `black_vega`·df | **1** | vega's reference is ng's atom, so it tests the *plumbing*, not the formula |
| greeks | gamma — positive, peaks at the **forward**, call/put identical | **structural** | deliberately not analytic: a second difference divides by `h²` and is too noisy for a tight match. Honest about its own precision |
| theta | BS closed-form theta vs the `TimeBump` FD, **plus the convergence rate** | **1** | the rate is what distinguishes a correct `O(Δt)` difference from a wrong construction landing nearby |
| c2 | HW MC **byte-identical**, 140 points / 113 distinct; `E[S_t]`, `Var[S_t]` on the drawn states | **1–2** | moments on the *states*, not through a price, so a dropped `−½σ²` cannot hide in convexity |
| c2 | equity option by MC → **c1 closed form** within 3·stderr | **1** | c1-as-anchor, the reason it was built first |
| c3 | `EE(tᵢ) = V₀/df(0,tᵢ)` — a **martingale identity** | **1** | not a second simulation: the reference is c1's price and a discount factor |
| c3 | the forward's exposure closed form; equity CVA 0.3763 @ R=40% | **1** | the forward exists so the `max(·,0)` floor is actually exercised |

**No rung-4 self-consistency oracle was used anywhere in this run.** Every slice anchored on a
closed form, and c1 was sequenced first specifically to be that anchor for c2 and c3 — the arc
design paid off exactly as intended.

**Two oracles in this run could not have failed, and both were mine:**
1. A `rec01` byte-identity capture of **27 identical `PricingFailure`s** (missing integration
   config) — compared equal over nothing.
2. An HW MC baseline of **40 identical zeros** (`_swap`'s first argument is the *strike*, not the
   tenor, so every swap was 200%-in-the-fixed-leg and every exposure floored).
3. And a *third* of a different kind: the test asserting a clock-advance is **not** an expiry bump
   **passed on a flat curve whichever had been implemented** — flat makes
   `df(T)/df(Δ) = e^{−r(T−Δ)} = df(T−Δ)` exactly.

(1) and (2) produced the **variance-floor clause**; (3) is the structural-oracle rule applied to a
test's *power* rather than its subject. The common thread: **green never reveals a powerless
check**, so power has to be asserted, not observed.

---

## 2. Quarry-drawdown reconciliation — 31 / 793, and an honest reading

| version | Δ | what |
|---|---|---|
| 0.129.0 | — | `SwaptionPrice`; the 381bp made unwritable |
| 0.130.0 | — | three §4 clauses; the sweep's count corrected 6 → 3 |
| 0.131.0 | **+3** | vol_surface · swaption · cds_market → **29** |
| 0.132.0 | — | variable-notional swap (build half of a build-and-tick) |
| 0.133.0 | **+1** | `fixed_income/swap.py` → **30** |
| 0.134.0 | 0 | equity opens (greenfield, 0 expected) |
| 0.135.0 | 0 | equity greeks — **tick projected, did not happen** |
| 0.136.0 | **+1** | theta closes the residual → **31** |
| 0.137.0 | 0 | c2 (0 expected) |
| 0.138.0 | 0 | c3 — **bar-mover projected, did not happen** |

**Reading it straight:** 31/793 is **3.9%**. The four ticks of the (b) harvest came from
*measurement* (modules already superseded), and that source is spent. This run's single tick came
from *building* a missing capability. At this rate `quarry empty = v1.0` is far away, and the
honest statement is that **breadth (opening equity) did not move the bar either** — c1–c3 produced
one tick, and it was the theta slice, not the asset class.

**What actually blocks the next ticks** is now precisely known and forward-linked, which is the
run's real drawdown product:
- `mc_exposure.py` → the **XVA-reporting** surface (ENE, PFE percentiles, peak/effective EPE, DVA,
  FVA), all computable from the **marginals ng already samples**.
- `gbm.py` → the **joint-path** widening (wrong-way risk's shape).
- `equity_option.py` → **ticked**, every name crossed.

---

## 3. Challenge me — the design choices this run made

1. **`StateProcess` is a marginal sampler, not a path sampler.** Narrowest shape both consumers
   need, and §6b-correct. But it is the reason c3's framework is "the right kind and the wrong
   shape" for `mc_exposure.py`. *Challenge:* was deferring joint paths the right call, given the
   module it blocks is the designated bar-mover? **My answer: yes** — Cowork's own correction
   shows the joint matrix is `compute`'s internal mechanism, not the consumed surface, so joint
   paths were never the blocker. The deferral cost nothing.
2. **`black_vec` is a second call shape of `black`.** Bound by a tested identity (`atol=0.0`, 72
   combinations) and precedented by `_bond_vec`. *Challenge:* §3d says an atom is defined once —
   is a bound twin really one atom? I say yes **because the identity is tested**, which is the
   same standard `weighted_annuity ≡ N·rpv01` meets. If that is too permissive, the alternative
   is making `norm_cdf` array-capable, which risks byte-identity across the whole tree.
3. **Greeks are taken by bump, never by closed form.** Equity rho then needed *no code at all*.
   *Challenge:* the quarry ships analytic greeks; are we slower and less precise for it? Accepted
   cost — one differentiation mechanism, and the price a greek differentiates is the price that
   is marked.
4. **`currency` is a field on `EquityOption`.** Deriving it from the snapshot reads fine in a
   single-currency book and silently marks a EUR option off the USD curve in a two-currency one.
5. **Theta's coupon precondition is documented, not enforced** (`NG-DEFER-THETA-COUPON-GUARD`). I
   argued for building the guard; Cowork overruled on §6b grounds and was right — no present
   consumer can violate it.

---

## 4. Smell + debt scan

- **12 live ledger items**, all deferred *scope* with named triggers; none buys a green oracle.
  **`NG-WATCH-CLOCK` closed this slice** by promotion to a gate (its second instance arrived).
- **`NG-DEFER-THETA-COUPON-GUARD`** is the one to watch: it is a documented precondition on a
  public function, which is the weakest kind of guarantee in the tree. Its trigger (first
  coupon-product theta) is also the first moment it could be violated, so the timing is right.
- **Naming:** `risk/` now holds `exposure`, `greeks`, `equity`, `credit`, `xva`, `bump`,
  `monte_carlo`, `priceable`. Still navigable, but `exposure.py` has grown four rates builders
  plus the equity one and a `singledispatch` table — **the next exposure builder should split it**,
  not the one after.
- **No suppressions.** The one `# noqa` this run would have needed (a PascalCase constructor
  function) was removed by choosing a classmethod instead.

---

## 5. The two §4 clauses this run added, and why they matter more than the ticks

1. **A consumed aggregate consumes its members** (v0.136.0). Landed from `equity_theta`; one slice
   later it caught **Cowork's own stale 0042 finding** (`ExposureResult` "had 0 consumers" — its
   importer calls `.to_dict()`). A rule that overturns its author's prior assessment is doing real
   work.
2. **A baseline must assert its discriminating power** (v0.138.0) — the floor rule's third face.

Plus **the clock gate** (`verify.py slow`, §7c), promoted from `NG-WATCH-CLOCK`.

**The through-line of all three:** every one of them guards against *a check that cannot fail*.
That is now, measurably, this project's most common defect class — more common than wrong numbers.

---

## 6. Named next checkpoint

**`CP_xva_reporting`** — at the first of: 6 slices after XVA-reporting lands, or the next
capability-cluster boundary (wrong-way risk / joint paths, or whatever opens after
`mc_exposure.py` retires). Immediate-stop triggers unchanged.

**Proposed next slice (Cowork to rule):** **XVA-reporting** — the marginal `XvaReport`
(ENE · PFE profile · peak EE · effective EPE · DVA · FVA) that retires `mc_exposure.py`,
**31 → 32**.
