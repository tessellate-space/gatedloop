# retry-budget Specification

## Purpose
Make the loop's stopping rule enforceable and give it memory: failed attempts are counted from the ledger and capped by `loop.attempts`, each failed attempt leaves a short structured note a resuming or restarted agent reads, and one fresh restart from a clean tree (`loop.fresh-restarts`) is allowed before a task escalates as `stalled`.

## Requirements

### Requirement: Failed attempts are counted from the ledger

For a task, the shim SHALL count failed attempts from the ledger alone, never from the
caller's `--attempt`. A failed attempt is a red `unit` or `ci` run for that task,
recorded after the task's first red `unit` run since the later of its latest task start
and its latest test placement, and after its latest restart. Exit 75 SHALL NOT count.

#### Scenario: A down environment is not an attempt

- **WHEN** a `unit` run for the task exits 75
- **THEN** the failed-attempt count is unchanged

#### Scenario: A test-defect cycle spends nothing

- **WHEN** task 1.1's placed tests fail on setup, a `setup` defect is recorded, the
  author re-hands off, and the task's tests are placed again
- **THEN** the red runs before the new placement are not counted, the next red `unit`
  run is the task's red run, and the count starts from zero after it

### Requirement: The attempt cap is enforced

Once a task's failed-attempt count reaches `loop.attempts`, `gates run unit` and `gates
run ci` for the task SHALL refuse without running the gate, exiting 1 with a message
naming the budget, the count and the remaining way forward. A run with no task SHALL
never be budgeted.

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

### Requirement: Attempt notes are structured ledger rows

`gates attempt note <task>` SHALL append an `attempt-note` row carrying four required,
single-line fields of at most 200 characters each: hypothesis, what changed, what the
oracle said, and what to rule out next. An over-long or missing field SHALL be
refused, never truncated. `gates attempt notes <task>` SHALL print the task's notes
oldest first, across restarts.

#### Scenario: A note after a failed attempt

- **WHEN** the agent records a note with all four fields after task 1.2's first failed
  attempt
- **THEN** `gates attempt notes 1.2` prints it, numbered with that attempt

#### Scenario: A note that is a transcript

- **WHEN** a field exceeds 200 characters or spans lines
- **THEN** the note is refused naming the field, and nothing is written

### Requirement: A fresh restart resets the count once, from a clean tree

`gates attempt restart <task>` SHALL refuse unless the working tree is clean at the
task's last commit, and SHALL refuse once the task's restarts number
`loop.fresh-restarts`. A task's placed tests SHALL count as clean while each holds
exactly its placed content, and so SHALL the removal of their holding files. Otherwise it
SHALL record a `restart` row, after which the failed-attempt count starts again from
zero. The implementer SHALL NOT restart itself; restarting is the dispatcher's act, in a
new agent context.

#### Scenario: A restart with one remaining

- **WHEN** task 1.2's budget is used, the tree is clean, and no restart has been
  recorded under `loop.fresh-restarts: 1`
- **THEN** `gates attempt restart 1.2` records a `restart` row and the next `gates run
  unit --task 1.2` runs

#### Scenario: No restart remains

- **WHEN** task 1.2 has already been restarted once under `loop.fresh-restarts: 1`
- **THEN** `gates attempt restart 1.2` refuses, naming the halt as the way forward

#### Scenario: A dirty tree

- **WHEN** the working tree has uncommitted changes
- **THEN** `gates attempt restart` refuses and records nothing

#### Scenario: Only the task's placed tests differ

- **WHEN** the only differences from the task's last commit are task 1.2's placed
  tests at exactly their placed content and the removal of their holding files
- **THEN** `gates attempt restart 1.2` treats the tree as clean and records the
  `restart` row

#### Scenario: A placed test edited after placement

- **WHEN** one of task 1.2's placed tests differs from its placed content
- **THEN** `gates attempt restart 1.2` refuses, naming the path, and records nothing

### Requirement: The budget is declared in the manifest

`loop.attempts` (default 2) and `loop.fresh-restarts` (default 1) SHALL be optional
non-negative integers under `loop` in `.gates.yaml`, validated by `gates validate`.

#### Scenario: No budget declared

- **WHEN** `.gates.yaml` declares neither key
- **THEN** two failed attempts and one fresh restart are allowed per task

#### Scenario: An invalid budget

- **WHEN** `loop.attempts` is negative or not an integer
- **THEN** `gates validate` fails, naming the key
