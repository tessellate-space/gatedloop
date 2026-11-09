## MODIFIED Requirements

### Requirement: A fresh restart resets the count once, from a clean tree

`gates attempt restart <task>` SHALL refuse unless the working tree is clean at the
task's last commit, and SHALL refuse once the task's restarts number
`loop.fresh-restarts`. Every active placement of the change SHALL count as clean while each placed test holds
exactly its placed content, whichever task it belongs to, and so SHALL the removal of
its holding files. An uncommitted append to the change's ledger made only of `usage`,
`restart` and `halt` rows SHALL count as clean. Otherwise it
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
- **THEN** `gates attempt restart 1.2` refuses, naming the path and its task, and records nothing

#### Scenario: Two tasks placed together

- **WHEN** tasks 8.1 and 8.2 were placed in one tree, both placements are uncommitted at
  their placed content, and 8.2 halted `stalled`
- **THEN** `gates attempt restart 8.2` records the `restart` row, and so does `gates
  attempt restart 8.1`

#### Scenario: A sibling's placed test edited

- **WHEN** tasks 8.1 and 8.2 were placed together and one of 8.1's placed tests differs
  from its placed content
- **THEN** `gates attempt restart 8.2` refuses, naming the path and task 8.1, and records
  nothing

#### Scenario: Uncommitted bookkeeping rows

- **WHEN** the only difference from the last commit is an append to the change's ledger
  of `halt`, `restart` and `usage` rows
- **THEN** `gates attempt restart` treats the tree as clean and records the `restart` row

#### Scenario: A dirty tree's refusal

- **WHEN** a restart refuses on uncommitted work other than placed tests and bookkeeping
  rows
- **THEN** the message names the paths and does not tell the agent to discard placed
  tests
