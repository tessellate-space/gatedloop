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

#### Scenario: The authored set draws a finding

- **WHEN** the authored-set review reports a test that asserts only a declared default
- **THEN** the author revises it before any implementation begins, and the review
  runs again

### Requirement: Authored tests are held undiscoverable, placed per task, and locked

Authored tests SHALL be committed in a holding area whose file names no test runner
discovers. `gates tests place <task>` SHALL move a task's tests onto their real paths
at the start of that task. It SHALL refuse when a real path has changed since
authoring other than by an earlier placement. `gates tests check` SHALL fail unless:

- every placed path is staged with exactly its handed-off content;
- every unplaced holding file matches the handoff;
- for a task with tests, a `unit` run recorded after placement failed for a reason
  other than a precondition.

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
- **THEN** it requires each placed path to hold its placed content (or its base content where a defect or halt voided the placement), the holding area to match the latest handoff, and every placed task with tests to have a red `unit` run recorded after its placement

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
