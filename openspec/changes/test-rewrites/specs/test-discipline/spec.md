# Spec Delta

## MODIFIED Requirements

### Requirement: A change's failing tests are authored before implementation, by an agent that does not implement it

Unless the project declares `loop.test-author: inline`, a change SHALL pass through an
authoring phase before its first task. In that phase a test-author agent writes the
failing tests for every task of the change. Its inputs are the task list, the
change's spec scenarios and design, the public interfaces of the code involved, and
the project's test conventions. It SHALL NOT read function bodies of the code under
change or the contents of existing test files, with one exception: the content of an
existing test file that a task's oracle tag declares under `rewrites:`, as the brief
prints it. It SHALL NOT read any other existing test file. It SHALL NOT write anything
outside the change's holding area. The authoring phase SHALL be dispatched by whoever
dispatches the implementation, never by the implementer.

#### Scenario: An approved change under the default

- **WHEN** implementation of an approved change is requested in a project that
  declares no `loop.test-author`, or declares `separate`
- **THEN** the test author writes every task's tests into the holding area, and they
  are handed off, reviewed and committed before the first task starts

#### Scenario: The implementer is started without authored tests

- **WHEN** the implementer starts a change under `separate` and no handoff exists for
  it
- **THEN** it writes no tests and halts with cause `missing-oracle`, naming the
  test-author dispatch as the missing step

#### Scenario: The plan leaves blocking questions

- **WHEN** the author cannot write some task's tests without deciding something the
  specs and design do not decide, and the choice is not low-stakes
- **THEN** nothing is handed off, and every such question for the whole change is
  returned together with cause `weak-spec`

#### Scenario: The author reports what each test guards

- **WHEN** the authoring phase completes
- **THEN** the report names, for each task, every test with the regression that makes
  it fail, or the reason the task changes no behaviour, together with the interface
  decisions the author took

#### Scenario: An orchestrator runs lanes

- **WHEN** implementation runs as a lane dispatched by an orchestrator or another
  session
- **THEN** that dispatcher runs the authoring phase first, as a sibling of the lane,
  so no agent needs to dispatch a subagent

#### Scenario: A bugfix change's reproduction

- **WHEN** a change on the regression-first route is authored
- **THEN** the test author turns the recorded reproduction into that unit's test,
  and the implementer writes only the fix

#### Scenario: A declared rewrite

- **WHEN** task 2.1 is tagged `[oracle: unit rewrites: tests/toolbar.test.ts]`
- **THEN** the author reads that file's content from the brief, hands off its full
  content after 2.1, and reads no other existing test file

#### Scenario: An existing test that must change but is not declared

- **WHEN** the author finds that a task needs an existing test file changed, and no
  task's tag declares it under `rewrites:`
- **THEN** the author does not read it, and returns it as a blocking question naming
  the task and the path, so the plan can declare it

### Requirement: A task may declare its oracle in the plan

A task line in `tasks.md` MAY end with `[oracle: <gate>]`, `[oracle: <gate> characterization]` or `[oracle: none]`. A tag that names a gate MAY end with a `rewrites:` clause: one or more repository-relative paths of existing test files that the task rewrites, separated by commas, as in `[oracle: unit rewrites: tests/a.test.ts, tests/b.test.ts]`. `<gate>` SHALL be a gate declared in `.gates.yaml` other than `ci`, `live-check`, `eval` and `confirm`. `gates validate` SHALL fail on an unknown gate, an excluded gate or a malformed tag, naming the change, the task and the tag. A tag is malformed when its `rewrites:` clause is empty, names a path that is absolute, contains a `..` segment or lies under gatedloop's state directory, names one path twice, or follows `none`. `gates validate` SHALL warn, without failing, when a declared path is absent from the working tree or does not look like a test path. A task without a tag SHALL behave as before.

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

#### Scenario: A rewrite clause

- **WHEN** task 2.1 ends with `[oracle: unit characterization rewrites: tests/a.test.ts, tests/b.test.ts]` and both files exist
- **THEN** `gates validate` passes, and 2.1's oracle is `unit`, green first, rewriting both files

#### Scenario: A path that escapes the repository

- **WHEN** a task ends with `[oracle: unit rewrites: ../other/a.test.ts]`
- **THEN** `gates validate` fails, naming the change, the task and the path

#### Scenario: A rewrite on a task with no tests

- **WHEN** a task ends with `[oracle: none rewrites: tests/a.test.ts]`
- **THEN** `gates validate` fails, saying a task that rewrites a test has a test

#### Scenario: A declared path not in the tree

- **WHEN** a task declares `rewrites: tests/gone.test.ts` and no such file exists in the working tree
- **THEN** `gates validate` passes with a warning naming the change, the task and the path

### Requirement: The test author is told each task's declared oracle

`gates tests brief` SHALL print each task's declared oracle beside it: the gate, whether it is `characterization`, or `none`. For an untagged task it SHALL say that the kind is the author's to decide. For each path a task declares under `rewrites:`, the brief SHALL print, under that task, the path and the file's full content at `HEAD`, or say that the path is absent at `HEAD`. The brief SHALL print the content of no other existing test file.

#### Scenario: A brief for a tagged plan

- **WHEN** the plan tags 3.1 `[oracle: unit characterization]` and 4.2 `[oracle: none]`
- **THEN** the brief lists 3.1 as characterization on `unit`, and 4.2 as needing no tests

#### Scenario: A brief for a declared rewrite

- **WHEN** the plan tags 2.1 `[oracle: unit rewrites: tests/toolbar.test.ts]`
- **THEN** the brief prints, under 2.1, `tests/toolbar.test.ts` and its content at `HEAD`, and prints only the paths of the other existing tests near the code

#### Scenario: A declared path absent at HEAD

- **WHEN** a task declares `rewrites: tests/gone.test.ts` and `HEAD` has no such file
- **THEN** the brief says the path is absent at `HEAD` and prints no content for it

### Requirement: The handoff refuses a declaration that contradicts the plan

`gates tests handoff` SHALL refuse a task whose holding area contradicts its tag, naming the task, the tag and what the plan requires. It SHALL refuse:

- tests or `CHARACTERIZATION` for a `none` task;
- `NO-TESTS` for a gate-tagged task;
- a `characterization` task without `CHARACTERIZATION`;
- `CHARACTERIZATION` on a task tagged red first;
- a path the task declares under `rewrites:` that does not exist at `HEAD`;
- a path the task declares under `rewrites:` for which the task holds no full authored file.

A handoff that writes an existing path no task declares SHALL be recorded as before, with an advisory line naming the task and the path, and SHALL NOT be refused for it.

#### Scenario: E2e tests declared characterization

- **WHEN** task 5.1 is tagged `[oracle: integration]` and the author marks it `CHARACTERIZATION`
- **THEN** the handoff is refused, naming 5.1 and saying the plan requires a red `integration` run first

#### Scenario: Tests for a task the plan says has none

- **WHEN** task 4.2 is tagged `[oracle: none]` and the holding area has tests for it
- **THEN** the handoff is refused, naming 4.2

#### Scenario: A declared rewrite missing from the handoff

- **WHEN** task 2.1 declares `rewrites: tests/toolbar.test.ts` and its holding area has no `tests/toolbar.test.ts.authored`
- **THEN** the handoff is refused, naming 2.1 and the path, and nothing is recorded

#### Scenario: A declared rewrite of a file that does not exist

- **WHEN** task 2.1 declares `rewrites: tests/gone.test.ts` and `HEAD` has no such file
- **THEN** the handoff is refused, naming 2.1 and the path, and saying the plan is amended

#### Scenario: An undeclared overwrite

- **WHEN** task 3.1 carries no `rewrites:` clause and its holding area holds a full file for an existing path
- **THEN** the handoff is recorded with that path's base as before, and prints an advisory line naming 3.1 and the path

### Requirement: A task's oracle tag is held to the approved plan

When a change's `tasks.md` carries an oracle tag, the approval sha SHALL also cover its `(task id, tag)` pairs, including any `rewrites:` clause, without checkbox state or task text, and a plan with no tag SHALL hash as before. A tag without a `rewrites:` clause SHALL hash as it did before the clause existed. The handoff, the lock and `gates tests check --ref` SHALL refuse a task whose tag in the evaluated tree differs from its tag in the merge target's `tasks.md`, naming the task, both tags and that the plan is amended on the target and re-attested.

#### Scenario: A retag on the change branch

- **WHEN** the target's `tasks.md` tags 5.1 `[oracle: integration]` and the change branch retags it `[oracle: unit characterization]`
- **THEN** the commit is refused, naming 5.1, both tags and the amend-and-re-attest route

#### Scenario: A retag on the target after approval

- **WHEN** an approved plan's tag for 5.1 is edited on the target
- **THEN** `check-implement` refuses until the change is re-attested

#### Scenario: Ticking a task

- **WHEN** a task's `[ ]` becomes `[x]`
- **THEN** the approval sha is unchanged

#### Scenario: A rewrite added on the change branch

- **WHEN** the target's `tasks.md` tags 2.1 `[oracle: unit]` and the change branch tags it `[oracle: unit rewrites: tests/a.test.ts]`
- **THEN** the handoff and the commit are refused, naming 2.1 and both tags

#### Scenario: Upgrading with tags and no rewrites

- **WHEN** an approved plan carries tags and no `rewrites:` clause
- **THEN** its approval sha is the same under this version as under the one before it

## ADDED Requirements

### Requirement: A rewritten existing test is the task's authored test

Once placed, a file a task declares under `rewrites:` SHALL be that task's authored test, under the same lock, red run and defect rules as a new one. `gates tests place` SHALL replace the existing file with the handed-off content, and the implementer SHALL NOT edit it.

#### Scenario: A rewrite placed and run red

- **WHEN** task 2.1 declares `rewrites: tests/toolbar.test.ts`, its handoff is placed, and a red `unit` run for 2.1 is recorded after placement
- **THEN** the existing file holds the handed-off content, and the lock's conditions hold for 2.1

#### Scenario: The implementer edits a rewritten test

- **WHEN** a commit for 2.1 stages `tests/toolbar.test.ts` with content other than its handed-off content
- **THEN** the commit is refused, naming the path and directing the implementer to record a test defect

#### Scenario: A rewrite with no red run

- **WHEN** task 2.1 is tagged red first, declares a rewrite, and no red `unit` run for 2.1 is recorded after placement
- **THEN** the commit is refused, because red before green is required

#### Scenario: A defect against a rewrite

- **WHEN** a defect is recorded for 2.1 after its rewrite was placed
- **THEN** the lock requires `tests/toolbar.test.ts` at its content before the change until 2.1 is placed again

### Requirement: Review sees each rewrite's change against its base

`gates tests show` SHALL list, for each task, every path it declares under `rewrites:` with the number of lines the handed-off content adds and removes against the path's content before the change, in its text and JSON output. `gates tests show --diff` SHALL print each rewrite's unified diff against that content. The authored-set review SHALL read that diff and SHALL report a removed case that the task's specs and design give no reason to remove.

#### Scenario: Show lists a rewrite

- **WHEN** task 2.1's handed-off `tests/toolbar.test.ts` drops three lines and adds five against its base
- **THEN** `gates tests show` lists `tests/toolbar.test.ts` under 2.1 as a rewrite, with five lines added and three removed

#### Scenario: Show prints the diff

- **WHEN** `gates tests show <change> --diff` runs after that handoff
- **THEN** it prints the unified diff of `tests/toolbar.test.ts` from its base to the handed-off content

#### Scenario: A dropped case with no reason

- **WHEN** a rewrite removes a test case and no scenario or design decision of the change removes that behaviour
- **THEN** the authored-set review reports it as a `gatedloop.test-quality` finding citing the task and the path
