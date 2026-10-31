# test-discipline Specification

## Purpose
The tests the loop writes must fail for a real regression, at the lowest layer that can
observe it, and must follow the project's own architecture and test conventions. The
loop names each test's regression before writing it, names an existing test when it
adds none, and a built-in review rule flags the patterns that cannot fail for a real
reason.

## Requirements

### Requirement: gatedloop ships a built-in test-quality rule that review always applies

gatedloop SHALL ship a stack-agnostic `gatedloop.test-quality` rule inside the plugin.
`gates rules` SHALL list it for every diff, together with its source path, whatever
surfaces are hot. The convention review SHALL apply it to every test the diff adds or
changes. Each finding SHALL cite the rule-id and the numbered item it violates. The
rule text SHALL NOT name any project-specific tool, framework or library.

#### Scenario: A diff touches no declared surface

- **WHEN** `gates rules` runs on a diff that makes no surface hot
- **THEN** it still lists `gatedloop.test-quality` and the path of the file that
  defines it

#### Scenario: The rule source resolves from an installed plugin

- **WHEN** `gates rules` runs from the plugin's installed cache location
- **THEN** the path it prints for the built-in rule exists and contains the rule's
  section, resolved relative to the plugin, never to the project

#### Scenario: A test asserts a declared default

- **WHEN** a diff adds a test whose only assertion is that a newly declared field
  holds its declared default
- **THEN** the review reports it as a `gatedloop.test-quality` finding citing the item
  for tests that execute no application behaviour

#### Scenario: The rule names no stack

- **WHEN** the shipped rule file is checked for project-specific tool, framework or
  library names
- **THEN** none appear

### Requirement: The RED step names the regression before writing a test

Before writing a failing test, the loop SHALL establish, in order: which real
regression would make the test fail; whether an existing test one layer down already
covers the behaviour; and whether the code under test is domain logic or I/O. A test
that no named regression would fail SHALL NOT be written.

#### Scenario: The behaviour is already covered one layer down

- **WHEN** an existing test at a lower layer already fails for the regression the task
  guards against
- **THEN** the loop names that test and adds no new one for that behaviour

#### Scenario: Domain logic under test

- **WHEN** the code under test is domain logic, with no database, network, filesystem
  or third-party client in its path
- **THEN** its test calls it directly, with no fakes

#### Scenario: An I/O adapter under test

- **WHEN** the code under test is an adapter to an external system
- **THEN** it gets a contract test against the real system at the integration gate,
  and no unit-level fake of that system

#### Scenario: The test would need a fake of a type the project does not own

- **WHEN** writing the test would require faking a type the project does not own
- **THEN** the loop extracts the domain logic behind an interface the project owns and
  tests that instead, and when the extraction falls outside the current task it halts
  with cause `weak-spec` rather than writing the fake

#### Scenario: The project's rules are read before the questions are answered

- **WHEN** the RED step begins for a task
- **THEN** the loop resolves the project's rules for the paths the task touches from
  the same rules-doc convention review uses, and reads them with the change's design
  before classifying the code or choosing a seam

#### Scenario: The project defines its layers

- **WHEN** the project's rules define what counts as domain and I/O, or where
  interfaces and their fakes live
- **THEN** the classification and any extraction follow those rules, and a project
  rule outranks any built-in test-quality item it contradicts

#### Scenario: No rule or design defines the seam

- **WHEN** an extraction is needed and neither the project's rules nor the change's
  design define where the seam belongs
- **THEN** the loop halts with cause `weak-spec` rather than designing the seam
  itself

#### Scenario: A scaffolding red test is superseded

- **WHEN** a test written only to make the loop go red is superseded by a behaviour
  test that fails for the same regression
- **THEN** the scaffolding test is deleted in the same task

### Requirement: Every task names its oracle

Every implementation task SHALL have an oracle: either a test the task adds, or an
existing test the task names. A task that adds no test SHALL name the covering test in
its commit message. Coverage SHALL NOT be assumed without a named test.

#### Scenario: A task adds no test

- **WHEN** a task's behaviour is already fully covered by an existing test
- **THEN** its commit message names that test, and the task is not required to add one

#### Scenario: A task adds no test and names none

- **WHEN** a task commits behaviour change with no added test and no named covering
  test
- **THEN** the review reports it as a `gatedloop.test-quality` finding

### Requirement: Higher-layer tests carry a reason no lower layer suffices

A test added at the integration or acceptance layer SHALL cover a scenario that crosses
a layer boundary or that no lower-layer test can observe. A verdict that depends on a
model's output SHALL NOT be bound to a blocking gate. An undefined acceptance step
SHALL count as a failure, never as a skip.

#### Scenario: A scenario already covered by a unit test

- **WHEN** the loop derives integration cases from a change's spec scenarios and a
  scenario's rule is already covered by a named lower-layer test with no layer boundary
  involved
- **THEN** no integration case is derived for it, and the covering test is named

#### Scenario: A verdict depends on a model's reply

- **WHEN** a scenario's pass or fail depends on what a model replies
- **THEN** it is routed to the advisory `eval` gate, never to `verify`, `live-check`
  or `ci`

#### Scenario: A step definition is missing

- **WHEN** an acceptance scenario has a step with no definition
- **THEN** the loop treats the scenario as failing and writes the definition, and it
  never counts a skipped scenario as passing

### Requirement: Adopters are told what a blocking gate's runner must refuse

The setup documentation and onboarding SHALL state that a command bound to a blocking
gate must exit non-zero when a test is undefined or skipped for a missing
implementation, and must not retry a failing test until it passes. gatedloop SHALL NOT
claim to enforce this, because only the adopter's runner configuration can.

#### Scenario: Onboarding binds an acceptance gate

- **WHEN** `gates-init` binds `verify` or `live-check`
- **THEN** it tells the adopter that the bound command must fail on undefined steps
  and must not pass on retry

### Requirement: A change's failing tests are authored before implementation, by an agent that does not implement it

Unless the project declares `loop.test-author: inline`, a change SHALL pass through an
authoring phase before its first task. In that phase a test-author agent writes the
failing tests for every task of the change. Its inputs are the task list, the
change's spec scenarios and design, the public interfaces of the code involved, and
the project's test conventions. It SHALL NOT read function bodies of the code under
change or the contents of existing test files. It SHALL NOT write anything outside
the change's holding area. The authoring phase SHALL be dispatched by whoever
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

### Requirement: The test author works from the project's own test conventions

The test author SHALL start from `gates tests brief`. The brief SHALL be generated by
the shim from the change, the adopter's manifest and the rules-doc, and SHALL NOT be
written by an agent. It SHALL name:

- the project's rules tagged `Applies to: tests`;
- each task's hot-surface rules;
- the built-in test rule;
- the command the `unit` gate is bound to, printed and never run;
- existing test paths near each task's code;
- the project's shared fixtures and helpers.

Where a project test rule and a built-in item disagree, the project rule SHALL win.
Onboarding SHALL capture the project's test conventions as `Applies to: tests` rules.

#### Scenario: A project with test conventions

- **WHEN** the rules-doc has rules tagged `Applies to: tests`
- **THEN** the brief lists them for every task, whatever the hot surfaces, and the
  author's report shows that it applied them

#### Scenario: A project without test conventions

- **WHEN** no rule is tagged `Applies to: tests`
- **THEN** the brief says so and names the onboarding step that captures them

#### Scenario: Existing tests near the code

- **WHEN** existing test files share a directory or file stem with a task's code
- **THEN** the brief lists up to five of their paths, and the author follows their
  location and naming and uses the shared fixtures, without reading their contents

#### Scenario: The tests target is not an artifact

- **WHEN** `gates conventions sync` runs over a rules-doc with `Applies to: tests`
  rules
- **THEN** it emits none of them into the OpenSpec config, and `gates validate`
  accepts the target

#### Scenario: Onboarding captures test conventions

- **WHEN** `gates-init` runs its conventions capture
- **THEN** it drafts test-convention candidates from the project's existing material
  and confirms each with the adopter before writing it as an `Applies to: tests` rule

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

### Requirement: Authored tests are held undiscoverable, placed per task, and locked

Authored tests SHALL be committed in a holding area whose file names no test runner
discovers. `gates tests place <task>` SHALL move a task's tests onto their real paths
at the start of that task. It SHALL refuse when a real path has changed since
authoring other than by an earlier placement. `gates tests check` SHALL fail unless:

- every placed path is staged with exactly its handed-off content;
- every unplaced holding file matches the handoff;
- for a task with tests, a `unit` run recorded after placement failed for a reason
  other than a precondition. For a task reopened after completion, a red run recorded
  after its first placement satisfies this condition.

The commit gates SHALL run that check wherever they check the `ci` marker.

#### Scenario: The authoring commit

- **WHEN** the authored set is committed before the first task
- **THEN** the `ci` gate is unaffected by the held tests, and the commit is allowed

#### Scenario: The implementer edits a placed test

- **WHEN** a commit is attempted whose staged content changes a placed test
- **THEN** the commit is denied, naming the path and directing the implementer to
  record a test defect

#### Scenario: The implementer skips the red run

- **WHEN** a task commit is attempted with no failing `unit` run recorded after that
  task's tests were placed
- **THEN** the commit is denied, because red before green is required

#### Scenario: Two tasks extend one test file

- **WHEN** a later task's authored copy of a test file already placed by an earlier
  task is placed
- **THEN** it replaces the earlier content, and the lock applies to the new content

#### Scenario: A held test is edited by hand

- **WHEN** a holding-area file differs from the latest handoff at commit time
- **THEN** the commit is denied until the change goes through a re-handoff

#### Scenario: The commit bypasses the tool hook

- **WHEN** a commit is created by a path the tool-level hook does not see
- **THEN** the git-layer commit hook applies the same check

### Requirement: A wrong test goes back to its author, and a persistent disagreement halts

The implementer SHALL NOT correct an authored test. It SHALL record `gates tests defect
<task> --kind setup|assertion|green --detail <why>`, and the author SHALL be
re-dispatched for the task. `green` records that the placed tests passed before any
implementation, without claiming they are wrong. A task SHALL take at most two
`assertion` defects, then halt with cause `oracle-conflict`, at most three `setup`
defects, then halt with cause `weak-spec`, and at most one `green` defect, then halt
with cause `oracle-conflict`. A defect without a kind SHALL be refused.

#### Scenario: The implementer finds a defective test

- **WHEN** the implementer judges a placed test wrong
- **THEN** it records a test defect with its kind and reason, the author revises or
  defends that task's tests, and implementation resumes against the new handoff

#### Scenario: Placed tests are already green

- **WHEN** a task's placed tests pass on their first run and the task is not
  declared `characterization`
- **THEN** the implementer records a `green` defect instead of implementing against
  them, and the author either re-declares the task or rewrites its tests

#### Scenario: Fixture mistakes do not spend the behaviour cap

- **WHEN** a task has two `setup` defects and no `assertion` defect
- **THEN** a first `assertion` defect is still accepted

#### Scenario: A green defect spends neither other cap

- **WHEN** a task has one `green` defect and no other defect
- **THEN** a first `setup` and a first `assertion` defect are still accepted

#### Scenario: Tests still green after the author's answer

- **WHEN** a task already has one `green` defect and its re-placed tests pass on their
  first run again, with no declaration
- **THEN** a second `green` defect is refused, and the loop halts with cause
  `oracle-conflict`

#### Scenario: Author and implementer keep disagreeing

- **WHEN** two `assertion` defects have been recorded for a task
- **THEN** a third `assertion` defect is refused, and the loop halts with cause
  `oracle-conflict`, carrying both positions

### Requirement: Only the author may declare a task free of behaviour

A task that changes no behaviour SHALL be marked by the author with its reason. It
then needs no tests and no red run. The implementer SHALL NOT make that declaration.
The authored-set review SHALL judge every such claim.

#### Scenario: A docs-only task

- **WHEN** the author marks a documentation-only task as changing no behaviour
- **THEN** placement does nothing for it, the task commits without a red run, and the
  reason is recorded in the handoff

#### Scenario: A false claim

- **WHEN** a task marked as changing no behaviour plainly changes behaviour
- **THEN** the authored-set review reports it as a `gatedloop.test-quality` finding

### Requirement: Inline authorship is declared, and bound by the same lock

When the project declares `loop.test-author: inline`, the implementer SHALL run the
authoring phase itself, before its first task, into the same holding area, and SHALL
record the handoff as inline. Placement, the red run, the lock and defects SHALL apply
unchanged. An unknown `loop.test-author` value SHALL fail validation.

#### Scenario: The project opts out

- **WHEN** `.gates.yaml` declares `loop.test-author: inline`
- **THEN** no test-author agent is dispatched, the implementer authors every test
  before implementing, and the handoff is recorded as inline

#### Scenario: An unknown authorship value

- **WHEN** `.gates.yaml` declares `loop.test-author` with any value other than
  `separate` or `inline`
- **THEN** `gates validate` fails naming the key and the allowed values

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

### Requirement: The lock is verifiable at any commit

`gates tests check --ref <commit>` SHALL evaluate the lock's conditions against that commit's tree and the change's ledger as of that commit, for every task of the change, reading nothing from the working tree or the index. A change with no handoff at that commit SHALL pass and say so.

#### Scenario: The conditions at a commit

- **WHEN** the check runs against a commit
- **THEN** it requires each placed path to hold its placed content (or its base content where a defect or halt at an uncompleted task voided the placement), the holding area to match the latest handoff, and every placed task with tests to have the red `unit` run its opening requires

#### Scenario: A locked test edited past the commit hooks

- **WHEN** a commit on the change branch changed a placed test's content and no defect voided that placement
- **THEN** `gates tests check --ref <that commit>` fails, naming the path, the task and the commit

#### Scenario: A clean head

- **WHEN** every placed path at the head matches its placed content and every placed task has its red run recorded
- **THEN** the check passes and lists the tasks it verified

#### Scenario: No authored tests

- **WHEN** the change's ledger at the commit holds no handoff
- **THEN** the check passes and reports that there are no authored tests to verify

#### Scenario: A voided placement

- **WHEN** a defect row voided a task's placement and the path holds its base content at the commit
- **THEN** the check passes for that path

#### Scenario: A halt and a reopen after completion

- **WHEN** the head carries a halt at a completed `NO-TESTS` task and a reopened task whose re-placed tests went green against its committed code
- **THEN** the check passes for both, and the merge's head proof is not stopped by either

### Requirement: A task is completed once its tick is committed

For the lock, a task SHALL be completed at a ledger row when the commit that checked
the task in `tasks.md` precedes the first commit carrying that row. A row not yet
committed SHALL be judged against the checked state at `HEAD`. A tick staged in the
same commit as the row SHALL NOT make the task completed at that row.

#### Scenario: A halt committed after the task's commit

- **WHEN** task 0.3's `[x]` was committed and a later commit carries a halt row for 0.3
- **THEN** task 0.3 is completed at that halt

#### Scenario: A tick staged with the halt

- **WHEN** a halt row for task 2.1 and 2.1's `[x]` are staged in the same commit
- **THEN** task 2.1 is not completed at that halt, and the halt voids its placement

### Requirement: A halt at a completed task leaves its placement in force

A `halt` row SHALL void a task's placement only when the task is not completed at that
row. At a completed task, the placement, its holding-file removals and any `NO-TESTS`
or `CHARACTERIZATION` reason SHALL keep being checked as placed.

#### Scenario: Waiting on a source after the task is done

- **WHEN** task 0.3 is a completed `NO-TESTS` task and `gates halt record oracle-conflict --task 0.3` is recorded and committed
- **THEN** later commits are not refused for 0.3's behaviour-free reason, and 0.3 needs no new placement

#### Scenario: A halt in flight

- **WHEN** a halt is recorded for the task in flight
- **THEN** its placement is voided, as before, and the task is placed again after the restart

### Requirement: A test defect at a completed task reopens it

A `test-defect` row at a completed task SHALL void its placement and open the task again. The author SHALL re-hand off the task, and `gates tests place` SHALL place it as for any task. The reopened placement SHALL be satisfied by a red `unit` run recorded after the task's first placement, so the earlier red-before-green stays the record. The reopened placement's paths SHALL hold their re-handed-off content.

#### Scenario: A late e2e mismatch on a finished task

- **WHEN** task 2.4 is completed, a `setup` defect is recorded for it, the author re-hands off, and the tests are placed again
- **THEN** the lock checks the new content, accepts the red run recorded at 2.4's first placement, and does not demand a new red run against the committed code

#### Scenario: The author re-declares a completed task

- **WHEN** a completed task with tests green on placement takes a `green` defect, and the author re-hands it off as `CHARACTERIZATION` with a reason
- **THEN** a green `unit` run after the re-placement satisfies the lock, and the reason is recorded in the handoff for review to judge

#### Scenario: A reopened test edited by the implementer

- **WHEN** a reopened task's re-placed test differs from its re-handed-off content
- **THEN** the commit is refused as for any placed test

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

### Requirement: A task's oracle tag is held to the approved plan

When a change's `tasks.md` carries an oracle tag, the approval sha SHALL also cover its `(task id, tag)` pairs, without checkbox state or task text, and a plan with no tag SHALL hash as before. The handoff, the lock and `gates tests check --ref` SHALL refuse a task whose tag in the evaluated tree differs from its tag in the merge target's `tasks.md`, naming the task, both tags and that the plan is amended on the target and re-attested.

#### Scenario: A retag on the change branch

- **WHEN** the target's `tasks.md` tags 5.1 `[oracle: integration]` and the change branch retags it `[oracle: unit characterization]`
- **THEN** the commit is refused, naming 5.1, both tags and the amend-and-re-attest route

#### Scenario: A retag on the target after approval

- **WHEN** an approved plan's tag for 5.1 is edited on the target
- **THEN** `check-implement` refuses until the change is re-attested

#### Scenario: Ticking a task

- **WHEN** a task's `[ ]` becomes `[x]`
- **THEN** the approval sha is unchanged

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
