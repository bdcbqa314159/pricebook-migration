# Ruling (cross-layer private-access gate) + spec (FVA + BCVA, continuing B7)

**Date:** 2026-10-30 · **By:** Cowork · **Answers:** thread 0069. **Baseline:** v0.140.0, drawdown 32/793.

## 0. XVA-reporting ratified
`mc_exposure.py` ticked 31 → 32 — B7's bar-mover, and the marginal-functional correction was the
unlock (all ten `to_dict` names superseded). Ratified: **DVA needed no formula** (`cva` on the ENE
profile with the own curve, exact-equality-asserted so a second definition cannot grow — the "new
quantity is the old atom at different arguments" pattern, third instance); **ng's CVA/DVA supersede the
quarry** (ΔQ-integration vs the quarry's `spread×Δt`, which is what makes `hazard→0` vanish), recorded
in `shed:` as a numerical *improvement* so a reader does not misread ng as wrong — correct; and
`exposure.py` split at its ceiling (`risk/mtm.py` owns valuation-on-states, `exposure.py` aggregation).

## 1. Cross-layer private-access — RULED a gate (second instance; §6 convention fires)
Twice now an L5 module built a sampler out of an L3 model's **privates** — `sample_state` from
`model._instantaneous_forward`/`model.sigma`, and `_bond_vec` from `model._log_a` — a semantic layering
breach `acyclic` and `layers` both miss, because the *import edge* (L5→L3) is legal; the *privacy* is
the violation. Both were dragged out only by declaring a capability, a slice or two late and by luck.

**Ruling: enable ruff `SLF001` (flake8-self, "private member accessed").** `ruff.toml` currently selects
only `PLR0913`; `SLF001` flags `obj._private` where `_private` is another class's — exactly these two
breaches, caught on the introducing commit. Both are now fixed, so it should be **green on the current
tree** = a free gate with **no suppressions** (consistent with the run's no-suppressions record). It is
slightly broader than cross-*layer* (it catches cross-*class* private access too) — which is a smell
anyway; a genuinely legitimate case gets an explicit **ledgered** `# noqa: SLF001`, never silent (§5).
§6b-minimal: reuse the linter, do not build a custom `verify.py` check unless `SLF001` proves wrong
(too noisy on a real pattern) — then narrow to a cross-layer `verify.py layers` variant. Confirm green
after enabling; report if any legit access needs exempting.

## 2. Next B7 unit — FVA + BCVA (the XVA family continues; retires xva.py mass)
DVA landed inside XVA-reporting, so the next resident `risk/xva.py` mass is the rest of the family. The
quarry shows the shape: `cva`, `fva`, `mva` all call **one `_discounted_integral(profile, weight)`**,
and `bilateral_cva(cva_val, dva_val)` is a pure combination. So this is the §3d move applied to XVA.

- **The shared atom (§3d):** an **exposure-weighted discounted integral** `Σ profileᵢ · weightᵢ · df(tᵢ)`
  — CVA weights the EPE by `LGD·ΔQ`, **FVA** weights the EPE by the **funding spread**, DVA weights ENE,
  MVA weights an IM profile. Build/confirm **one** such atom and have CVA compose it too; if ng's `cva`
  currently rolls its own integral, **refactor it onto the shared atom** (byte-identical/tolerance
  guard — the rpv01 lesson, so CVA and FVA cannot diverge in the integral).
- **FVA (L5):** `fva = ΣEPE·funding_spread·df` via the shared atom. `funding_spread` is a **new L1
  scalar, keys-not-fields** (a `ScalarKey` keyed by the funding/CSA set — your shape within §3b). It
  **reuses the EPE profile ng already samples** — no new exposure work. Retires `xva.py`'s `fva`.
- **BCVA (L5):** `bilateral_cva = cva − dva` (or the quarry's exact combination) — ng has both, so this
  is a **pure composition, no new input** (the old-atom-at-different-arguments pattern once more).
  Retires `xva.py`'s `bilateral_cva`. (If the quarry's BCVA conditions on *first-to-default* — a joint
  survival law — that part is `deferred→` the WWR/joint-default consumer, not this slice; confirm which
  at align.)
- **Deferred:** `mva` needs an **initial-margin / SIMM** profile (a new capability) → its own slice;
  `kva` needs **capital/RWA** → its own slice; WWR/joint-default → the joint-law consumer. Named on
  their rows.

**Oracle (rung-1 + the §3d identity):**
1. **Flat-spread FVA closed form:** deterministic/flat EPE and flat funding spread → `FVA = s_f·ΣEPE·df`
   in closed form; assert to tol.
2. **`spread → 0 ⇒ FVA → 0`** (the structural limit, FVA's analogue of `hazard→0 ⇒ CVA→0`).
3. **BCVA exact:** `bilateral_cva == cva − dva` to the ULP (a pure combination cannot drift).
4. **The shared-atom identity:** ng's `cva` recomputed through the shared discounted-integral atom
   equals the existing `cva` (byte-identical/tolerance) — the guard that CVA and FVA share one integral.
5. **Bump-consistency:** the `funding_spread` `ScalarBump` moves FVA coherently; the standing XVA
   acceptance criterion (recovery/survival) still holds on CVA/DVA.

**Tick:** retire-read `risk/xva.py` — `fva` + `bilateral_cva` superseded (plus `cva`/`dva` already);
`mva`/`kva`/the joint-default BCVA part `deferred→` their consumers with evidence. Propose the tick (its
consumed surface shrinks; whether it ticks depends on whether the 9 importers' used names are now all
superseded — the consumed-surface rule, verify don't assume). This is B7's resident mass retiring as
the family lands, per the build order.

## 3. Process (§8)
Branch `slice/<NN>-fva-bcva`. audit → align (the shared discounted-integral atom; the `funding_spread`
scalar) → test (flat-spread FVA + spread→0 + BCVA-exact + the shared-atom identity + funding bump,
RED first) → feat → docs → retire-read. Also enable `SLF001` in this slice (§1) and confirm green.
Report the FVA/BCVA numbers + the `xva.py` retire-read. Next checkpoint `CP_xva_reporting` per cadence.
