## ADDED Requirements

### Requirement: A task id may carry a letter suffix

A task id in `tasks.md` SHALL be two or more dot-separated numbers, optionally followed by one lowercase letter (`1.2`, `1.2.3`, `1.2a`). Every consumer of a change's task lines SHALL read such an id as it reads an `N.M` id: the oracle tag and its validation, the test author's brief, task completion, the approval digest and `gates tests show`. `gates validate` SHALL still report an oracle tag on a line whose id is not of that form.

#### Scenario: An amended task with a letter

- **WHEN** a change's `tasks.md` holds `- [ ] 1.2a Handle the empty case [oracle: unit]` and the test author has placed tests under `1.2a`
- **THEN** `gates tests show` lists `1.2a` after `1.2` with its oracle `unit`, and exits 0

#### Scenario: A lettered task is ticked

- **WHEN** the commit that checks `1.2a` precedes the first commit carrying a halt row for `1.2a`
- **THEN** task `1.2a` is completed at that halt, as an `N.M` task would be

#### Scenario: A tag on an unnumbered line

- **WHEN** a task line reads `- [ ] Update the docs [oracle: unit]`
- **THEN** `gates validate` reports that the tag is not read, naming the line

### Requirement: Tasks are listed in natural order

Wherever the shim lists a change's tasks, it SHALL order them by number, segment by segment, with a lettered id after the same id without a letter.

#### Scenario: Natural order

- **WHEN** a change has tasks `1.10`, `1.2a`, `1.2` and `1.9`
- **THEN** every listing orders them `1.2`, `1.2a`, `1.9`, `1.10`

## MODIFIED Requirements

### Requirement: The authored set is reviewed before implementation begins

Before the authoring commit, the convention review SHALL review the whole authored
set against `gatedloop.test-quality` and the project's `tests` rules, and SHALL record
its verdict with the `authored` scope. Findings SHALL go back to the author. After two
rounds with findings still open, the loop SHALL halt with cause `oracle-conflict`.

The review SHALL judge oracle coverage across the whole set. A behaviour SHALL be reported as lacking an oracle only when no task of the change holds a test for it. A `NO-TESTS` reason on a task whose work is writing a test that another task of the change holds SHALL NOT be reported as a missing oracle.

#### Scenario: The authored set draws a finding

- **WHEN** the authored-set review reports a test that asserts only a declared default
- **THEN** the author revises it before any implementation begins, and the review
  runs again

#### Scenario: The test is held by the behaviour's task

- **WHEN** an untagged plan has task 1.1 "write the self-test" recorded `NO-TESTS` and task 2.1 "implement the behaviour" holding that test
- **THEN** the review reports no missing oracle for 1.1 or 2.1

#### Scenario: No task holds a test for a behaviour

- **WHEN** a task changes behaviour, records no `NO-TESTS` reason a reviewer accepts, and no task of the change holds a test for that behaviour
- **THEN** the review reports it as a `gatedloop.test-quality` finding
