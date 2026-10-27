# Spec Delta

## ADDED Requirements

### Requirement: A task may declare its oracle in the plan

A task line in `tasks.md` MAY end with `[oracle: <gate>]`, `[oracle: <gate> characterization]` or `[oracle: none]`. `<gate>` SHALL be a gate declared in `.gates.yaml` other than `ci`, `live-check`, `eval` and `confirm`. `gates validate` SHALL fail on an unknown gate, an excluded gate or a malformed tag, naming the change, the task and the tag. A task without a tag SHALL behave as before.

#### Scenario: An e2e task

- **WHEN** task 5.1 ends with `[oracle: integration]` and `integration` is declared
- **THEN** `gates validate` passes, and the task's oracle is the `integration` gate, red first

#### Scenario: An excluded gate

- **WHEN** a task ends with `[oracle: ci]`
- **THEN** `gates validate` fails, saying `ci` cannot judge one task and naming the gates that can

#### Scenario: An undeclared gate

- **WHEN** a task ends with `[oracle: contract]` and no `contract` gate is declared
- **THEN** `gates validate` fails, naming the gate and the task

#### Scenario: A task with no tag

- **WHEN** a task carries no tag
- **THEN** authoring, handoff, the lock and the attempt budget treat it exactly as they did without this capability

### Requirement: The test author is told each task's declared oracle

`gates tests brief` SHALL print each task's declared oracle beside it: the gate, whether it is `characterization`, or `none`. For an untagged task it SHALL say that the kind is the author's to decide.

#### Scenario: A brief for a tagged plan

- **WHEN** the plan tags 3.1 `[oracle: unit characterization]` and 4.2 `[oracle: none]`
- **THEN** the brief lists 3.1 as characterization on `unit`, and 4.2 as needing no tests

### Requirement: The handoff refuses a declaration that contradicts the plan

`gates tests handoff` SHALL refuse a task whose holding area contradicts its tag, naming the task, the tag and what the plan requires. It SHALL refuse:

- tests or `CHARACTERIZATION` for a `none` task;
- `NO-TESTS` for a gate-tagged task;
- a `characterization` task without `CHARACTERIZATION`;
- `CHARACTERIZATION` on a task tagged red first.

#### Scenario: E2e tests declared characterization

- **WHEN** task 5.1 is tagged `[oracle: integration]` and the author marks it `CHARACTERIZATION`
- **THEN** the handoff is refused, naming 5.1 and saying the plan requires a red `integration` run first

#### Scenario: Tests for a task the plan says has none

- **WHEN** task 4.2 is tagged `[oracle: none]` and the holding area has tests for it
- **THEN** the handoff is refused, naming 4.2

### Requirement: The lock reads the task's declared gate

For a task tagged with a gate, the lock's red-run condition SHALL be read on that gate: a run of it for the task, recorded after placement, that failed for a reason other than a precondition. For a `characterization` tag, the task's first verdict on that gate after placement SHALL be green. Untagged tasks SHALL keep the `unit` rule. The commit hooks and `gates tests check --ref` SHALL apply the same rule.

#### Scenario: An e2e task red on its gate

- **WHEN** task 5.1 is tagged `[oracle: integration]` and a red `integration` run for 5.1 is recorded after placement, with no `unit` run
- **THEN** the lock's red-run condition holds for 5.1

#### Scenario: A red unit run for an e2e task

- **WHEN** task 5.1 is tagged `[oracle: integration]` and only a red `unit` run is recorded after placement
- **THEN** the commit is refused, naming `gates run integration --task 5.1`

#### Scenario: A characterization task on another gate

- **WHEN** task 3.1 is tagged `[oracle: integration characterization]` and its first `integration` verdict after placement is green
- **THEN** the lock's condition holds for 3.1

### Requirement: A project may require every task to declare its oracle

`loop.task-oracle` SHALL accept `optional` (the default) or `required`. Under `required`, `gates tests handoff` SHALL refuse a change with any untagged task, naming each one. An unknown value SHALL fail validation.

#### Scenario: An untagged task under required

- **WHEN** `loop.task-oracle: required` and task 2.3 carries no tag
- **THEN** the handoff is refused, naming 2.3 and the tag syntax

#### Scenario: The default

- **WHEN** `loop.task-oracle` is not declared
- **THEN** untagged tasks are handed off as before
