## MODIFIED Requirements

### Requirement: The apply flow dispatches on the change's schema
`/specloop:tdd-apply` SHALL read the selected schema from the change's `.openspec.yaml` and route to the flow that schema declares, rather than assuming feature work. The route SHALL be decided from the schema's structure and its declared flow, never from the schema's name, so that a project's fork of a pack keeps the pack's flow.

#### Scenario: A feature change runs the feature loop
- **WHEN** a change whose schema declares an implementation phase that tracks a file, and declares no flow, is applied
- **THEN** the standard per-task TDD loop runs: red, green, `gates run ci`, convention review, atomic commit

#### Scenario: A bugfix change runs the bugfix loop
- **WHEN** a change whose schema declares the regression-first flow is applied
- **THEN** the regression-first flow runs, in which the recorded repro is the first thing executed

#### Scenario: A project's fork of the bugfix pack keeps its flow
- **WHEN** a change uses a project-local schema with a different name that declares the regression-first flow
- **THEN** it is routed to the regression-first flow exactly as the shipped `bugfix` pack is

#### Scenario: A schema named bugfix that declares no flow
- **WHEN** a change uses a schema named `bugfix` that does not declare the regression-first flow
- **THEN** it is routed by its structure alone, because the name carries no meaning to dispatch

#### Scenario: An unknown flow is declared
- **WHEN** a schema declares a flow value Specloop does not know
- **THEN** dispatch fails loud naming the value and the known flows, and does not fall back to the default loop

#### Scenario: A change whose schema has no implementation phase
- **WHEN** a change using a schema with no `apply` block is passed to the apply flow
- **THEN** the flow refuses cleanly, explains that this workflow ends at its final artifact, and does not improvise a task list

#### Scenario: An implementation phase that tracks nothing
- **WHEN** a change uses a schema whose `apply` block declares no `tracks`
- **THEN** the flow refuses it exactly as it refuses a schema with no `apply` block, because there is nothing to tick off

#### Scenario: The refusal does not depend on interpreting an instruction response
- **WHEN** the flow determines whether a change has an implementation phase
- **THEN** it decides from the resolved schema's own structure, so a plausible-looking but empty instruction response cannot be mistaken for permission to proceed

#### Scenario: The dispatch decision needs no third-party dependency
- **WHEN** the route is decided on a machine without PyYAML
- **THEN** it is decided correctly from the schema's top-level `apply` and flow declarations, and a shape the built-in reader does not recognise fails loud rather than being read as absent

### Requirement: An installed workflow can be inspected before it is trusted
Specloop SHALL be able to report what a schema delivers, determining structural facts in code and leaving fit and coherence to judgement.

#### Scenario: An adopter asks what a workflow produces
- **WHEN** a schema is inspected
- **THEN** the report enumerates its artifacts in dependency order, states whether it has an implementation phase, whether that phase tracks anything, and which flow the schema declares

#### Scenario: The structural facts are not left to a model
- **WHEN** the presence of an implementation phase is determined
- **THEN** it is resolved deterministically from the schema, on the same grounds as hot-surface selection, because a missed `apply` block causes the loop to improvise implementation

#### Scenario: An apply block with nothing to track
- **WHEN** an inspected schema has an `apply` block with no `tracks`
- **THEN** the report warns that dispatch will treat the schema as decision-terminal, and says that omitting `apply` is the correct spelling for such a schema

#### Scenario: A schema hard-codes stack commands
- **WHEN** a schema's templates or instructions name project-specific test, build or probe tools inside inline code or a fenced block
- **THEN** the inspection reports them and cross-checks them against the gates the project declares, so an unbound coupling is visible at install time rather than at first use

#### Scenario: A tool is named in prose
- **WHEN** a product or tool name appears only in ordinary prose, outside any code span or fenced block
- **THEN** the inspection does not report it, because a noun in a sentence is not an invocation

#### Scenario: Inspection reports rather than blocks
- **WHEN** an inspection produces findings
- **THEN** the schema is still installable and unmodified, because the adopter may have reasons the inspection cannot see

#### Scenario: A cyclic or unreachable artifact graph
- **WHEN** a schema declares `requires` relationships that cannot be satisfied
- **THEN** the inspection reports it as a structural defect rather than presenting the workflow as usable
