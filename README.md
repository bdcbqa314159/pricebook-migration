# PriceBook

Quantitative finance library for derivatives pricing and risk analytics. Results are validated
against closed-form solutions, published numbers, and reference implementations — never eyeballed.

PriceBook is the successor to QuantPricer. After the original codebase was lost to a hardware theft,
the decision was made to start over rather than reconstruct what was gone. The ideas, the lessons and
the intuition survived; the code didn't.

## Status: migration in progress

The library is being rebuilt **bottom-up, one oracle-backed slice at a time**, from a read-only
quarry of the previous tree. `0.x` means the migration is running; **`1.0.0` is reached exactly when
the quarry is empty.** Progress is one number, and it is deliberately unflattering:

**Drawdown: 22 / 793 quarry modules retired.** Single source: `docs/handoffs/quarry_reconciliation.md`.

## Layout

```
src/pricebook/     the library — L0 foundation → L6 shell, dependencies point DOWN only
tests/L0..L6       oracles, one directory per layer
docs/              the design corpus — 23 ratified artifacts + checkpoint reasoning
notes/             LaTeX notes on the papers and textbooks behind the methods
quarry/            the previous tree, READ-ONLY — source material, never edited
quarry/parked/     quarry topics already crossed, plus the pre-rebuild `ng` tree
verify.py          the whole audit setup: acyclic · layers · fields · debt · version · provenance
```

## Start here

1. **`CLAUDE.md`** — the law for this repo. Guardrails, not suggestions; when a change conflicts
   with it, it wins.
2. **`docs/README.md`** — where the work is, what to read in order, what is still live.
3. **`OPEN.md`** — the debt ledger. Every suppression and deferral, with a re-open trigger.

## History

This repo was re-founded at `v0.111.0` under `docs/23_repo_restart.md`. The first 111 versions —
151 pull requests, each carrying its own `RED → GREEN` commit sequence — are preserved in
[**bdcbqa314159/pricebook-legacy**](https://github.com/bdcbqa314159/pricebook-legacy) (archived,
read-only). Per-slice commit sequences live there on `refs/pull/<N>/head`.

## License

[MIT](LICENSE) — Bernardo Cohen / deLaPatada Software
