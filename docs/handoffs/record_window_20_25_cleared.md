# Record — the slices-20–25 window, cleared by execution

**Date:** 2026-10-26 · **Recorded by:** Claude Code (execution; Cowork cannot run the suite)
**Answers:** `rulings_floor_rule.md` §"Note on confidence in the slices-20–25 window"

## The claim being discharged

Because CI ran `verify.py tests --layer 0`, "all gates green" across slices 20–25 meant **L0 green
only** — 177 of 366 tests. The ruling is explicit that it does not itself clear that window:

> *This ruling does not itself clear the window — only execution does (I cannot run the suite).
> The full 366 must be **run green under the un-truncated collector** before the window is trusted;
> that is Code's to verify and record, not mine to mark.*

## The evidence

The restart (artifact 23) removed the `--layer` ceiling in the **initial commit**, so every CI run on
the new repo has used the un-truncated collector. Three independent runs, each on both OSes:

| run | event | sha | ubuntu | windows | collected |
|---|---|---|---|---|---|
| `40246231753` | push → main | `944063f` | success | success | **366 passed** |
| `40246615523` | pull_request #1 | `508bc7f` | success | success | **366 passed** |
| `40248710380` | push → main (squash) | `6351cdb` | success | success | **366 passed** |

Locally, same tree, deps pinned to the CI versions (`numpy 2.4.3` / `scipy 1.17.1`): **366 passed**,
`0 failed`, `0 errors`.

**Window cleared.** Every oracle landed in slices 20–25 — SABR caplet smile, SABR smile calibration,
cap/floor + the `cap_ladder` atom, multi-law caplet, law-generic implied-vol inversion, swaption SABR
on the threaded-forward signature — has now executed green on Linux and Windows under the full
collector. No oracle expected value was touched by the restart (artifact 23, A1: 2035 files
byte-identical, 0 unexplained), so these are the same assertions those slices committed, merely run
for the first time by the gate that claimed to be running them.

## What this does and does not establish

**Does:** every test those six slices wrote passes, on both platforms, under a collector that
collects all of them. The historical gate's silence is replaced by execution.

**Does not:** make those slices' *oracles* stronger than they were. Execution clears truncation, not
oracle quality. Audit #10's lesson stands separately — a self-consistency oracle can pass while the
decomposition is wrong, which is why §6's first clause exists and why the slice-B audit
(`AUDIT_swaption_vol_cube.md` F1) flags the cube calibration's node-drop before it is built rather
than after.

**Standing from here:** `TEST_FLOOR = 366` in `verify.py`, CI RED below it, raised in the same commit
as any slice that adds a tier. The window cannot silently reopen.
