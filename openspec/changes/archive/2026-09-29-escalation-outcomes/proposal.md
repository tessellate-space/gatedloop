# Proposal: escalation-outcomes

## Why

Issue #23: the factory's success measure is *the share of shipped increments that went
from approved spec to accepted demo with no code-level human intervention*, and the
loop cannot compute it. The raw material is there — the durable ledger records every
gate run, review verdict, taint and merge — but nothing turns it into that measure:

- **A halt's reason is free text.** `tdd-implementer` ends with
  `"HALTED AT task <N.M>: <reason + what's needed>"`. Nothing classifies it, so every
  escalation stays an anecdote rather than a backlog category (*missing oracle* vs
  *weak spec* vs *stalled*).
- **A halt is not even an event.** The ledger has no row for it. Worse, the `Stop` hook
  cannot tell a halt from a task boundary: `gates discipline check-continue` continues
  the loop whenever a change branch has an unchecked task and a clean tree — which is
  exactly the state `tdd-implementer` §3 is told to halt in. A clean halt with tasks
  remaining is, to the hook, an invitation to continue.
- **Human interventions leave no trace.** The interactive "pause and ask" after two
  red attempts (`skills/tdd-apply/SKILL.md` §5e/§6/§7) and a human fixing a lane by
  hand are both invisible; a change that needed three human turns and one that needed
  none look identical in the ledger.
- **`gates stats` reports cost only** — gate minutes, failed attempts, active time.
  It does not report throughput or autonomy.

So we cannot answer *what fraction of changes ran hands-off, and what stopped the
rest?* — the one question that tells a team which oracle or spec pattern to invest in
next.

## What Changes

- **A closed set of escalation causes**, held in one place in the shim:
  `missing-oracle`, `weak-spec`, `oracle-conflict`, `stalled`, `environment`, `other`
  (which must carry free text). Extending the set is a spec change, not a prompt edit.
- **A halt becomes a ledger event.** `gates halt record <cause> --task <N.M>
  [--detail …]` appends a `halt` row carrying the cause. An unknown or missing cause,
  or `other` without detail, is refused with the accepted set named.
- **A halt is only a halt when recorded.** `gates discipline check-continue` stops
  continuing the loop when the change's ledger carries a `halt` row with no later
  `task-start` — so the Stop hook honours a recorded halt and re-enters an unrecorded
  one. The cause is not bookkeeping the agent may skip; it is how a halt takes effect.
- **Interventions become ledger events, detected in code where possible.**
  - `ask` — a `PreToolUse` hook on the `AskUserQuestion` tool appends an
    `intervention` row when a change branch is checked out. It records; it never
    denies.
  - `human-commit` — every ledger row gains a `session` field (`agent` when the
    `CLAUDECODE` session marker is present, else `human`, the same discriminator the
    git-layer commit hook already uses). The existing Stop-hook audit, which already
    joins each new commit's tree to green-`ci` rows, classifies a commit whose only
    green-`ci` evidence was written outside a session as a `human-commit`
    intervention. The merge gate runs that audit before its taint check, so the
    classification is complete at merge time.
- **The implementer's final report gains `cause`.** The report is an echo of the
  recorded `halt` row, never the record itself; the agent records first, then reports.
  Existing halt situations map onto the set (§1 ambiguity → `weak-spec`; §5 red after
  two attempts → `stalled`; §6 exit 75 → `environment`; a disputed finding or two gates
  disagreeing → `oracle-conflict`; a scenario no declared gate can decide →
  `missing-oracle`).
- **`gates stats --outcomes`** — the north-star view over the same ledger: per change,
  a terminal state (`merged` / `halted` / `in-progress`), halts by cause, interventions
  by kind, taints, and **hands-off** (merged with zero halts, interventions or taints);
  with `--all`, the hands-off share of merged changes, breakdowns by cause and kind,
  and a per-month trend. Human table by default, stable `--json` shape, same
  determinism and fail-loud rules as the existing report.

No new gate, no new LLM agent, no stack command anywhere. The terminal event is
`merged` for now; the companion change for issue #25 (an attested acceptance gate)
will make *accepted* the terminal event where a project declares that policy, and this
proposal leaves that seam explicit rather than pre-building it.

## Capabilities

### New Capabilities

- `escalation-record`: the closed cause vocabulary; the `halt` and `intervention`
  ledger row kinds, their writers and refusals; the `session` field on every row; how
  an `ask` is detected by hook and a `human-commit` by the audit; and what the record
  discloses when it cannot classify.

### Modified Capabilities

- `loop-enforcement`: the Stop hook stops continuing on a recorded halt (today it
  cannot distinguish one from a task boundary); the implementer's final report carries
  the recorded `cause`; the post-hoc audit additionally classifies human-gated commits
  as interventions and the merge gate runs it; the ledger row shape gains `session`.
- `gate-economics`: a new requirement for `gates stats --outcomes` (terminal-state
  derivation, the hands-off definition, breakdowns, trend, JSON shape and data-quality
  disclosure).

## Impact

- `bin/gates` — `HALT_CAUSES`; `cmd_halt` / `cmd_intervention` (`record`); two new
  fields `cause`, `detail` and one new field `session` appended to `LEDGER_ROW_FIELDS`
  (union-tuple convention, `None` on rows that do not use them); `session` set
  centrally in `_append_ledger_row`; `halt`/`intervention` added to `NON_GATE_EVENTS`;
  `check-continue` reads the halt row; `cmd_audit` appends `human-commit` rows;
  `cmd_stats` gains `--outcomes` (a second pure aggregation next to `stats_from_rows`).
- `hooks/record-ask.sh` (new, `PreToolUse` on `AskUserQuestion`) and one entry in
  `hooks/hooks.json`; `hooks/gate-merge.sh` runs `gates audit` before `taint check`.
- `agents/tdd-implementer.md` — the record-before-report rule, the cause mapping, the
  seventh report field. `skills/tdd-apply/SKILL.md` — one sentence at each "pause and
  ask" point. `SETUP.md`, `AUTOMATION.md` — the report shape and the new stats mode.
  `docs/candidates.md` — the `gates audit` entry notes that `--outcomes` now supplies
  the run-history half it said was missing.
- `tests/` — new cases for the cause set and refusals, the halt-aware `check-continue`,
  the `session` field, the audit's `human-commit` classification, and the `--outcomes`
  aggregation; the existing stats, ledger, audit and taint suites must keep passing.
- Adopters: additive. Rows written before this change read as `session: None` and are
  disclosed as unclassifiable, never counted as agent or human. Existing halts that were
  never recorded are simply absent from the outcomes view, which the report says.
- Rejection test: authors no artifact, names no stack command; makes "a halt stops the
  loop" and "every escalation says why" enforceable, and gives a team the metric that
  tells it what to build next — a `close` job and a `climb` job, both ours.
