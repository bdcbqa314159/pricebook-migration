# Protocol for Cowork on this repo

You are working in **pricebook** — a quantitative finance library being rebuilt bottom-up from a
read-only quarry, one oracle-backed slice at a time. Read this file first, every session.

## Start here, in order
1. `CLAUDE.md` — the law for this repo. When anything you would do conflicts with it, it wins.
2. `.cowork/thread.md` — the prompt channel. Act on the last `Code → Cowork` entry.
3. `docs/README.md` — the artifact index, with liveness tiers (► START HERE · ► THE METHOD ·
   ► REFERENCE WHILE BUILDING · ► ARCHIVED). An artifact with no status is presumed stale.
4. The specific artifact the thread names — `docs/NN_<slug>.md`.

`OPEN.md` is the debt ledger: every suppression, shim, skip and deferral, each with a re-open
trigger. CLAUDE.md §5 — no debt is silenced silently.

## How to reply

**Re-read `thread.md` immediately before you append — not when you started work.** Both surfaces
write the same file with no locking, and a long turn is exactly how a collision happens: on
2026-10-26 Code worked ~15 minutes, appended `0003`, and Cowork had already written `0003` six
minutes in. That entry was wasted. If the last entry is newer than when you began, **act on it
first** — it may redirect or supersede what you were about to send.

Then append one entry: numbered, directed, timestamped, referencing the entry you answer, ending
with a single explicit `**Ask:**`. Never edit a prior entry — append a correction. One ask per
entry. Pointers, not pastes.

**If you do collide,** renumber only your own just-written entry, only while the other surface
cannot have read it (its timestamp precedes yours), and say so in the entry. Never renumber or edit
theirs.

**State goes to the artifact, not the thread** — update `docs/NN_<slug>.md` and `OPEN.md` in the
same turn. A fact written only into the thread is lost when the slice closes and the thread is
cleared.

## The working tree is shared state

You read the **filesystem**, not GitHub — so whatever branch Claude Code has checked out is the
world you see. A file committed on an unmerged slice branch is visible to you; the moment Code
checks out `main`, it is gone.

Consequence, in both directions:
- **Code** must not switch branches while an Ask points you at files that live only on that branch.
- **You**, if a path an entry names does not exist, must say so rather than working around it — the
  likely cause is a branch switch, not a bad pointer. Where the thread and the repo disagree, the
  repo wins; where the repo seems to have *lost* something an entry names, ask.

Precedent: thread `0005` pointed at `handoffs/AUDIT_swaption_vol_cube.md`,
`handoffs/rulings_floor_rule.md` and `handoffs/record_window_20_25_cleared.md` while all three were
committed only on `slice/27-floor-rule`. Readable then, invisible after a checkout of `main`.

## Hard limits
- **You cannot run the test suite**, so you cannot know what passes. Never mark a criterion
  verified, closed, or passing — the green-oracle gate (§4) is satisfied by execution only. Record
  what you did; Claude Code verifies and marks it.
- **Never run the release sequence.** A slice ends with one `chore(release):` commit bumping
  `pricebook.__version__` plus its `CHANGELOG.md` entry, and CI asserts the two agree (§7). Code
  owns that commit.
- **The quarry is read-only** (`quarry/`). It is never edited or deleted — it is the source material
  the migration mines for *content*, never for *structure* (§4).
- **No upward imports.** Lower layers never import higher ones; enforced per commit by the Tarjan
  SCC check. If a change seems to need one, the design is wrong — say so rather than working around.
- **Never mine the quarry for structure.** A quarry file's organisation carries no authority here.
  If a file cannot be expressed in the ratified shape, that is an immediate-stop trigger and you
  rule on it — it is never resolved by bending the new tree to the quarry's shape.

## Commits
Short, single line, project style. Two real ones from this repo's log:

```
feat(models): SABRModel.swaption_vol — the swaption smile at the engine's marked S (two capabilities)
test(models): swaption SABR oracles RED — non-canonical-underlying ATM-at-smile-minimum, Hagan, negative S
```

No co-author line. No "generated with" line. One branch per slice, `slice/<NN>-<short-kebab-title>`
off `main`; `main` is protected and advances only by squash-merged, oracle-passed slices (§8).

## What you are for
Your reach is what Claude Code lacks: Slack, Drive, email, documents, external data, scheduled and
long-running work. You also **rule** — checkpoint reports, design drift, and contract questions come
to you, because Code should not rule its own design (§6 immediate-stop triggers).

Claude Code owns code, tests, git, and verification by execution. Work needing both splits into two
items, one per surface — not one task volleyed back and forth.

## Trust boundary
You have outbound connectors, and most of this repo is tracked. Never write credentials, tokens,
internal URLs or hostnames, or client specifics into any file here, thread included. Point at where
they live instead.
