# Spec Delta

## MODIFIED Requirements

### Requirement: Per-task attribution uses the recorded task id and never guesses

Rows carrying a `task` id SHALL be attributed to that task; per-task time is the
active-time sum over intervals attributed to the task's rows. Rows whose `task` is
null SHALL be reported under an explicit *unattributed* bucket — never assigned to
a nearby task by inference. The report SHALL state what the ledger cannot answer
(anything between recorded events — edit vs. think time, host contention, and
token spend for tasks with no usage row) rather than approximating it.

#### Scenario: Task-tagged rows produce a per-task breakdown

- **WHEN** the ledger holds rows with `task` ids recorded by `gates run --task`
- **THEN** the report shows time and failed attempts per task id

#### Scenario: Untagged rows are unattributed, not guessed

- **WHEN** the ledger holds rows whose `task` is null
- **THEN** their time appears in an explicit unattributed bucket and no heuristic assigns them to a task

## ADDED Requirements

### Requirement: `gates stats` reports token spend from usage rows

`gates stats` SHALL sum `usage` rows into tokens per task and per change, by model, print them beside time, and disclose the tasks and the span with no usage row. `--json` SHALL carry the same figures under a stable `tokens` key. `--epic` SHALL roll tokens up per child and for the epic.

#### Scenario: Tokens beside time

- **WHEN** a change's ledger holds usage rows for tasks 1.1 and 1.2 and none for 1.3
- **THEN** the per-task table shows tokens for 1.1 and 1.2, marks 1.3 as unrecorded, and the change total states how many tasks are unrecorded

#### Scenario: Rows from before usage existed

- **WHEN** a ledger holds no usage row at all
- **THEN** the report prints the time figures unchanged and states that token spend was not recorded for this change

### Requirement: `gates stats --outcomes` counts budget halts

The outcomes view SHALL count halts with cause `budget` under halts by cause, and the playbook SHALL name what a budget halt points to: a cheaper gate shape or a smaller change.

#### Scenario: A budget halt in the outcomes view

- **WHEN** a change's ledger holds a halt row with cause `budget`
- **THEN** `gates stats --outcomes` lists it under halts by cause as `budget`
