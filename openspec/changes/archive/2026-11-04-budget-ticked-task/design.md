## Context

`cmd_run` budgets `unit` and `ci` (`BUDGETED_GATES`) for a change unless `--full` is passed. With no `--task`, it takes `_current_task_after_handoff(rows)`: the latest `task-start` row after the latest full handoff. It then calls `_budget_refusal` with that task and writes the task onto the run's ledger row. Nothing consults `tasks.md`'s tick state, though `_checked_task_ids` and `_blob_at` already read it from any commit (unblock-authored-lock D2's completion walk uses them).

The issue's sequence (#147): every task of `room-occupants` ticked and committed; a merge-time `ci` red and a later main-sync `ci` red were both charged to task 2.2, the last one started. With `loop.attempts: 2` and the restart used, `gates run ci` after `git merge --no-commit origin/main` refused with "halt `stalled`". The budget ignores `CLAUDECODE`, so a human was refused too.

`_current_task_after_handoff` has two other callers: `_tests_check_problems`' `current` (the lock) and `gates usage record`'s attribution. Neither is a budget, and neither is changed here.

## Goals / Non-Goals

**Goals:** a run with no `--task` after the task in flight is done spends nobody's budget, and a fully ticked change's syncs and merges can run `gates run ci`.

**Non-Goals:**
- changing `_attempt_state`'s counting window;
- changing usage attribution or the lock's notion of the current task;
- budgeting the merge's unscoped `ci` (`full`), which stays unbudgeted.

## Decisions

### D1. An implicit run after a ticked task belongs to no task

In `cmd_run`, when `--task` is absent and `_current_task_after_handoff(rows)` returns `T`, the shim reads `openspec/changes/<change>/tasks.md` at `HEAD` (`_blob_at`) and, if `T` is in `_checked_task_ids` of it, sets the run's task to `None`. A run with no task is never budgeted (retry-budget: "A run with no task SHALL never be budgeted"), and its row records `task: null`, so it can't later count against `T` either. The resolution happens once, before the refusal check, so the refusal and the row agree.

An explicit `--task N.M` is untouched: the caller named the task, and a deliberate run against a reopened or completed task is still that task's attempt.

The helper itself stays as it is, because its other callers want "the latest started task" regardless of tick (the lock checks the task's placement; usage attributes tokens spent finishing it).

### D2. `_attempt_state` keeps counting post-tick reds — rejected as unnecessary

The issue suggests also dropping `ci` reds recorded after the task's tick commit from its count. Rejected. With D1, an implicit run after the tick writes `task: null`, so no new post-tick red row carries the task; the only post-tick rows that do are explicit `--task` runs, which are deliberate. The case where a completed task genuinely resumes is a test defect, and unblock-authored-lock D4 already reopens it through re-handoff and placement, whose `TESTS_PLACED` row restarts the counting window (D6). Filtering by tick commit would need the commit walk inside every budget check, for no case D1 leaves open.

Ledgers already poisoned by 0.11.0 (rows charged to a ticked task) stay as written. Under D1 those rows only matter for an explicit `--task` run on that task, and the window resets on the next placement or restart.

### D3. "Ticked" is read from `HEAD`, not the working tree

The issue proposes the working tree. We read `HEAD`, because it can't be gamed. A tick in the working tree costs nothing: an agent could tick the task in flight, run `ci` unbudgeted as often as it likes, and untick it. A tick at `HEAD` was committed beside the task's code through the commit gate (`ci` green plus convention review), which is the loop's done ⟺ committed rule. So a ticked task at `HEAD` has already passed, and the budget has nothing left to protect.

The cost: a sync started with `git merge --no-commit` has `HEAD` at the branch tip, whose `tasks.md` holds the ticks, so the issue's case is covered. A tick staged but not yet committed is still budgeted, which is the intent: that task isn't done yet.

Alternative considered: the working tree (as the issue proposes). Rejected for the gaming route above. Alternative considered: the completion walk (unblock-authored-lock D2's commit ordering). Rejected as heavier than needed: D1 only asks whether the task is done now, not where a row sits relative to the tick.

### D4. Docs: SETUP.md only

SETUP.md's "`loop.attempts` and `loop.fresh-restarts`" section says a run with no `--task` belongs to "the latest `task-start` after the handoff". It gains: "unless that task is checked in `HEAD`'s `tasks.md`; then the run belongs to no task and is not budgeted. A run with `--task` is always budgeted." The shipped prompts (`agents/tdd-implementer.md`, `skills/tdd-apply/SKILL.md`) describe the budget per task but never state the implicit-task rule, so they don't change.

## Risks / Trade-offs

- [A red during the task in flight, after an early tick was committed] → impossible without passing the commit gate, which requires `ci` green; accepted.
- [One extra `git cat-file` per implicit budgeted run] → one blob read; negligible beside the gate it precedes.
- [Detached HEAD or no `tasks.md` at HEAD] → `_blob_at` returns `None`, no ids are checked, and the run stays budgeted as today (fail closed).

## Migration Plan

None. Ships in 0.11.1; existing ledgers need no rewrite.
