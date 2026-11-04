## Why

A `gates run ci` or `unit` with no `--task` is charged to the latest `task-start` after the handoff (`_current_task_after_handoff`, retry-budget D2). That helper never asks whether the task is already done. On a change whose tasks are all ticked and committed, a merge-time red and a main-sync red therefore count as failed attempts of the last task started. Once its fresh restart is used, a plain `gates run ci` is refused for agent and human alike, and the sanctioned `git merge --no-commit origin/main` sync route is blocked (#147).

A failed attempt measures fix attempts on the task in flight (retry-budget D1). A ticked task has nothing in flight, so a red after it is not an attempt at it.

## What Changes

- In `cmd_run`, an implicit (no `--task`) budgeted run resolves to no task when the latest started task is checked in `HEAD`'s `tasks.md`. The run is then unbudgeted and its ledger row carries `task: null`, as a run outside the loop already does.
- A run that passes `--task N.M` is budgeted exactly as today.
- `_attempt_state` is unchanged: reds after a task's tick are not filtered from its count.
- SETUP.md's retry-budget section states the new rule.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `retry-budget`: a run with no `--task` belongs to the latest started task only while that task is unchecked in `HEAD`'s `tasks.md`; otherwise it belongs to no task and is not budgeted.

## Impact

- `bin/gates` (`cmd_run`), `tests/`, SETUP.md. No shipped prompt states the implicit-task rule, so no prompt changes.
- Ships in the 0.11.1 patch.
