# Audit — slice B align step: STOP. The FIT was never threaded, only the READ (ML-D2)

**Baseline:** v0.113.0 · **Spec:** `spec_slice_B_swaption_cube.md` · **Trigger:** §6 immediate stop —
a contract question on a ratified L1 type. Found in the **align** step, before any code.
**Relation:** this is **ML-D1 again, on the other side of the calibration boundary.**

## 1. The finding

Slice A (v0.111.0, Cowork ruling A) threaded the forward through the **read**: both vol capabilities
take it as an input, so the engine computes `S = float_leg_pv/rpv01` over the contract's own accrual
and **passes** it. The **fit** was not changed. `calibrate_sabr_smile` still derives its own forward:

```python
accrual = index.canonical_accrual(smile.expiry)          # sabr_calibrate.py
fwd = forward(market.curves.projection(index), accrual)  # the single-period CAPLET forward
```

The engine, pricing a swaption, marks something else entirely (`engine/vanilla_option.py`):

```python
annuity = rpv01(fixed_sched, swap.fixed_leg.day_count, discount)
s = float_leg_pv(float_sched, swap.float_leg.day_count, discount, projection) / annuity
vol = model.swaption_vol(index, swaption.expiry, swap_tenor, strike, s)   # the marked S
```

`s` depends on the swap's **fixed-leg frequency**, **both legs' day counts**, its **collateral**
(which discount curve) and **seasoning** (`future_periods`). None of that is derivable from
`(index, expiry, swap_tenor)` — that *is* ML-D1, and slice A measured the gap at **48.8 bp / 1.4%**
across the four underlying conventions this tree itself uses.

**Consequence for slice B as specced.** The spec says *"fit each node at the same S the pricer will
use"* — the right intent — but instructs composing `calibrate_sabr_smile`, which cannot do it. Every
cube node would be fit at the caplet forward and read at the swaption S: ML-D1 reintroduced per node,
in a grid, right after the slice that eliminated it.

## 2. Why it cannot be patched locally

`SabrCalibrationSpec` is **already at §3b's 5-field ceiling** (`model, index, smile, beta, solve`), so
it cannot gain a `forward`. §3b is explicit that a signature over the limit is un-bundled vocabulary,
never a reason to raise the limit — so the forward must land on an existing value object.

## 3. Options, ranked

**(1) `SmileQuote` gains `forward` — RECOMMENDED.** 3 → 4 fields, inside the limit. Semantically it is
the quote's own datum: a market smile *is* quoted at a forward, and the forward must travel **with**
the smile for the same reason `SabrSurface.law` must travel with its params — params read against the
wrong forward are silently wrong by the F-gap, and the existing docstring already makes that argument
for `law`. Required, not defaulted: a smile without its forward is a contract error.
*Blast radius:* 2 src sites (`sabr_calibrate.py:66,187`), 9 test construction sites. Small, and it
threads the fit symmetrically with slice A's read.

**(2) A `SwaptionSmileQuote` sibling carrying the forward.** Leaves the caplet path untouched, but
§6b's rule of two forbids it at one consumer, and it duplicates the smile atom (§3d — two dialects of
one thing is the defect this cluster already has twice, audit F9).

**(3) Optional `forward=None` → canonical fallback. REJECTED.** It reinstates the hidden default slice
A deleted, and the fallback is silently wrong in exactly the non-canonical case that motivated A.
Invariant 5: config is explicit, never a hidden default.

## 4. The answer to the spec's own vacuity flag (oracle 2)

The spec asks Code to flag whether any oracle can pass without S flowing per node. **Yes — oracle 2
can, and the condition is precise:** if the test's underlying is *canonical* (annual / ACT-365F, i.e.
matching `index.canonical_accrual`), then `S == F` and the ATM-payer-at-smile-minimum test passes with
the defect fully latent. It bites **only** with a non-canonical underlying — which is exactly why
slice A's RED test is named *non-canonical-underlying ATM-at-smile-minimum*.

**So oracle 2 must specify a non-canonical underlying (semi-annual / ACT-360) or it is vacuous.** That
is a spec amendment, not an implementation detail: as written, "each node's ATM payer lands at its
smile minimum" is satisfiable by a canonical test grid while every node is mis-fit.

## 5. What is unaffected

Rulings **B1** (node count / no silent drop), **B2** (failure as a counted value) and **B3** (defer
`interp_surface`; negative criterion) are untouched by this — they concern the result shape and the
deferral, not the forward. Oracles 1, 3, 4, 5 stand. The slice-A read path
(`SABRModel.swaption_vol`) is correct and stays. 366 tests green; drawdown unchanged at 22 / 793.
