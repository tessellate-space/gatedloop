# Design: escalation-outcomes

## Context

See proposal.md — Why. The mechanics this design builds on, all in `bin/gates` and
`hooks/`:

- **One ledger writer.** `_append_ledger_row` fills a fixed shape, `LEDGER_ROW_FIELDS`,
  and every row kind goes through it. The shape is extended by appending fields as an
  additive union (fix-marker-mechanics D7); a row that does not use a field carries it
  as `None`, so old readers never see a shape they do not know.
- **Event rows already share the gate row shape.** `merge`, `taint`, `taint-clear`,
  `review` and `task-start` are recorded in the `gate` column and excluded from gate
  arithmetic by `NON_GATE_EVENTS`. `stats_from_rows` is a pure function over parsed
  rows; `cmd_stats` only resolves scope, reads and formats.
- **The Stop hook's continue check is blind to halts.** `discipline check-continue`
  continues on (change branch ∧ unchecked task ∧ clean tree). `tdd-implementer` §3
  requires exactly that state on a halt. Today nothing distinguishes the two.
- **The audit already walks new commits and joins trees to green-`ci` rows** at every
  Stop; it taints on a miss and keeps a per-worktree cursor so it never re-walks.
- **`CLAUDECODE` is the session discriminator.** `templates/git-hooks/pre-commit`
  exits 0 without it; the spec calls this scoping deliberate, not a skip.
- **Hooks fire on tool calls.** `hooks.json` already matches `Bash`, `Write`,
  `Edit|Write`, `Stop`, `PreCompact`. A `PreToolUse` matcher on `AskUserQuestion` is
  the same mechanism pointed at the one tool call that *is* a human turn.
- Constraints: `zero-dep-shim`, `fail-loud-gates`, `stack-agnostic-prompts`, the O(1)
  hook budget (no gate re-runs under a hook), and that the report shape `{change,
  tasks_done, tasks_total, branch, gates, outcome}` is documented in SETUP.md and
  AUTOMATION.md for headless callers.

## Goals / Non-Goals

**Goals:**

- A halt has exactly one cause from a closed set, written to the ledger by the shim.
- A recorded halt is what stops the loop; an unrecorded one does not stick.
- Human turns are detected in code where a hook or the audit can see them.
- `gates stats --outcomes` computes the hands-off share from ledger rows alone.

**Non-Goals:**

- Any change to what `ci`, `live-check` or the merge gate require.
- Acting on a cause (drafting a spec delta on `weak-spec`, retrying on `stalled`) —
  issues #27 and #29.
- An acceptance event; the terminal event stays `merged` until issue #25 lands.
- Detecting a human edit that was never committed, or a human turn that went through
  neither the question tool nor a gated commit. The report says so instead.

## Decisions

### D1: One constant, six causes, `other` must explain itself

`HALT_CAUSES = ("missing-oracle", "weak-spec", "oracle-conflict", "stalled",
"environment", "other")` next to `REVIEW_VERDICTS`. `gates halt record` validates
against it and refuses `other` without `--detail`. The set is the one from issue #23,
unchanged: each member names *what to invest in* (an oracle, a spec, a conflict rule,
an attempt budget, an environment), and `other` exists so an honest agent is never
forced to mislabel — at the price of explaining.

**Alternative — free text plus a suggested vocabulary in the prompt:** rejected. A
suggestion is not a category; `--outcomes` would be grouping strings, and the first
run to write `stalled (ci)` breaks the count.

**Alternative — a richer taxonomy (sub-causes, severities):** rejected for now. Six
buckets is what a team can act on; a finer split is an extension to this spec once
the coarse counts show where the mass is.

### D2: A halt is a ledger row, and the shim is its only writer

`gates halt record <cause> --task <N.M> [--detail]` appends `gate: "halt"`,
`exit: None`, `duration_ms: 0`, `tree: <head tree>`, `cause`, `detail`. Two fields,
`cause` and `detail`, are appended to `LEDGER_ROW_FIELDS`; `halt` and `intervention`
join `NON_GATE_EVENTS` so `stats_from_rows` never counts them as gates and
`_green_ci_trees` can never match them (`gate != "ci"`). The change is resolved the
way every other subcommand resolves it (`--change`, else the branch; `main`/`master`
→ refuse, fail-loud).

The row records the head tree rather than the staged tree because a halt is defined
to happen at a clean task boundary (implementer §3); the head is the boundary.

**Alternative — encode the cause in the report only:** rejected; the report is prose
the agent emits, the ledger is what survives the squash and what `--outcomes` reads.

**Alternative — reuse `outcome` (the precondition row's discriminator) for the
cause:** rejected. `outcome` says *what kind of row this is* on a gate row; `cause`
says *why the loop stopped* on an event row. Overloading one field for two questions is
how the next reader guesses wrong.

### D3: A halt is only a halt when recorded — the continue check reads the ledger

`discipline check-continue` gains one more condition: after the existing three, read
the change's ledger and return non-zero (printing the cause) when the latest `halt`
row is newer than the latest `task-start` row. `gates task start` already appends a
`task-start` row at every task's beginning (§5a), so resuming lifts the halt with no
new command.

This is the decision that turns the cause from bookkeeping into enforcement. Today a
clean halt with tasks remaining is re-entered by the Stop hook — the agent says
"HALTED", the hook says "continue from task 2.3". After D3 the loop honours a
recorded halt and re-enters an unrecorded one, which is the fail-loud shape for "the
shim rejects a halt with no cause": the halt does not take.

Ordering by row position in the file, not by `ts` — the ledger is append-only and
rows are written in event order; comparing timestamps would make the check depend on
clock monotonicity for no gain.

**Alternative — a halt marker under `.git/` like the gate markers:** rejected. A halt
must survive the session (a fresh agent resumes from it), and the marker store is
per-worktree and ephemeral by design. The ledger is durable and already committed with
the task.

**Alternative — make the Stop hook parse the transcript for "HALTED":** rejected;
that enforces phrasing, the anti-pattern the git-layer hook exists to avoid.

### D4: An `ask` is recorded by a `PreToolUse` hook on the question tool

New `hooks/record-ask.sh`, registered in `hooks.json` under `PreToolUse` with matcher
`AskUserQuestion`. It resolves the repository like the other hooks (`gates hook
git-cwd`), and when a change branch is checked out calls
`gates intervention record ask --detail "<first question, truncated to 200 chars>"`.
It always exits 0: recording never gates a human turn, and a failed write is reported
on stderr and swallowed for the tool call's sake.

The interactive loop's "pause and ask" *is* an `AskUserQuestion` call, so the tool
call is the event and the hook sees it without the prompt having to remember. The
prose fallback (`gates intervention record ask` by hand, one sentence at §5e/§6/§7 of
the skill) covers a pause that does not go through the tool.

Self-reporting is acceptable here in a way it is not for approval: an `ask` row can
only lower a run's autonomy score. Nothing an agent writes here can make a run look
more hands-off than it was.

A question asked on a change branch for a reason unrelated to the loop still records.
That is correct: it was a human turn in that change's timeline. The report counts
turns, not intentions.

### D5: A `human-commit` is derived from a `session` field, by the audit

Two parts:

1. **`session` on every row.** `_append_ledger_row` sets
   `row["session"] = "agent" if os.environ.get("CLAUDECODE") else "human"`. Set in the
   writer, not by callers, so no row kind can omit it. `session` is appended to
   `LEDGER_ROW_FIELDS`. It reuses the exact discriminator the git-layer hook uses, so
   the two mechanisms agree about what a session is. A row without the key is
   *unknown* — never coerced.

2. **Classification in the audit.** `cmd_audit` already computes, per new commit,
   whether its tree has a green-`ci` row. It now keeps the matching rows: none →
   taint (unchanged); all `session == "human"` → append `gate: "intervention"`,
   `cause: "human-commit"`, `sha`, `tree`; any `agent` → nothing; any `None` among
   them with no `agent` → nothing, counted unclassifiable by `--outcomes` (it can
   recompute the same join from the ledger and the branch, or the audit can append a
   disclosure — implementer picks; the spec requires only the count). The existing
   SHA-dedupe set is extended to intervention rows so a commit is classified once.

3. **The merge gate runs the audit first.** `hooks/gate-merge.sh` calls
   `gates audit >/dev/null 2>&1 || true` before `gates taint check`. The audit is a
   `rev-list` plus a ledger read — no gate re-run — so it fits the hook budget, and
   it closes a real gap: a commit created after the last session stop is otherwise
   neither tainted nor classified when the merge is decided.

Why not detect the commit itself? The git-layer hook is a no-op outside a session by
spec, and a `PreToolUse` hook only sees the agent's commands. The one durable trace a
human leaves when they *follow the rules* is the ledger row their own `gates run ci`
wrote — and following the rules is the case worth classifying. The one who does not
follow them is already tainted.

**Alternative — author/committer identity:** rejected. Agents commit under the same
git identity as their operator, and the audit spec forbids identity from exempting a
commit; using it to classify would invite the same drift.

**Alternative — a `human-commit` row written by the git-layer hook:** rejected; the
hook is not running when the human commits. Making it run outside sessions would
reverse a deliberate scoping decision for a metric's convenience.

### D6: The report echoes the record

`agents/tdd-implementer.md`: (a) a seventh JSON field `"cause"`; (b) the rule "before
emitting a HALTED report, run `gates halt record <cause> --task <N.M>`; the report's
`cause` is that row's cause"; (c) a cause table for the halt situations the prompt
already describes (§1 → `weak-spec`; §5 two red attempts → `stalled`; §6 exit 75 →
`environment`; a finding the agent disputes or two gates disagreeing →
`oracle-conflict`; a scenario no declared gate can decide → `missing-oracle`).

The order matters and D3 enforces it: an agent that reports without recording is
re-entered by the Stop hook, so the record-first rule is backed by something.

SETUP.md and AUTOMATION.md list the report fields; both gain `cause`. The `gates` /
`outcome` fields are unchanged so existing headless parsers keep working.

### D7: `--outcomes` is a second pure aggregation beside `stats_from_rows`

`outcomes_from_rows(rows) -> dict` (no I/O, no git, no clock) computes per change:
`terminal` (`merged` if any `merge` row; else `halted` if the last `halt` is after the
last `task-start` by file order; else `in-progress`), `hands_off` (merged ∧ no `halt`
∧ no `intervention` ∧ no `taint`), `halts` by cause over `HALT_CAUSES` (unknown →
`data_quality.malformed_halts`), `interventions` by kind, `taints`, `first_ts`.
`cmd_stats` branches on `--outcomes` for reading and formatting only, exactly as it
does today; `--all` composes the aggregate (hands-off share as numerator/denominator/
value-or-null, breakdowns, per-month trend keyed on `first_ts`). JSON is one
`json.dumps(..., sort_keys=True)` document.

Taints count against hands-off because a taint is a commit that bypassed the loop's
own gate — whoever made it, the run was not the loop running itself.

`in-progress` deliberately includes a change whose last event is a green gate with
tasks remaining; the ledger cannot see `tasks.md` and the report should not pretend
to. Terminal states come from rows only.

**Alternative — extend `stats_from_rows` with the new keys:** rejected. The existing
function's contract is byte-stable output for the same input; adding keys changes
every existing `--json` consumer's document for a view they did not ask for.

### D8: What this is not — `gates audit` in `docs/candidates.md`

The candidate `gates audit` scores *coverage* (which oracles exist, per phase).
`--outcomes` measures *throughput* (what stopped runs). The candidates entry says half
its signal is run history that did not exist yet; this change supplies that half, and
the entry gains one sentence saying so. It is not promoted: scoring rungs still needs
calibration across projects, which is a separate objection this change does not touch.

## Risks / Trade-offs

- [An agent records `other` for everything] → `other` requires detail, `--outcomes`
  shows `other` as its own bucket, and a high `other` share is itself the signal that
  the set needs a member. Better a visible `other` than a mislabel.
- [D3 changes when the Stop hook continues] → It only *stops* continuing in one new
  case (halt row newer than task-start). Every case that continues today still
  continues unless the agent recorded a halt, which is what the agent asked for.
  Pinned by tests on `check-continue`.
- [A stale `halt` row blocks a legitimate resume] → Resume begins with `gates task
  start` (§5a), which appends the `task-start` row that lifts it. The denial message
  names that command.
- [`CLAUDECODE` leaks into a human's shell (a terminal spawned from the session)] →
  Their `gates run` rows read `agent`. The report can only *under*-count human
  commits, never over-count them; the limitations line says human-commit detection
  depends on the session marker.
- [The audit runs in the merge hook] → It is a `rev-list` and a file read, bounded by
  the branch's commit count; no gate is re-run. It already runs on every Stop with the
  same inputs.
- [The `AskUserQuestion` hook fires for onboarding's many questions] → Onboarding runs
  on the merge target, where the hook is a no-op by branch check.
- [Adding three fields to every row grows the ledger] → Three short keys per row;
  negligible against `tree` and `approved_by`, and the shape rule says append, never
  infer.

## Migration Plan

Ship in the next plugin release. Additive everywhere: new subcommands, new hook, three
new row fields, one new stats mode, one new report field. No manifest change. Rows
written before the release read as `session: None` and are disclosed. Rollback is
reverting the release; old rows with the new fields are ignored by old readers via the
fixed-shape lookup.
