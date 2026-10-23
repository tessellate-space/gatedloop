## ADDED Requirements

### Requirement: Specloop ships a built-in test-quality rule that review always applies

Specloop SHALL ship a stack-agnostic `specloop.test-quality` rule inside the plugin.
`gates rules` SHALL list it for every diff, together with its source path, whatever
surfaces are hot. The convention review SHALL apply it to every test the diff adds or
changes. Each finding SHALL cite the rule-id and the numbered item it violates. The
rule text SHALL NOT name any project-specific tool, framework or library.

#### Scenario: A diff touches no declared surface

- **WHEN** `gates rules` runs on a diff that makes no surface hot
- **THEN** it still lists `specloop.test-quality` and the path of the file that
  defines it

#### Scenario: The rule source resolves from an installed plugin

- **WHEN** `gates rules` runs from the plugin's installed cache location
- **THEN** the path it prints for the built-in rule exists and contains the rule's
  section, resolved relative to the plugin, never to the project

#### Scenario: A test asserts a declared default

- **WHEN** a diff adds a test whose only assertion is that a newly declared field
  holds its declared default
- **THEN** the review reports it as a `specloop.test-quality` finding citing the item
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
- **THEN** the review reports it as a `specloop.test-quality` finding

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
implementation, and must not retry a failing test until it passes. Specloop SHALL NOT
claim to enforce this, because only the adopter's runner configuration can.

#### Scenario: Onboarding binds an acceptance gate

- **WHEN** `gates-init` binds `verify` or `live-check`
- **THEN** it tells the adopter that the bound command must fail on undefined steps
  and must not pass on retry
