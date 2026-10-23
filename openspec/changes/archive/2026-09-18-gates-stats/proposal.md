# Proposal: gates-stats

## Why

Field report #18 measured a week of real use (15 fully-instrumented merged changes)
and had to hand-parse `.specloop/runs/*.jsonl` to learn the one thing that matters
for tuning: **gate execution is the dominant cost** (one 25-task change spent 143 of
268 active minutes in gates, ~5–6 failed gate attempts per change). The durable
ledger already records every gate event with timestamps and durations — Specloop
writes the data and then makes every adopter rediscover the same jq incantations to
read it. The analysis should ship as a built-in report, and the "now what" — how to
restructure gates once the bottleneck is visible — should ship as a short playbook.

This is issue #18 **items 1 and 5 only** (see Non-scope).

## What Changes

- **`gates stats`** — a new shim subcommand: a deterministic, stdlib-only report
  over the durable ledger (`.specloop/runs/<change>.jsonl`). Per change: active
  loop time, per-task time, failed-gate-attempt counts, and per-gate share of
  active time. Scope is one change (`--change`, defaulting to the current branch
  like the rest of the shim) or `--all` for every ledger under `.specloop/runs/`.
  Output is a human-readable table by default and `--json` with a stable schema.
  The aggregation is designed **on the row fields that exist today**
  (`ts, gate, exit, duration_ms, change, task, tree, attempt, approved_by, sha`);
  no new row field is added, and what today's rows cannot answer is stated in the
  report and the design rather than approximated (see design.md).
- **"Active loop time" gets a defined, deterministic meaning**: rows are events,
  not sessions, so active time is the sum of inter-row wall intervals with gaps
  above an idle threshold excluded (default fixed in design, overridable by flag).
  Rows without a `task` id are reported as *unattributed*, never guessed.
- **A scaffolding playbook** (`docs/gate-economics.md`): the adopter-facing
  answer to what `gates stats` reveals — cheapest suites first, target a fast
  per-task `ci`, expensive builds keyed on their inputs, full suite at the merge
  lane, one heavy gate per machine. Principles and gate shapes only; no named
  tool anywhere (**stack-agnostic-prompts** binds). Linked from `SETUP.md`, and
  the `stats` report points at it as the next step.
- **stdlib-only `unittest` coverage** for the aggregation — it is branching
  Python, and this repo's rule is that branching Python gets tests while prompts
  stay untested.

## Non-scope

Stated explicitly so the field report's other items are not silently dropped:

- **#18 item 2** (changed-file context for `ci`) and **item 4** (two-tier
  fast/full `ci` contract) are already delivered by the merged `scale-gate-cost`
  change (`openspec/changes/scale-gate-cost/proposal.md`): surface-scoped
  `ci`/`unit` oracles selected by the hot set, with the unscoped `ci` remaining
  the last word at merge. This change does not duplicate any of it.
- **#18 item 3** (cross-worktree gate lock) belongs to the sibling
  `worktree-native-loop` change, not here.

## Ordering

Independent of the other in-flight changes. One compatibility note:
`scale-gate-cost` records a `scope` on marker/ledger rows — `stats` MUST tolerate
rows both with and without that field (and, per the ledger's own comment, any row
whose extra keys it does not recognize), since one ledger file can span both eras.

## Rejection test

- Does it make a stated guarantee enforceable/inspectable? **Yes** — the ledger is
  the oracle record Specloop itself writes; `stats` is the read-back that makes it
  usable without hand-parsing. Ours.
- Does it get a team running faster? **Yes** — the playbook is climb-surface work:
  it moves an adopter from "gates are slow" to a tuned manifest. Ours.
- Does it author an artifact or know a stack command? **No** — the report reads
  Specloop's own file; the playbook names gate shapes, never tools.

## Capabilities

### New Capabilities

- `gate-economics`: reading the gate-cost story back out of the durable ledger
  (`gates stats` — metrics, scope, output contract, tolerance rules) and the
  stack-agnostic playbook that tells an adopter what to do about it.

### Modified Capabilities

<!-- None. The ledger's write path, row shape, and every existing subcommand are
     untouched; stats is a pure reader. -->

## Impact

- `bin/gates`: new `cmd_stats` + aggregation helpers (stdlib-only; reuses
  `_read_ledger_rows` / `_ledger_path`); argparse wiring for `stats`.
- `tests/`: new test module covering the aggregation (interval/idle-gap math,
  failed-attempt counting, per-gate share, unattributed rows, unknown-field and
  `scope`-field tolerance, malformed-line handling, `--json` schema).
- `docs/gate-economics.md` (new), `SETUP.md` (link + one-paragraph pointer).
- No schema change to `gates.schema.json`, no new ledger fields, no hook changes,
  no prompt-asset changes beyond the SETUP pointer.
