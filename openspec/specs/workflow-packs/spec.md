# workflow-packs Specification

## Purpose
A change's OpenSpec schema is its workflow: the loop dispatches on it, adopters can
install and inspect a workflow at any time, and the two shapes no upstream schema
covers (a bugfix whose failing repro precedes the plan, and an architecture decision
with no implementation phase) ship as packs that declare artifacts, never stack
commands.

## Requirements

### Requirement: The apply flow dispatches on the change's schema
`/gatedloop:tdd-apply` SHALL read the selected schema from the change's `.openspec.yaml` and route to the flow that schema declares, rather than assuming feature work. The route SHALL be decided from the schema's structure and its declared flow, never from the schema's name, so that a project's fork of a pack keeps the pack's flow.

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
- **WHEN** a schema declares a flow value gatedloop does not know
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

### Requirement: The bugfix pack inverts the test-first order
The `bugfix` schema SHALL carry a `report` artifact recording the failing reproduction and the root cause, and its flow SHALL treat that reproduction as the oracle rather than deriving a test from a spec.

#### Scenario: The repro must fail before any fix
- **WHEN** the bugfix flow begins implementation
- **THEN** the recorded reproduction is run first and must be RED; a reproduction that passes halts the flow, because it does not reproduce the reported bug

#### Scenario: The fix is proven by the same reproduction
- **WHEN** the fix is applied
- **THEN** the same reproduction passes, and it is committed together with the fix so the bug is pinned against regression

#### Scenario: Every bug fix records a spec delta
- **WHEN** the bugfix flow completes
- **THEN** a spec delta exists for the change — no bug fix may land without one

#### Scenario: The bug exposed a gap in the specs
- **WHEN** no existing requirement covers the behaviour the bug violated
- **THEN** the delta ADDS the scenario that would have caught it, so `verify` gains coverage the specs were missing

#### Scenario: The specs were already correct
- **WHEN** an existing requirement already described the correct behaviour and only the implementation was wrong
- **THEN** the delta records that explicitly as a MODIFIED requirement restating the behaviour, so the fix is attributed to implementation rather than to a specification gap

### Requirement: The architecture pack ends at an accepted decision
The `architecture` schema SHALL produce a decision record as its terminal artifact and SHALL NOT require an implementation phase.

#### Scenario: The workflow completes without code
- **WHEN** every artifact in the architecture schema is complete
- **THEN** the change is complete, with no `tasks.md` and no implementation expected

#### Scenario: The schema is valid without an apply block
- **WHEN** the architecture schema is checked with `openspec schema validate`
- **THEN** it validates despite declaring no `apply` block

### Requirement: Packs declare artifacts, never stack commands
A shipped pack's schema SHALL NOT name any project-specific test, build, or probe command in its templates or instructions. Verification is expressed as an abstract gate.

#### Scenario: A pack refers to verification
- **WHEN** a pack's instruction needs the project's tests or probes to run
- **THEN** it names `gates run <gate>` and the binding is resolved from the adopter's `.gates.yaml`

#### Scenario: A pack is audited for coupling
- **WHEN** shipped pack files are checked for tool names such as pytest, cucumber, gherkin-lint, cargo or npm
- **THEN** none appear

### Requirement: Packs install by the community-schema convention
Packs SHALL be installed by copying a bundle into the project's `openspec/schemas/<name>/`, guided by an agent-readable install document.

#### Scenario: An agent installs a pack
- **WHEN** a user asks for a pack to be installed
- **THEN** the agent follows the install document to copy the bundle preserving its structure, activates it, and validates it with `openspec schema validate`

#### Scenario: The absence of an update path is disclosed
- **WHEN** a pack is installed
- **THEN** the documentation states that installed schemas have no upstream update path and will drift

### Requirement: Onboarding offers workflow selection and installation
Onboarding SHALL ask which workflows a project wants and install the chosen ones, rather than leaving the user to discover the community catalog unaided.

#### Scenario: A project is onboarded
- **WHEN** the onboarding command runs
- **THEN** it presents the available workflows — the bundled schema, the community catalog, and the shipped packs — with a one-line description of what each is for

#### Scenario: The user selects workflows
- **WHEN** the user chooses one or more workflows to install
- **THEN** they are installed into the project's `openspec/schemas/`, activated, and validated

#### Scenario: The user wants only the bundled workflow
- **WHEN** the user declines the community schemas and packs
- **THEN** onboarding completes normally with the bundled schema alone, and nothing is installed

#### Scenario: The user asks what is already installed
- **WHEN** the set of available workflows must be reported
- **THEN** it is read from OpenSpec's own schema resolution rather than from a list gatedloop maintains separately

### Requirement: Workflow installation is available at any time
Selecting and installing a workflow SHALL be reachable on its own, independently of onboarding, so a project can add one when the need appears rather than only at setup.

#### Scenario: An established project needs a new workflow
- **WHEN** a team that onboarded previously reaches work its current workflows do not fit
- **THEN** they can select and install an additional workflow in one step, without re-running onboarding

#### Scenario: Onboarding reuses the same path
- **WHEN** onboarding reaches workflow selection
- **THEN** it invokes the same capability rather than carrying its own copy of the selection and install procedure

### Requirement: An installed workflow can be inspected before it is trusted
gatedloop SHALL be able to report what a schema delivers, determining structural facts in code and leaving fit and coherence to judgement.

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
