# Design: gates-stats

## Context

The durable ledger already exists (`harden-unattended-loop`): `gates run` appends
one JSON object per event to `.specloop/runs/<change>.jsonl`, with a fixed
10-field row shape — `ts, gate, exit, duration_ms, change, task, tree, attempt,
approved_by, sha` — where `gate` names the EVENT and several values are not gates
(`merge`, `taint`, `taint-clear`, `review`, `task-start`). The shim already has
`_ledger_path`, `_read_ledger_rows` (tolerant line-by-line JSON parsing) and
`_resolve_change_name` (branch-name default). Tests load `bin/gates` by path via
`SourceFileLoader` and call its functions directly.

Constraints that shape everything below: **zero-dep-shim** (stdlib only),
**fail-loud-gates**, determinism (a report over the same bytes must be the same
bytes), and the pinned row shape — `harden`'s "fix the row shape before writing
rows" rule means a reader must never need a field the writer didn't record.

See `proposal.md` for motivation; `specs/gate-economics/spec.md` for the
behavioral contract.

## Goals / Non-Goals

**Goals:**

- One pure, testable aggregation path: parsed rows in, stats structure out; the
  CLI layer only resolves scope, formats, and exits.
- A defined metric vocabulary that is honest about what event rows can and
  cannot support.
- Output stable enough to script against (`--json`) without freezing the human
  table's cosmetics.

**Non-Goals:**

- No new ledger fields, no writer changes, no marker changes. Stats is a pure
  reader; if a metric needs a field that isn't written, the metric is out of
  scope and the limitation is documented instead.
- No cross-repo or historical trend analysis (archived changes keep their
  ledger files; `--all` already covers "everything recorded here" — anything
  fancier is a future candidate).
- No attempt to measure host contention, token cost, or wall time between
  events' causes (edit vs. think). The rows cannot say; the report says so.

## Decisions

### D1 — Metric definitions (the honest set)

All metrics derive from four row fields (`ts`, `gate`, `exit`, `duration_ms`)
plus the attribution keys (`task`, `attempt`). Definitions, pinned here so the
tests and the `--json` schema mean one thing:

- **Gate rows vs. event rows.** A row is a *gate row* iff its `gate` value is
  not in the known non-gate event set `{merge, taint, taint-clear, review,
  task-start}`. This is deliberately a *denylist*, not an allowlist of the six
  known gates: adopters cannot declare arbitrary gate names today, but the
  non-gate event vocabulary is owned by the shim itself, so the denylist is the
  set this code controls. A future event kind added to the shim must be added
  here; the test suite pins the current set.
- **Gate time** = sum of `duration_ms` over gate rows, grouped by `gate`.
  `duration_ms` is measured by the writer around the actual command, so it is
  exact, not inferred.
- **Failed attempts** = count of gate rows with `exit != 0`, grouped by `gate`
  (and by `task` in the per-task view). `attempt` is reported as recorded but is
  not used to dedupe — it is caller-supplied and defaults to 1, so counting rows
  is the only honest count.
- **Active loop time** = sum over consecutive-row wall intervals (rows sorted by
  `ts`, ties broken by file order) of `min(interval, ...)` — excluded entirely
  when the interval exceeds the idle threshold. Default threshold: **30
  minutes**, chosen to comfortably exceed any plausible in-loop pause (a long
  gate run is bracketed by its own row, so the interval *after* a slow gate is
  small) while excluding meal/overnight gaps; overridable via
  `--idle-gap <minutes>`. The first row opens the window with zero elapsed. One
  extra term: the *last* row's own `duration_ms` (if a gate row) is added, since
  an interval only exists between rows and the final gate's execution would
  otherwise vanish.
- **Gate share** = gate time ÷ active loop time. Because `duration_ms` is exact
  and active time is gap-filtered, share can exceed 100% in a pathological
  ledger (e.g. a single-row file); the formatter clamps display, the JSON
  carries raw numbers.
- **Per-task time** = active-time computation restricted to intervals whose
  *ending* row carries that `task` id (the interval before a row is the work
  that led to it), plus the task's gate rows' overshoot handling as above. Rows
  with `task: null` end intervals in the **unattributed** bucket. `task-start`
  rows give the boundary extra precision when present but are not required.
- **What cannot be computed** (stated in the report's footer and here): token
  cost; how inter-row time was spent; concurrency effects (rows carry no host or
  lane identity); per-attempt failure causes; anything about a change whose
  loop predates the ledger. None of these justify a new row field in this
  change — `scale-gate-cost`'s `scope` lands independently and is *tolerated*,
  not required.

*Alternative considered*: deriving active time from session boundaries — rejected
because the ledger records no session identity, and inventing one would violate
the fixed row shape.

### D2 — Pure core, thin CLI

The aggregation is a pure function `stats_from_rows(rows, idle_gap_ms) -> dict`
(plus small helpers) with no I/O, no `git`, no clock. `cmd_stats` does only:
resolve scope (`--change`/branch default via the existing `_resolve_change_name`,
or `--all` = every `*.jsonl` under `.specloop/runs/`, sorted by filename), read
rows via the existing `_read_ledger_rows` **extended to also return a
skipped-line count** (today it silently drops unparseable lines — stats must
disclose them; the audit path ignores the new count), call the core, format.
Tests load the shim by path (the established `SourceFileLoader` pattern) and hit
`stats_from_rows` directly with synthetic rows — no git repo, no subprocess,
no tmp ledger needed for the math; one or two end-to-end tests cover scope
resolution and fail-loud paths against a temp directory.

*Alternative considered*: a separate `bin/` script — rejected; the shim is the
single entry point (`gates <subcommand>`) and the helpers already live there.

### D3 — Output contract

Human mode: per change, a header line (change, row count, active time, idle
threshold), a per-gate table (gate, runs, failed, time, share), a per-task table
(task, time, gate time, failed attempts) with an `(unattributed)` row when
applicable, a data-quality line (malformed lines skipped, rows without usable
`ts`), a limitations sentence, and a final pointer to
`docs/gate-economics.md`. Exact column cosmetics are NOT part of the contract
and may change; the *presence* of each section is.

JSON mode (`--json`): one document —

```json
{
  "idle_gap_ms": 1800000,
  "changes": [
    {
      "change": "<name>",
      "rows": 0, "skipped_lines": 0, "rows_without_ts": 0,
      "active_ms": 0,
      "gates": {"ci": {"runs": 0, "failed": 0, "total_ms": 0, "share": 0.0}},
      "tasks": {"1.2": {"active_ms": 0, "gate_ms": 0, "failed": 0}},
      "unattributed": {"active_ms": 0, "gate_ms": 0, "failed": 0},
      "events": {"merge": 0, "review": 0}
    }
  ],
  "totals": {"active_ms": 0, "gate_ms": 0, "failed": 0}
}
```

Keys are the schema; additional keys may be added later but never removed or
retyped. Numbers are raw (ms, 0–1 shares); formatting is the human table's job.
`--all` emits the same shape with every change in `changes[]`; single-change mode
emits `changes` of length 1 (same shape, no special case).

### D4 — Tolerance and fail-loud, reconciled

Two different failure classes get opposite treatment, deliberately:

- **Row-level oddities are tolerated and disclosed**: unknown extra fields
  (`scope`) are ignored by iterating the fields stats needs, never the row's
  full key set; a missing/None optional field degrades that row's contribution
  (no `duration_ms` → contributes 0 gate time but still a run count and a
  timestamp); an unparseable `ts` or non-object line → excluded and counted.
  Rationale: one ledger spans plugin versions; a reader that crashes on a newer
  writer's rows would make every future ledger change a breaking change.
- **Scope-level absence fails loud** (fail-loud-gates): no ledger for the
  resolved change, `--all` with no ledger files, or stats invoked on
  `main`/`master` with no `--change` → exit non-zero naming the path/branch
  looked at. An empty-but-green report would be indistinguishable from "the
  loop ran and cost nothing".

### D5 — The playbook is a doc, not a prompt asset

`docs/gate-economics.md`, ~1 page, five principles (cheapest suites first; fast
per-task `ci` as the target; expensive builds keyed on their inputs; the full
suite at the merge lane — pointing at `scale-gate-cost`'s scoped-oracle contract
in `SETUP.md` rather than restating it; one heavy gate per machine — noting the
lock itself is `worktree-native-loop`'s scope). Each principle is phrased as a
gate *shape* (`.gates.yaml` structure), never a tool. `SETUP.md` gains one
paragraph linking it; `gates stats` human output prints the path. It lives in
`docs/` with the other adopter-facing memos; it is not a skill or command
because it instructs a human tuning a manifest, not an agent in the loop.

## Risks / Trade-offs

- [Idle threshold is a heuristic constant] → It is disclosed in every report,
  overridable per invocation, and pinned in one place; the metric's *definition*
  is deterministic even though its default is a judgment call.
- [`duration_ms` inside vs. intervals between rows can double-count when a gate
  row's own duration exceeds the following interval] → Intervals are computed
  between row timestamps (each row's `ts` is written at completion), so a gate's
  execution time is inside the preceding interval, not additional to it; only
  the final row's duration is added explicitly. Tests pin this with a synthetic
  slow-gate sequence.
- [Denylist of non-gate events drifts when a new event kind is added] → A test
  asserts the denylist matches the event kinds the shim itself writes (grepping
  isn't possible from tests, but the constants live adjacent in one file and the
  test pins today's set, so adding an event kind fails a test until the author
  decides which side it belongs on).
- [`scale-gate-cost` may land scoped rows whose `ci` means "scoped ci"] → Stats
  aggregates by the `gate` name recorded; when `scope` is present it is ignored
  in v1 (tolerated per spec). A later enhancement can group by (gate, scope)
  additively under D3's "keys may be added" rule.
- [`_read_ledger_rows` gains a second return value used by one caller] → Kept
  backward-compatible by adding a new function (or keyword) rather than changing
  the audit path's call signature; the tasks pin this.

## Open Questions

- Whether `--all` should also read archived changes' ledgers from the same
  directory (they persist there today, so it already will — the question is only
  whether to *label* merged/archived changes in the report). Safe to answer at
  implementation time; the JSON schema already carries per-change `events.merge`
  counts, which is enough to tell.
