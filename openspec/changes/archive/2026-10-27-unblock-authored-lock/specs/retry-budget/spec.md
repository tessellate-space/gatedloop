# Spec Delta

## MODIFIED Requirements

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
