# Design

## Context

See proposal.md for motivation. What exists today:

- Every ledger row is filled out to `LEDGER_ROW_FIELDS` (`bin/gates`, `_append_ledger_row`); the row type is the `gate` field. `duration_ms` is the only cost-like field. `session` is `agent` when `CLAUDECODE` is set.
- `task-start` rows mark where a task began (`gates task start`, written by the loop before RED). The retry budget already counts rows per task from the ledger and refuses in `cmd_run` with exit 1 (`_budget_refusal`).
- `hooks/gate-commit.sh` (PreToolUse on `git commit`) and `hooks/continue-loop.sh` (Stop) read the hook's JSON on stdin. Claude Code's hook input carries `session_id` and `transcript_path`. The git-layer `templates/git-hooks/pre-commit` has no hook input at all.
- A Claude Code transcript is JSONL. Each `assistant` entry carries `timestamp`, `message.model`, `message.usage` with `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, and `isSidechain`/`agentId` for subagent turns. Subagent transcripts may also live in sibling files under the session's directory.
- `gates stats` reads rows by `change` and attributes by `task`, with an explicit unattributed bucket; `--outcomes` resolves halts against `HALT_CAUSES`; `--epic` rolls children up.

## Goals / Non-Goals

**Goals:**
- Tokens per task in the same ledger, written by the same hooks, with the same attribution discipline as time.
- Nothing stored but counts; nothing fails because a source is missing.
- A budget with the same shape as the attempt cap: counted from the ledger, refused in `gates run`, escalated with a named cause.

**Non-Goals:**
- Per-gate-run tokens. A gate run is a command; the tokens around it belong to the task.
- Wall-clock cost of gates (already `duration_ms`), model routing, or any spend control inside the host.
- A shipped price list, or any currency conversion.
- Reading other hosts' transcripts in this change. The row shape leaves room (`source`); the reader set is one.

## Decisions

### D1. One row type, `usage`, written at two moments

A `usage` row carries `task`, `window` (`from`, `to` as ISO timestamps), `messages`, `source`, and `tokens`: a map of model name to `{input, output, cache_read, cache_write}`. Totals are derived by readers, never stored.

Two writers, same subcommand:
- **At the gated commit.** `hooks/gate-commit.sh` passes the hook's `transcript_path` to `gates usage record --task <inferred> --transcript <path>` after `tests check` passes and before the commit proceeds. The task is the one `check-commit` already resolves (latest `task-start`).
- **At session stop.** `hooks/continue-loop.sh` calls the same command for the task in flight before it decides whether to continue. A task that ends in a halt is costed here.

Alternative considered: one row per `gates run`. Rejected: a run has no transcript access (Bash gets no hook input), and tokens are spent between runs, not inside them.

### D2. The window, and why it cannot double count

A record's window starts at the later of the task's latest `task-start` row and the task's latest `usage` row, and ends now. Only assistant entries whose timestamp falls inside the window are counted. Two flushes with nothing in between produce a second row with zero counts; the sum is unchanged. A restart (`gates attempt restart`) does not reset the window, because its tokens were spent on the same task.

Entries with no `task-start` before them (the authoring phase, a session running no task) are recorded under `task: null` at session stop, so the unattributed bucket exists for tokens as it does for time.

### D3. The reader is a host adapter behind `source`

`source` is a closed string: `claude-code-transcript`, `no-transcript` (the hook input carried no path, or the writer is the git-layer hook, which has none), `unreadable-transcript` (the file exists but did not parse). The reader for Claude Code walks the main transcript and any sibling JSONL files under the session's directory that carry the same `sessionId`, so subagent turns are counted. A second host adds a second adapter and a second `source` value; nothing else changes.

Alternative considered: storing the transcript path and computing lazily in `stats`. Rejected: transcripts are pruned and move between machines; the ledger is tracked and must be self-contained.

### D4. Prices are a binding in the manifest

```yaml
economics:
  currency: USD
  prices:
    "<model-name>": { input: 3, output: 15, cache-read: 0.3, cache-write: 3.75 }
```

Values are per million tokens. `gates validate` checks the shape (non-negative numbers, a currency string) and nothing about the names. `gates stats --cost` multiplies per model and names any recorded model with no price. Without the block, `--cost` prints tokens and says no prices are declared. This is the same move as a gate body: the shim owns the contract, the adopter owns the binding.

### D5. The budget mirrors the attempt cap

`loop.token-budget` (positive integer, optional, no default) is checked in `cmd_run` beside the attempt check, for task-bearing `unit` and `ci` runs only: sum every `usage` row for the change; at or above the budget, refuse with exit 1 and a message naming the budget, the recorded spend, the fact that the in-flight task is counted at its commit or stop, and `gates halt record budget --task <N.M>`. `--full` is never budgeted (the merge lane must be able to prove the head). `budget` joins `HALT_CAUSES`; `--outcomes` counts it; the cause table in the implementer prompt and the skill gains a row.

Alternative considered: a per-task budget. Deferred: the attempt cap already bounds a task; the question a team asks is per change.

### D6. Stats

`gates stats` adds a `tokens` column per task (sum across models) and a per-model line per change, plus an `unrecorded` disclosure: tasks with no usage row and the first/last row span not covered by any window. `--json` adds `tokens` with per-task, per-model and unrecorded sub-keys. `--epic` sums children. The `gate-economics` disclaimer is narrowed to what still cannot be answered.

### D7. Git-layer hook

`templates/git-hooks/pre-commit` has no transcript. It records `source: no-transcript` so that a commit made through the git layer still leaves a row and the stop flush covers the window. The hook's `CLAUDECODE` guard is unchanged here.

### D8. Adoption

One catalogue item, `token-budget`, since the next minor: question "Cap a change's token spend?", recommended answer "No budget: record only" (`declined` is the recommended answer, deliberately), alternative "Yes: I set `loop.token-budget`". Detector: `loop.token-budget` present in the manifest.

## Risks / Trade-offs

- [The transcript format is undocumented and may change] → the adapter reads four usage fields and a timestamp, tolerates missing ones, and records `unreadable-transcript` rather than failing; a fixture transcript in `tests/` pins the shape read today.
- [Subagent transcripts in separate files may be missed] → the reader counts what it finds and the row's `messages` count makes an undercount visible; the stats disclosure says which tasks look sparse.
- [The budget lags the in-flight task] → stated in the refusal and the docs; a Stop flush narrows the lag to one session.
- [A price table in a tracked manifest goes stale] → prices affect `--cost` only; tokens are the stored truth.
- [The pending plugin rename changes hook and status names] → this change names only `gates` subcommands and manifest keys; none carry the plugin name.

## Open Questions

None that change the specs or tasks. Whether to read a second host's transcript is a later change with its own adapter.
