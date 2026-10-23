# Proposal: scale-gate-cost

## Why

Field-trial issue #13, measured across six autonomous runs on one adopting project:
300–500k tokens and 1–3 hours per change, of which ~60–100 minutes is gate execution —
the aggregate `ci` (typecheck + three unit suites + a compose build) runs in full for
every red-proof and every commit, regardless of what the task touched. Token growth is
dominated by convention review running inline in the implementer's context and by raw
gate output accumulating there; the field agents independently invented `| tail`
because nothing else taught it. The manifest already computes hot surfaces per diff
for rules and live-checks; the commit oracle is the one consumer of that selection
that doesn't exist yet.

## What Changes

- **Surface-scoped oracles.** `surfaces[]` MAY declare per-surface overrides for the
  `ci` and `unit` gates. `gates run ci`/`unit` selects by the staged diff's hot
  surfaces with the same deterministic selection that already drives rules and
  live-checks, with a strict **err-full** rule: the scoped command runs only when the
  hot set is exactly one surface that declares the override (catch-all `**` surfaces
  are ignored for this decision); any unmatched file, multi-surface diff, or missing
  declaration falls back to the global gate. Markers and ledger rows record which
  oracle ran.
- **Full `ci` is always the last word.** Change completion (the pre-merge step)
  requires an unscoped green `ci` on the branch head; a scoped marker can satisfy a
  per-task commit but never the merge.
- **Quiet-on-green output in the shim.** `gates run` captures gate output to a file
  and prints a one-line summary (gate, scope, duration, exit) on success and the full
  output on failure, with `--verbose` restoring today's behavior. The hygiene every
  adopter's agent currently rediscovers becomes the default, in code.
- **Review delegation hardened.** `skills/tdd-apply/SKILL.md` and
  `agents/tdd-implementer.md` explicitly require the convention review to run as the
  `convention-review` subagent — never inline — keeping rules prose and diff text out
  of the long-lived loop context.
- **Task batching is explicitly deferred** to `docs/candidates.md`: it blurs the
  done ⟺ committed resumability invariant, task granularity belongs to the OpenSpec
  schema, and its benefit shrinks once the above land.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `gate-binding`: surfaces may bind scoped `ci`/`unit` oracles selected by the
  existing hot-set rule with a pinned err-full direction; markers record oracle scope
  and the merge requires an unscoped green; `gates run` reports one line on green and
  everything on red.

## Impact

- `bin/gates`: scoped-gate selection (reusing `hot_surfaces`), marker/ledger `scope`
  field, output capture; `schema/gates.schema.json`: per-surface gate overrides;
  `tests/`: selection, fallback, marker-scope, and output-mode coverage.
- `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`: delegation mandate + use
  of the quiet default (no more `| tail` folklore).
- `SETUP.md`: the scoped-oracle contract and its err-full rule; `docs/candidates.md`:
  the batching entry.
- Ordering: builds on `unblock-parallel-planning`'s `discipline check-commit` (merged,
  PR specloop PR 32) — the commit gate keeps one entry point; scoped markers flow through it.
- Adopter impact: opt-in per surface; a manifest with no overrides behaves exactly as
  today. The rejection test holds: the *bindings* stay in `.gates.yaml`; Specloop adds
  only selection, recording, and reporting.
