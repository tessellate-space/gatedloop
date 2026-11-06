# Spec Delta

## MODIFIED Requirements

### Requirement: Failed attempts are counted from the ledger

For a task, the shim SHALL count failed attempts from the ledger alone, never from the
caller's `--attempt`. A failed attempt is a red run, for that task, of its oracle gate or
of `ci`, and under `loop.ci-at: ready` also of `unit`, the commit gate there. It counts only if recorded after the task's first red oracle-gate run since the
later of its latest task start and its latest test placement, and after its latest
restart. The oracle gate is the gate the plan declares for the task, or `unit` when it
declares none. Exit 75 SHALL NOT count.

#### Scenario: A down environment is not an attempt

- **WHEN** a `unit` run for the task exits 75
- **THEN** the failed-attempt count is unchanged

#### Scenario: A test-defect cycle spends nothing

- **WHEN** task 1.1's placed tests fail on setup, a `setup` defect is recorded, the
  author re-hands off, and the task's tests are placed again
- **THEN** the red runs before the new placement are not counted, the next red `unit`
  run is the task's red run, and the count starts from zero after it

#### Scenario: An e2e task's red run

- **WHEN** task 5.1 is tagged `[oracle: integration]` and its first red `integration`
  run after placement is recorded
- **THEN** that run is the task's red run, and later red `integration` or `ci` runs
  count as failed attempts

#### Scenario: An e2e task's commit-gate red under ready

- **WHEN** `loop.ci-at: ready` is declared, task 5.1 is tagged `[oracle: integration]`,
  its RED `integration` run is recorded, and a later `unit` run for it is red
- **THEN** that `unit` run counts as a failed attempt

#### Scenario: A unit red under task for an e2e task

- **WHEN** `loop.ci-at` is absent and the same task records a red `unit` run after its
  RED run
- **THEN** the count is unchanged, as before

#### Scenario: The full ci at READY is no task's attempt

- **WHEN** `loop.ci-at: ready` is declared, every task is checked in HEAD's `tasks.md`,
  and `gates run ci` with no `--task` is red on the head
- **THEN** no task's failed-attempt count changes, and the gate is not refused by the
  budget
