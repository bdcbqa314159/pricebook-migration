# Artifact #07 — Branching & Commit Policy (Ratified)

**Status:** Ratified. Companion workflow policy. Governs how slices become git
history in the new tree.

---

## Principle

A **slice** is the unit of *correctness* (one oracle, one version bump, one changelog
entry). It is **not** required to be the unit of *history*. A slice may — and usually
should — be several meaningful commits. Slower, legible progression beats one squashed
blob: the history should show the audit, the alignment, the red oracle, then the green.

---

## Branching model — one branch per slice

```
main                    always green; every commit is a landed, oracle-passed slice
  └── slice/00-walking-skeleton     one branch per slice, off main
  └── slice/01-daycount-schedule
  └── slice/02-discount-curve-bootstrap
```

- Branch name: `slice/<NN>-<short-kebab-title>` (NN = slice number from the slice plan).
- A branch exists for the life of one slice; it merges to `main` when the slice lands
  green, then is deleted.
- `main` is sacrosanct: it only ever advances by whole, oracle-passed slices. Never
  commit work-in-progress directly to `main`.

## Commits within a slice — several, each meaningful

Commits map to the per-entry migration checklist, so the history *is* the audit trail:

```
audit:  <entry> — read quarry original; note deps, debt, oracle target
align:  <entry> — rewrite to spine layer + vocabulary; behaviour → engine
test:   <entry> — oracle RED (failing reference-value test committed first)
feat:   <entry> — oracle GREEN (implementation passes the reference value)
docs:   <entry> — provenance (quarry path, paper/model, oracle) recorded
```

- Not every slice needs all five, but **red-before-green must be two commits** — the
  failing oracle is committed before the code that satisfies it. That is the proof the
  oracle can fail, which is the whole point of an oracle.
- Each commit compiles and is internally coherent (even if the slice isn't done).
- Conventional-commit prefixes (`audit/align/feat/fix/test/docs/refactor`) for scannable
  history.

## Merge — SUPERSEDED 2026-10-24: squash-and-merge (see CLAUDE.md §8)

> **AMENDED.** The ratified rebase-and-merge policy below was overturned on 2026-10-24 for a reason
> it could not have anticipated: **GitHub's rebase-and-merge strips commit signatures.** It
> re-creates every commit (new parent, committer line replaced by the merging account at merge
> time), which invalidates the signature, and it cannot re-sign because the private key never
> leaves the author's machine — so `main` was **Unverified** for its entire history up to v0.110.0
> (`reason: "unsigned"`, observed on every landed commit). Of GitHub's three merge methods only
> **squash** leaves `main` both linear *and* verified, because GitHub authors the squashed commit
> and therefore signs it.
>
> **What changed:** `main` now takes **one squashed commit per slice**, carrying the `(#NN)` PR
> reference. **What did NOT change:** a slice is still several meaningful commits in the
> `audit → align → test(RED) → feat(GREEN) → docs → chore(release)` order, and red-before-green is
> still a hard rule — the sequence now lives on the PR (`refs/pull/<NN>/head`, which outlives the
> branch) instead of on `main`. The history-level proof that the oracle can fail is preserved; only
> *where it is read* moved. `CLAUDE.md` §8 is the enforceable statement; the text below is kept as
> the record of what was originally ratified and why.


- Land slices with **rebase-and-merge**: `main` stays a clean straight line, and the
  intra-slice commits (`audit → align → test → feat → docs`) are all preserved on it.
  No squash.
- Because there is no merge commit, the **version bump + `CHANGELOG.md` entry** are the
  **final commit of the slice** — a `chore(release): vX.Y.Z — <slice>` commit that lands
  at the tip, carrying provenance (what changed, oracle, quarry path). One per slice.
- **Merge gate:** a slice may land only when its oracle is green *and* the layer-scoped
  test tier passes (see the staged-test policy). Enforced by CI / branch protection on
  `main`. Rebase locally onto latest `main` before landing so the line stays clean.

## What this changes vs. the quarry's habit

The quarry advanced ~11 versions/day, effectively one commit per bump on a single line.
The new model is slower and branchier by design: fewer, larger, *meaningful* landings on
`main`, each a proven slice with a readable internal history. That is the point.

---

## Ratified decisions (2026-07, Bernardo)

1. **Merge strategy: rebase-and-merge.** ⚠️ **SUPERSEDED 2026-10-24 → squash-and-merge**
   (signature verification; see the amendment note above and `CLAUDE.md` §8). As originally
   ratified: linear `main`; all intra-slice commits preserved; no squash, no merge bubble.
   Version bump + changelog is the slice's final `chore(release):` commit — still true, and
   it is now the commit the squash is named after.
2. **Red-before-green: hard rule.** ✅ Every slice commits the failing reference-value
   test *before* the code that satisfies it — enforced, not just encouraged. This is the
   history-level proof that the oracle can fail (the core answer to the "no oracle"
   problem). Narrow carve-out: a pure refactor guarded by an *already-green* oracle need
   not re-introduce a red, but it must run that oracle.

Defaults adopted: `slice/NN-title` branch naming; conventional-commit prefixes
(`audit/align/feat/fix/test/docs/refactor/chore`); `main` protected and green-only;
branch deleted after landing.
