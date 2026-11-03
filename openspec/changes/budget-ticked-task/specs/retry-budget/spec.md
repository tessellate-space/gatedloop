## MODIFIED Requirements

### Requirement: The attempt cap is enforced

Once a task's failed-attempt count reaches `loop.attempts`, `gates run unit` and `gates
run ci` for the task SHALL refuse without running the gate, exiting 1 with a message
naming the budget, the count and the remaining way forward. A run with no task SHALL
never be budgeted. A run given no `--task` SHALL belong to the latest task started after
the handoff, unless that task is checked in the change's `tasks.md` at `HEAD`; then the
run SHALL belong to no task, and its ledger row SHALL record no task. A run given
`--task` SHALL belong to that task whether or not it is checked.

#### Scenario: The budget is used

- **WHEN** task 1.2 has had its RED run and then two red `unit` runs, and
  `loop.attempts` is 2
- **THEN** `gates run unit --task 1.2 --attempt 4` refuses with exit 1 without running
  the gate, and names `gates attempt restart 1.2` when a restart remains

#### Scenario: The caller's attempt number buys nothing

- **WHEN** the budget for task 1.2 is used and the caller passes `--attempt 1`
- **THEN** the run is still refused

#### Scenario: A run outside the loop

- **WHEN** `gates run ci` runs with no task given and no task started
- **THEN** no budget applies and the gate runs

#### Scenario: A red ci on a fully ticked change

- **WHEN** every task of the change is checked at `HEAD`, task 2.2 was the last started
  and has used its attempts and its restart, and a red `ci` has been recorded since
- **THEN** a plain `gates run ci` runs the gate, and its ledger row records no task

#### Scenario: An explicit task stays budgeted

- **WHEN** task 2.2 is checked at `HEAD` and its budget is used
- **THEN** `gates run ci --task 2.2` refuses with exit 1 without running the gate

#### Scenario: A tick not yet committed buys nothing

- **WHEN** the task in flight has used its budget and is checked in the working tree's
  `tasks.md` but not at `HEAD`
- **THEN** a plain `gates run ci` is refused as that task's attempt
