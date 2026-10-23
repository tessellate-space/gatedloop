## ADDED Requirements

### Requirement: A characterization task's tests must pass before implementation

The author MAY declare a task `characterization`, with a reason, when its tests pin
behaviour the tree already has. For such a task, the commit check SHALL require a
green `unit` run for the task after placement instead of a red one. A red run there
SHALL be a defect. The implementer SHALL NOT make the declaration, and the
authored-set review SHALL judge it.

#### Scenario: A refactor guarded by characterization tests

- **WHEN** task 2.1 is declared `characterization` and its placed tests pass on the
  base tree
- **THEN** the green run satisfies the check, and the task commits under the usual
  lock and `ci`

#### Scenario: A characterization test that fails on the base tree

- **WHEN** a characterization task's run after placement is red
- **THEN** the commit is refused and the implementer records a test defect

#### Scenario: Declared both ways

- **WHEN** a task carries both `CHARACTERIZATION` and `NO-TESTS`
- **THEN** the handoff is refused, naming the task

## MODIFIED Requirements

### Requirement: A wrong test goes back to its author, and a persistent disagreement halts

The implementer SHALL NOT correct an authored test. It SHALL record `gates tests defect
<task> --kind setup|assertion --detail <why>`, and the author SHALL be re-dispatched
for the task. A task SHALL take at most two `assertion` defects, then halt with cause
`oracle-conflict`, and at most three `setup` defects, then halt with cause
`weak-spec`. A defect without a kind SHALL be refused.

#### Scenario: The implementer finds a defective test

- **WHEN** the implementer judges a placed test wrong
- **THEN** it records a test defect with its kind and reason, the author revises or
  defends that task's tests, and implementation resumes against the new handoff

#### Scenario: Placed tests are already green

- **WHEN** a task's placed tests pass on their first run and the task is not
  declared `characterization`
- **THEN** the implementer records a defect instead of implementing against them

#### Scenario: Fixture mistakes do not spend the behaviour cap

- **WHEN** a task has two `setup` defects and no `assertion` defect
- **THEN** a first `assertion` defect is still accepted

#### Scenario: Author and implementer keep disagreeing

- **WHEN** two `assertion` defects have been recorded for a task
- **THEN** a third `assertion` defect is refused, and the loop halts with cause
  `oracle-conflict`, carrying both positions
