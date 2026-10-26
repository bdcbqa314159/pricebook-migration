# Artifact #10 — CI & Cross-Platform Policy (Ratified)

**Status:** Ratified. Companion policy. Tests run on **Linux and Windows**;
this fixes the constraints that a cross-platform *pricing* library must honour, and the
tracking implications that follow.

---

## Why cross-platform settles the tracking question

Running CI on two OSes means GitHub Actions off a **pushed, tracked** repo. `verify.py`'s
checks need their inputs present:
- `verify.py debt` reads **`OPEN.md`**
- `verify.py version` reads **`CHANGELOG.md`**
- `verify.py provenance` reads the **source headers**

So `OPEN.md`, `CHANGELOG.md`, `CLAUDE.md`, and `redesign/` are **tracked** (gitignore
exceptions added). The quarry-era "root notes stay local" convention is superseded — a
half-tracked repo can't run its own discipline in CI.

---

## The one real hazard: floating point across OS

Linux (glibc) and Windows (MSVC CRT) both use IEEE-754 doubles, so arithmetic agrees, but
`exp` / `log` / `pow` / trig can differ by **1–2 ULP** between their math libraries.

**Rules for oracles under cross-platform CI:**
1. **Assert tolerances, never bit-exact equality across OS.** `pytest.approx(..., abs=1e-12)`
   or `rel=1e-10`, never `==` on transcendental results. Slice 0's `PV == notional·exp(-r·t)`
   to `<1e-12` is safe; a bit-exact assertion is not.
2. **Statelessness "byte-identical" stays valid** — it is *same-process, same-platform*
   reproducibility (repeat a pricing, get the identical result), not a cross-OS claim.
   Keep it; don't reinterpret it as cross-platform bit-equality.
3. **Set oracle tolerances to the oracle's own accuracy**, comfortably above libm noise
   (~1e-15). Closed-form oracles: `1e-12`. MC/PDE oracles: their convergence tolerance.
4. **Seeded stochastic tests:** fix the RNG in `NumericalConfig`; the sequence is
   deterministic cross-OS, but assert on aggregates with tolerance, not per-path equality.

---

## Routine cross-platform hygiene

- **`.gitattributes`** normalising to **LF** (`* text=auto eol=lf`) — stops Windows CRLF
  corrupting golden files, test data, and diffs.
- **UTF-8 forced** — `PYTHONUTF8=1` in CI env (Windows defaults to cp1252); open files with
  explicit `encoding="utf-8"`.
- **`pathlib` everywhere** — no hardcoded `/`; no OS-specific path assumptions.
- **Deps** — numpy / scipy / duckdb all ship Windows wheels; SQLite is stdlib. No
  LibreOffice/`soffice` needed in CI (that was only for xlsx recalc in the design phase).

---

## CI shape

```yaml
# .github/workflows/ci.yml  (sketch)
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest]
    python-version: ["3.12"]      # matches pyproject target-version
```

- **Per slice-branch PR (fast, both OSes):**
  `verify.py acyclic && verify.py debt && verify.py version && verify.py provenance`
  + the slice's layer tier `verify.py tests --layer <L>`.
- **Merge gate:** the above green on **both** OSes before rebase-and-merge to `main`.
- **Nightly / layer checkpoint:** full new-tree suite + quarry regression suite, matrix.

Keep it to one workflow file. No speculative jobs (per CLAUDE.md §6b) — add macOS or more
Python versions only when a real need appears.

---

## Ratified decisions (2026-07, Bernardo)
1. **Matrix: Ubuntu + Windows, Python 3.12.** ✅ One workflow file. macOS / more Python
   versions added later only on a real, present need (CLAUDE.md §6b), never speculatively.
2. **Tolerance-based oracles: hard rule.** ✅ Oracles assert tolerances sized to the
   oracle's own accuracy (closed-form `1e-12`; MC/PDE their convergence tol) — never `==`
   on transcendental results. A bit-exact cross-OS assertion is a bug. The statelessness
   "byte-identical" check remains valid (same-process reproducibility, not cross-OS).
3. **Track the discipline inputs.** ✅ `OPEN.md`, `CHANGELOG.md`, `CLAUDE.md`, `redesign/`
   are git-tracked (gitignore exceptions applied) so `verify.py` runs in CI. The
   "root-notes-stay-local" quarry convention is superseded for these files.

---

## The test floor (amended 2026-10-26 — ruling: `handoffs/rulings_floor_rule.md`)

CI runs the **whole** suite: `verify.py tests` with no `--layer` ceiling, discovering every
`tests/L*` directory present. `--layer N` survives only for the per-tier local run.

**And the collected count is asserted against a committed floor** — `TEST_FLOOR` in `verify.py`,
currently **366**. CI is **RED** below it. A slice that adds a test tier raises `TEST_FLOOR` in the
same commit.

**Why a floor and not just "no ceiling":** removing the ceiling fixes *truncation*; the floor also
catches *shrinkage* — tests silently dropped, a collection error swallowing a directory, a rename
orphaning a tier. Both are the same defect: green over a population nobody counted. This is the
floor rule's first face (CLAUDE.md §6), and it is the assertion that would have caught the original
`--layer 0` bug: that command collects 177 against a floor of 366.

The never-bumped `ci.yml` comment *"Bump --layer as topics add tiers"* was the original sin. A number
that must be remembered will eventually not be; a hard floor plus discovery removes the need to
remember.

---

## The quarry import gate (added 2026-10-26 — ruling: `handoffs/rulings_quarry_park_model.md`)

**`verify.py quarry` walks the quarry package tree and asserts the importable-module count against
`QUARRY_IMPORT_FLOOR`** (currently **792**), RED on any drop, and RED if *any* module fails to import.

**It is deliberately not `import pricebook`.** That check was proposed first and rejected after
measurement: it **passes while the quarry is broken**, because the top package's `__init__` does not
eagerly import its sub-packages — `import pricebook` was OK while `pricebook.core` and
`pricebook.curves` raised and 265 of 583 modules were unreachable. A gate must assert the property,
not a name that resolves (CLAUDE.md §6, the floor rule).

**It also asserts it measured the right package.** Since the restart, ng and the quarry are *both*
named `pricebook` (`src/pricebook`, `quarry/pricebook`), so the walk runs in a subprocess rooted at
`quarry/` **and** checks that the imported package's `__file__` lies under `quarry/` — measuring ng
here would be a proxy that passes while the quarry is broken.
