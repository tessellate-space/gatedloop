## ADDED Requirements

### Requirement: A task may declare that it preserves behaviour

A task line in `tasks.md` MAY end with `[oracle: <gate> preserve]`, where `<gate>` obeys the same rules as any oracle gate. `gates validate` SHALL fail, naming the change, the task and the tag, when `preserve` is combined with `characterization`, with a `rewrites:` clause or with `none`. It SHALL warn, without failing, when a preserve task's text names a test path.

#### Scenario: A refactor task

- **WHEN** task 2.1 ends with `[oracle: unit preserve]` and `unit` is declared
- **THEN** `gates validate` passes, and 2.1's oracle is `unit`, preserving every test

#### Scenario: Preserve with characterization

- **WHEN** a task ends with `[oracle: unit characterization preserve]`
- **THEN** `gates validate` fails, naming the change, the task and the tag

#### Scenario: Preserve with a rewrite

- **WHEN** a task ends with `[oracle: unit preserve rewrites: tests/a.test.ts]`
- **THEN** `gates validate` fails, saying a task that preserves every test rewrites none

#### Scenario: Preserve on none

- **WHEN** a task ends with `[oracle: none preserve]`
- **THEN** `gates validate` fails, naming the tag as malformed

#### Scenario: A preserve task that names a test file

- **WHEN** task 2.1 is tagged `[oracle: unit preserve]` and its text names `tests/test_parser.py`
- **THEN** `gates validate` passes with a warning naming the change, 2.1 and the path

### Requirement: The approval covers the preserve modifier

The approval sha and the tag-drift check SHALL cover the `preserve` modifier. A tag without it SHALL hash as it did before the modifier existed.

#### Scenario: Upgrading with no preserve tag

- **WHEN** an approved plan carries tags and none of them says `preserve`
- **THEN** its approval sha is the same under this version as under the one before it

#### Scenario: A preserve tag added on the target after approval

- **WHEN** an approved plan's tag for 2.1 is edited on the target to `[oracle: unit preserve]`
- **THEN** `check-implement` refuses until the change is re-attested

#### Scenario: A preserve tag added on the change branch

- **WHEN** the target's `tasks.md` tags 2.1 `[oracle: unit]` and the change branch tags it `[oracle: unit preserve]`
- **THEN** the handoff and the commit are refused, naming 2.1 and both tags

### Requirement: The test author places nothing for a preserve task

`gates tests brief` SHALL tell the author that a preserve task needs no tests: only its `NO-TESTS` reason, with the gate the task must stay green on. `gates tests handoff` SHALL refuse tests or `CHARACTERIZATION` for a preserve task and SHALL accept its `NO-TESTS`, naming the task, the tag and what the plan requires. `gates tests place` for a preserve task SHALL place nothing, and SHALL say that no test path may change and that a green run of the gate on the task's tree is required.

#### Scenario: A brief for a preserve task

- **WHEN** the plan tags 2.1 `[oracle: unit preserve]`
- **THEN** the brief lists 2.1 as preserve on `unit`, needing only a `NO-TESTS` reason

#### Scenario: Tests held for a preserve task

- **WHEN** task 2.1 is tagged `[oracle: unit preserve]` and the holding area has tests for it
- **THEN** the handoff is refused, naming 2.1, and nothing is recorded

#### Scenario: A preserve task's reason

- **WHEN** task 2.1 is tagged `[oracle: unit preserve]` and its holding area holds only `NO-TESTS`
- **THEN** the handoff is recorded

#### Scenario: Placing a preserve task

- **WHEN** `gates tests place 2.1` runs for a preserve task
- **THEN** nothing is placed, no red run is required, and the output names the gate and the test-path rule

### Requirement: What counts as a test path

A path SHALL count as a test path when the brief's heuristic classes it as a test, when the change's ledger records it as handed off or placed, or when it matches the manifest's `acceptance.match`. A path under gatedloop's state directory or under `openspec/` SHALL never count.

#### Scenario: A path the change handed off

- **WHEN** a handoff row of the change names `src/checks/ParserCheck.java`
- **THEN** it counts as a test path, whatever its name

#### Scenario: gatedloop's own state

- **WHEN** a path lies under `.gatedloop/`
- **THEN** it does not count as a test path

#### Scenario: A plan artifact

- **WHEN** a path lies under `openspec/specs/`
- **THEN** it does not count as a test path

### Requirement: A preserve task changes no test path

While a preserve task is in flight, `gates tests check` SHALL fail for each test path whose staged content differs from the task's latest `task-start` tree, naming the path, the task and whether it was modified, deleted or added. A rename SHALL be refused as a deletion and an addition.

#### Scenario: An existing test edited during a refactor

- **WHEN** task 2.1 is tagged `[oracle: unit preserve]` and the staged tree changes `tests/test_parser.py` from its content at 2.1's `task-start`
- **THEN** the commit is denied, naming the path, 2.1 and that a preserve task changes no test

#### Scenario: A test deleted during a refactor

- **WHEN** a preserve task's staged tree lacks a test path its `task-start` tree has
- **THEN** the commit is denied, naming the path as deleted

#### Scenario: A test added during a refactor

- **WHEN** a preserve task's staged tree adds `tests/test_new.py`
- **THEN** the commit is denied, naming the path as added and saying that a characterization test belongs in an earlier characterization task

#### Scenario: A source-only refactor

- **WHEN** a preserve task's staged tree changes only paths that are not test paths, with its green run recorded
- **THEN** both conditions hold for the task

#### Scenario: Checking a preserve task that never started

- **WHEN** `gates tests check --task 2.1` runs for preserve task 2.1 and no `task-start` row exists for 2.1
- **THEN** the check fails, saying that `gates task start 2.1` was never recorded

#### Scenario: An acceptance file

- **WHEN** `acceptance.match` is `features/**/*.feature` and a preserve task's staged tree changes `features/login.feature`
- **THEN** the commit is denied, naming the path

### Requirement: A preserve task's gate is green on its own tree

For a preserve task in flight, `gates tests check` SHALL fail unless a run of the task's declared gate for that task, recorded after its latest `task-start`, exited 0 on a tree equal to the staged tree with the ledger left out. A precondition failure SHALL NOT count as a run. No red run SHALL be required.

#### Scenario: Green on the staged tree

- **WHEN** task 2.1 is tagged `[oracle: unit preserve]` and `gates run unit --task 2.1` passed on the staged tree after 2.1's `task-start`
- **THEN** the green-run condition holds for 2.1

#### Scenario: Green before the last edit

- **WHEN** the only passing `unit` run for 2.1 was recorded on a tree that differs from the staged tree by a source edit
- **THEN** the commit is denied, naming `gates run unit --task 2.1` with the task's changes staged

#### Scenario: A green run on another gate

- **WHEN** task 2.1 is tagged `[oracle: integration preserve]` and only a passing `unit` run is recorded
- **THEN** the commit is denied, naming `gates run integration --task 2.1`

### Requirement: The preserve conditions hold at any commit

`gates tests check --ref <commit>` SHALL judge, from commits only, every preserve task that is checked at that commit, at the commit C that ticks it in `tasks.md`. The test-path condition SHALL compare C's tree with the tree of the last earlier commit that ticks another task, or the branch's first commit's parent. The green-run condition SHALL accept a passing run of the task's gate for that task, recorded after its latest `task-start` and carried by C's ledger, without comparing trees.

#### Scenario: A test edited past the commit hooks

- **WHEN** the commit that ticks preserve task 2.1 changed a test path from the last earlier commit that ticks another task
- **THEN** `gates tests check --ref <head>` fails, naming the path, 2.1 and that commit

#### Scenario: A clean refactor at the head

- **WHEN** every preserve task's ticking commit changed no test path and carries a passing row of the task's gate after its `task-start`
- **THEN** the check passes for those tasks

#### Scenario: A later task changes the same test

- **WHEN** preserve task 2.1's ticking commit changed no test path, and the later task 3.1 placed new content at a test path 2.1 kept
- **THEN** `gates tests check --ref <head>` holds for 2.1, because each preserve task is judged at its own ticking commit

#### Scenario: A green run at the forge

- **WHEN** a fresh clone holds only the branch's commits, and C carries a passing `unit` row for preserve task 2.1 after 2.1's `task-start`
- **THEN** the green-run condition holds for 2.1 under `--ref`, although no recorded tree can be read there

#### Scenario: No green run at the ticking commit

- **WHEN** C carries no passing `unit` row for preserve task 2.1 after 2.1's `task-start`
- **THEN** `gates tests check --ref <head>` fails, naming `unit`, 2.1 and C

#### Scenario: A change with no preserve task

- **WHEN** a change's `tasks.md` has no preserve task at the commit
- **THEN** `gates tests check --ref <commit>` writes the same bytes to stdout and stderr, and exits with the same code, as 0.13.0 does on the same commit, so step 1 of `gates merge` is unchanged for that change

#### Scenario: A preserve task not yet ticked

- **WHEN** preserve task 2.2 is not checked at the commit
- **THEN** the `--ref` check applies no preserve condition to 2.2
