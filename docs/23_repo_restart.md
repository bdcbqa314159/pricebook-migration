# Artifact #23 — repo restart (current)

**Status:** current — executed 2026-10-25, all 8 criteria pass
**Governing purpose:** Re-found the repository so the remaining 97% of the migration lands in a
clean structure, and repair the merge gate so it asserts what the law already claims.
**Inherits:** THE BAR (`CLAUDE.md` §1 layering · §4 green-oracle · §5 debt · §7b provenance)

## Reframe

**Nothing about the design is broken.** The law (`CLAUDE.md`), the 22 ratified artifacts, the 59 ng
modules (L0 closed, zero debt), every oracle's expected value, the migration method, linear-history
protection and the squash-only button all stand and are carried unchanged. What is broken is
**housekeeping and one gate**: 13 quarry-era docs sit at root that §7b already declares "not carried
forward"; `_ng` suffixes are migration scar tissue; and CI runs `tests --layer 0`, which is **177 of the
suite's 366 tests** — so 189 tests (52%), including every oracle from slices 20–25, are gated by
nothing. This is a relocation plus a gate repair. No
pricing logic changes, no design decision is reopened, no number moves.

## MUST — in scope, full discipline

- **M1** Fresh repo at the ratified layout, **one initial commit** stamped `v0.111.0`:
  `src/pricebook/` · `tests/` · `docs/` (was `redesign/`) · `notes/` (was `documents/`) ·
  `quarry/` (was `python/`, with `parked/` + `ng_parked/` folded under it) · root limited to
  `CLAUDE.md` `CHANGELOG.md` `OPEN.md` `README.md` `LICENSE` `pyproject.toml` `ruff.toml`
  `pyrightconfig.json` `verify.py` **`conftest.py`** + the tracked dotfiles `.gitignore`
  `.gitattributes` `.editorconfig` `.pre-commit-config.yaml` `.github/workflows/ci.yml`.
  **Correction (pre-ratification):** `conftest.py` was listed as quarry-era debt on first pass. It
  is not — it puts `src/` on `sys.path` and **all 366 tests depend on it**. Dropping it would have
  failed A2 on the first run. `.pre-commit-config.yaml` likewise moves from NOT-NOW to MUST: it is
  tracked and working, so carrying it is zero work.
- **M2** Package rename `pricebook_ng` → `pricebook`, `tests_ng` → `tests`, including every
  `quarry:` provenance header rewritten `python/…` → `quarry/…`, and `verify.py` / `pyproject.toml`
  / `pyrightconfig.json` / `ci.yml` path updates.
- **M3** CI gates **every present test layer** (L0–L6), not L0 alone.
- **M4** All gates green on `ubuntu-latest` + `windows-latest`: `acyclic · layers · debt · version ·
  provenance`, `ruff check src/pricebook`, `pyright`, full test tier.
- **M5** Old repo renamed `pricebook-legacy` and GitHub-archived read-only; new `README.md` links to
  it as the record of the 151 landed slices.
- **M6** Branch protection replicated on the new repo: required linear history, both OS checks
  required, squash-only merge button.
- **M7** `.cowork/` re-established in the new tree, **its two files treated oppositely.** The
  directory is **gitignored** (`.gitignore:73`, landed PR #151), so `git archive` carries neither:
  - `README.md` — **regenerated, not copied.** Its pointers name `redesign/` and
    `src/pricebook_ng/`, both of which M1/M2 rename. A stale protocol is worse than none, because
    Cowork will follow it.
  - `thread.md` — **copied verbatim, at the last possible moment** (Phase 2, after the folder swap).
    It holds live conversation — entry `0001` carries an unanswered Ask — and conversation is the one
    thing the repo does not already record. Regenerating the directory wholesale would delete it,
    along with any reply Cowork appends while the restart is in flight.

  Ordering constraint: `README.md` is written in the **staging tree** (Phase 0) so the protocol is
  already correct the instant the swap happens; `thread.md` is copied **last**, so no Cowork reply
  written during Phase 1 is lost.
- **M8** `docs/README.md` reconciled against the artifacts it describes. Two known stale claims,
  both found while writing this one: (a) drawdown reads `13 / 768`, the tracker reads `22 / 793`
  (§4 names the tracker the single source); (b) it calls F2/artifact 22 "rev 2 … awaiting
  adversarial review before ratification", but 22 is **RATIFIED rev 3 (2026-07-29)**. The whole
  file is re-read against its referents, not just these two lines — a stale index is the one doc
  that mis-routes every cold start.

## NOT-NOW — real, but deferred this cycle

- Repository **rulesets** in place of legacy branch protection (legacy protection works today;
  migrate when a second branch pattern needs governing).
- The **nightly full-sweep + quarry-regression** workflow §7b/§7c describe and that has never
  existed. M3 closes the per-PR hole; the nightly job is its own slice.

## NEVER — out of scope

- **Replaying the 151-PR history** into the new repo. §8 names `refs/pull/<NN>/head` the durable
  RED→GREEN record; it stays where it already is.
- **Deleting `pricebook-legacy`.** Archive, never delete — it holds that record.
- **Splitting the quarry into its own repo.** See D2.
- **Touching pricing logic, oracle expected values, or any ratified design decision.** A diff in any
  of those means this artifact failed, not that it grew.
- **Resetting the version line to `0.1.0`.** See D4.

## Acceptance

| ID | Criterion | Oracle | Rung |
|----|-----------|--------|------|
| A1 | Every carried file is byte-identical to its legacy counterpart, modulo the rename map and the M2/M8 edits | scripted git-blob-hash compare across the rename map; expect **0 unexplained mismatches** over all carried files, and an explicit allow-list for the M2/M8 edits | 1 |
| A2 | The full suite over L0–L6 in the new tree reproduces the legacy tree at `ba4d5afd` | `pytest tests -q`; expect **366 passed, 0 failed, 0 errors** (measured baseline, legacy tree @ `ba4d5afd`) | 3 |
| A3 | The gate runs the whole suite, not one tier | CI's test step reports **366 passed across 6 layer dirs**; today it reports **177 across 1**, so the gate must newly cover **189 tests**. A count, per §6's structural-oracle rule — a tier gate is a *structure*, and a flat "gates green" claim was blind to the L0-only hole for 6 slices | structural count |
| A4 | All gates green on both OSes | first CI run on the new repo's initial PR: green × 2 | 3 |
| A5 | No provenance header was broken by the `python/` → `quarry/` rewrite | `verify.py provenance` green **and** scripted existence check on every `quarry:` path; expect **0 dangling** | 1 |
| A6 | The legacy record survives the rename + archive | fetch `refs/pull/{1,75,150,151}/head` from `pricebook-legacy` after archiving; expect 4 successes | 3 |
| A7 | The rename left no residue | `grep -r 'pricebook_ng\|tests_ng'` over `src/ tests/ conftest.py verify.py pyproject.toml pyrightconfig.json .github/`; expect **0 hits**. Measured surface: **4 root files** (`conftest.py` `pyproject.toml` `pyrightconfig.json` `verify.py`, ~12 refs) **+ the test files that import the package**. `docs/` and `quarry/` are exempt — historical text | 1 |
| A8 | The channel survives with correct pointers | two checks: (a) scripted path-extract + existence over the regenerated `README.md`, expect **0 dangling** (today it names `redesign/`, which M1 renames); (b) `thread.md` carried, entry `0001` present, byte-identical to the legacy copy plus any reply appended during the restart | 1 |

## Decisions

| # | Decision | Alternatives | Why this | Revisit when |
|---|----------|--------------|----------|--------------|
| D1 | Fresh repo | in-place `git mv`; orphan commit on this repo | The reorganisation is identical work either way; the fresh repo additionally buys Verified-from-commit-1 and slice-aligned PR numbers. Repo is 25 MiB, so nothing is paid for it | one-way — not revisited |
| D2 | Quarry carried in-repo as `quarry/` | separate read-only repo; submodule | §4 parking **physically moves** quarry modules into `parked/<topic>/` when a topic closes; a read-only sibling makes that write cross a repo boundary and splits the drawdown bookkeeping from the tracker that computes it | drawdown ≥ ~700/793, when the residue is small enough to sit inside `docs/` |
| D3 | Rename `pricebook_ng` → `pricebook` now | keep `_ng` until v1.0 | 59 modules is the cheapest this rename will ever be, and `_ng` is exactly the scar tissue the restart exists to remove. Deferring means doing it at 10× the size | one-way — not revisited |
| D4 | Version line continues at `v0.111.0` | reset to `0.1.0` | §7 binds `1.0.0` to "quarry empty". Resetting either breaks that binding or asserts the 111 landed stamps did not happen | one-way — not revisited |
| D5 | `ng_parked/` (119 files) carried under `quarry/parked/ng/` | leave it in legacy | Artifact 18 §T1 states "most of C2/C3 is a **re-base from `ng_parked/`**" — it is load-bearing content source for the *next* topic, not dead weight | T1 closes and its MANIFEST rows are all re-based |
| D6 | `redesign/` carried whole as `docs/` (97 files) | ratified artifacts + live trackers only | The checkpoint reports are the rationale trail behind the law, and `quarry_reconciliation.md` is the drawdown source of truth. Cheap to keep, expensive to want back | `docs/` exceeds ~200 files |

## Open questions — closed at ratification

1. **Reuse the name `pricebook`** — *yes.* Old repo → `pricebook-legacy`, new repo takes
   `pricebook`. Accepted cost: GitHub's `pricebook` → `pricebook-legacy` redirect is removed, so
   stale links to the old name resolve to the new repo rather than the archive. Tolerable — there
   is one clone and it is re-pointed in Phase 2.
2. **Execution** — Claude Code runs the GitHub-facing steps with `gh`, reporting each result.
3. *(was non-blocking)* `documents/` → `notes/` — confirmed.

## Progress
| ID | Status | Oracle result | Note |
|----|--------|---------------|------|
| A1 | pass | 2157 / 2157 accounted · **0 unexplained** | 2035 byte-identical · 111 differ only by the path rewrites (each re-derived from the legacy blob by applying the substitutions) · 8 deliberate edits · 3 dropped. 0 missing, 0 extra. |
| A2 | pass | **366 passed, 0 failed** vs baseline 366 | `pytest tests -q`, 1.24s |
| A3 | pass | `verify.py tests` collects **366 across 6 layer dirs** (was 177 across 1) | **189 tests newly gated.** Fixed by making `--layer` optional and discovering `tests/L*` — a hardcoded ceiling is the bug, not the value `0`. **Re-anchored 2026-10-26:** this count was written on Code's authority; it now derives from CLAUDE.md §6's floor rule (ruling `handoffs/rulings_floor_rule.md`) and is enforced as `verify.py`'s committed `TEST_FLOOR`, RED below — not a number in a table |
| A4 | pass | **ubuntu-latest: success · windows-latest: success** | run on `944063f`; deps matched the CI pins (numpy 2.4.3 / scipy 1.17.1) locally beforehand, so the first push was predictable |
| A5 | pass | **0 broken by the rewrite** (17 of 45 already dangling before it) | pre-existing drift logged as `OPEN.md` **NG-DEFER-PROV**, not fixed here — three distinct failure modes make it its own slice |
| A6 | pass | **4 / 4** refs resolve from the archived repo | `refs/pull/{1,75,150,151}/head` → `57fde59f` `0418d137` `bcd4eeda` `49dd2921`; 150's tip is the slice-25 RED→GREEN sequence |
| A7 | pass | **0 refs** to `pricebook_ng` / `tests_ng` on the live surface | 644 refs rewritten across 113 files; `quarry/parked/ng/`'s 728 deliberately untouched (its package genuinely is `pricebook_ng`) |
| A8 | pass | (a) **0 dangling** in the regenerated protocol, re-run post-swap · (b) `thread.md` **byte-identical** to the legacy copy, entry `0001` intact | |

## Carry-list corrections found during Phase 0

Measured against `git archive`, not assumed:

- **The quarry-era root docs are GITIGNORED and untracked** — `ARCHITECTURE.md` `AUDIT_PLAN.md`
  `DESIGN.md` `GUIDE.md` `IDEAS.md` `PLAN.md` `L0..L7_DEPS.md`. They were **never in the GitHub
  repo**, so "they live on in `pricebook-legacy`" was wrong: they live on only in the *local* folder
  `~/work/pricebook-legacy` after the Phase 2 swap. Nothing is lost, but nothing about them is
  backed up either — true before this artifact and still true after it.
- **The only TRACKED drops are** `REFERENCES.md`, `RELEASE_NOTES.md` (frozen quarry record, §7) and
  `analysis/` (1 file). Those three do survive in the GitHub archive.
- **`tools/` (3 files) was missing from the rename map.** It is quarry-era tooling that scans
  `pricebook/` — `layer_deps.py` is the generator for the `L*_DEPS.md` files §7b declines to carry.
  It goes to **`quarry/tools/`**: it operates on the quarry, the quarry is carried, and dropping a
  working tool to save three files is false economy. Its outputs stay gitignored, so nothing
  regenerates into the tree.
- **Reference count: 2157 tracked files** at `97d22ed2`. A1 compares against exactly this set.

## Outcome

Executed in three phases, nothing outward-facing until A1/A2/A5/A7 were green. `main` on the new
repo is protected identically to the legacy repo (linear history, both OS checks required,
squash-only, no force-push). The legacy repo is archived read-only with all 151 PRs' commit
sequences reachable on `refs/pull/<N>/head`.

**One finding deferred, not silenced:** `OPEN.md` **NG-DEFER-PROV** — 17 of 45 `quarry:` provenance
paths do not resolve, *none* broken by this artifact's rewrite. `verify.py provenance` checks the
four lines exist, never that the path resolves. Three distinct failure modes (parked-move,
wrong-subdirectory-from-birth, file-exists-nowhere) make it its own slice with its own oracle.

## Re-anchoring (2026-10-26)

A3's count stood on Code's authority when this artifact landed, and `0002` asked whether it should.
Cowork ruled it should not: `handoffs/rulings_floor_rule.md` amends CLAUDE.md §6 so the floor rule
binds the verification apparatus, and A3's count is now the law's `TEST_FLOOR`, asserted by
`verify.py tests` with CI RED below it. The criterion is unchanged; its *authority* moved from
judgement to law.
