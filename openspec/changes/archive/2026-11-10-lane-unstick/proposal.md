# Proposal: lane-unstick

## Why

Two 0.11.1 defects strand an adopter's lane with no sanctioned way out. Both are still in 0.12.0, and the only escapes are a hand edit of the ledger or the locked area, or a history rewrite. The lock exists to forbid exactly those.

- **#178.** `gates tests check` reports that the ledger "loses rows" on a lane that lost none. `_task_completion` starts its first-parent walk at the merge-base with the target, so the first count it compares against is the target's copy of the ledger. Each amended plan's approval attestation appends `approval-local` rows to that copy on `main` after the lane forked. The first lane commit after the base then reads as a shrink. The walk runs only when a `halt` or `test-defect` row names a task, so the refusal surfaces when that task's `[x]` is staged. It blocks the merge's `tests check --ref` the same way. An adopter has a lane stuck on it.
- **#173.** `gates attempt restart` counts every placement except the restarted task's as dirt, so neither task of a batch placed together can restart after a halt. It also counts an uncommitted `restart` or `halt` row as dirt, so each restart needs its own ledger-grade commit first. Its refusal tells the agent to "discard the halted run's partial work", which reads as "delete the placed tests".

## What Changes

- The completion walk starts at the first walked commit's own first parent, not at the merge-base snapshot. It compares the lane's ledger only with the lane's own earlier copies. A real shrink on the lane is still refused, naming the commit.
- `gates attempt restart` treats every placement of the change that is active or voided only by a halt, at exactly its placed content, as clean, along with its holding-file removals, whichever task it belongs to. A placed test of any task that differs from its placed content is refused, and the refusal names the path and its task.
- `gates attempt restart` treats an uncommitted append to the change's ledger as clean when the append holds only bookkeeping rows (`usage`, `restart`, `halt`). The refusal for real dirt no longer says to discard work. It names what is dirty and says to commit or set aside work that is not a placed test.
- Ships as 0.12.1.

## Capabilities

### Modified Capabilities

- `test-discipline`: the completion walk reads the lane's own first-parent line.
- `retry-budget`: what a restart counts as clean.

## Impact

- `bin/gates`: `_task_completion`, `_restart_dirt`, `_attempt_restart`, and a restart-only bookkeeping predicate next to `_usage_only_append`. That function and its other callers (the `Stop` hook's task boundary) are unchanged.
- `tests/test_task_completion_order.py`, `tests/test_attempt_restart_placed.py`, `tests/test_attempt_restart.py`.
- `SETUP.md` (the `gates attempt restart` bullet), `AUTOMATION.md` (the restart line).
- No new subcommand, flag, manifest key or ledger field, so `tests/contract.json` is unchanged.
