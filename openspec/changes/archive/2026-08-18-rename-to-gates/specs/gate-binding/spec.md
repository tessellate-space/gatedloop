## ADDED Requirements

### Requirement: The gate-binding seam is named for what it binds
The shim, its manifest, its JSON schema, its template, and its onboarding command SHALL be named after gates rather than after a harness.

#### Scenario: An adopter invokes the shim
- **WHEN** the plugin is installed and an adopter runs the shim from the Bash tool
- **THEN** `gates validate`, `gates run <gate>`, `gates surfaces`, `gates rules`, and `gates init` all resolve and behave as their predecessors did

#### Scenario: An adopter scaffolds a new project
- **WHEN** the onboarding command runs in a project with no manifest
- **THEN** it writes `.gates.yaml` carrying a `gatesVersion` key, and no file named `.harness.yaml` is created

#### Scenario: The manifest is validated against its schema
- **WHEN** a `.gates.yaml` is validated
- **THEN** it is checked against `schema/gates.schema.json`, and the gate contract, `surfaces[]` shape, and hot-set rule are unchanged from the previous name

### Requirement: The old name keeps working for one release and says so
Migration SHALL NOT produce a silent failure or an uninformative one. The previous entry point and manifest filename SHALL continue to work while reporting that they are deprecated and naming their replacement.

#### Scenario: An adopter invokes the old shim name
- **WHEN** the previous `harness` entry point is invoked with any arguments
- **THEN** it forwards to the new shim with the same arguments and the same exit code, and prints a deprecation notice to stderr naming `gates`

#### Scenario: A project still has the old manifest filename
- **WHEN** the shim runs in a project that has `.harness.yaml` and no `.gates.yaml`
- **THEN** it reads the old file, succeeds, and warns loudly that the file should be renamed to `.gates.yaml`

#### Scenario: The deprecation is never silent
- **WHEN** either compatibility path is exercised
- **THEN** a message is emitted; neither path succeeds quietly, so migration cannot be indefinitely postponed by accident

#### Scenario: Both manifests are present
- **WHEN** a project contains both `.gates.yaml` and `.harness.yaml`
- **THEN** the new file wins and the shim reports that the old one is being ignored and can be deleted

### Requirement: The manifest version key discriminates the format
The manifest SHALL carry a `gatesVersion` key, and the loader SHALL use the presence of the old or new key to determine which vintage it is reading.

#### Scenario: A current manifest is loaded
- **WHEN** a manifest carrying `gatesVersion: 1` is read
- **THEN** it loads without any deprecation warning

#### Scenario: A legacy manifest is loaded
- **WHEN** a manifest carrying `harnessVersion: 1` is read
- **THEN** it loads, and the shim warns that the key should be renamed to `gatesVersion`

### Requirement: No shipped asset refers to the retired name
Shipped prompts, skills, agents, hooks, and documentation SHALL NOT invoke or reference the retired name, except in the compatibility forwarder and in explicit migration guidance.

#### Scenario: A shipped prompt invokes a gate
- **WHEN** any command, skill, or agent instructs that a gate be run
- **THEN** it names the new shim, so an adopter following the prompt never triggers the deprecation path

#### Scenario: The repository is swept for stale references
- **WHEN** the repository is searched for the retired name after this change
- **THEN** the only matches are the compatibility forwarder, the migration notes in the reader-facing docs, and historical records such as archived changes and the design memo
