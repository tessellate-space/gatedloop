# plugin-positioning Specification

## Purpose
Where gatedloop's boundary sits and how that is written down. The manifests and docs separate what gatedloop owns (the gated loop, onboarding) from what it delegates (artifact authoring to OpenSpec schemas, commands to the adopter's `.gates.yaml`), and a written rejection test and a single conventions source keep that boundary from drifting.

## Requirements

### Requirement: The plugin manifests state the delegation boundary
The `description` field in `.claude-plugin/plugin.json` and in the `plugins[]` entry of `.claude-plugin/marketplace.json` SHALL describe gatedloop as closing the loop between an approved task list and a verified merge, and SHALL NOT describe it as providing proposals, specifications, or a full development lifecycle.

#### Scenario: A reader installs from the marketplace listing
- **WHEN** a user reads the plugin description before installing
- **THEN** the description names what gatedloop carries (approved tasks → verified on main) and what the adopter must bring (a schema and a stack)

#### Scenario: The description does not claim upstream's work
- **WHEN** the manifest descriptions are checked against the boundary
- **THEN** they contain no claim to author proposals, specs, designs, or workflow shapes

### Requirement: README and SETUP separate what is owned from what is delegated
`README.md` and `SETUP.md` SHALL each identify three owners explicitly: work delegated upstream to OpenSpec and community schemas, work delegated to the adopting project through the gate manifest, and work owned by gatedloop.

#### Scenario: A new adopter asks what they must supply
- **WHEN** a reader follows SETUP
- **THEN** they can tell, without reading source, that they supply a schema selection and a gate manifest, and that gatedloop supplies the loop, its gates, their enforcement, and the onboarding that produces the manifest

#### Scenario: OpenSpec's prerequisite status is justified, not asserted
- **WHEN** a reader asks why OpenSpec is required rather than optional
- **THEN** the docs name the four things the loop consumes from a task source — a stable work-unit identity, a checkable task cursor, spec scenarios as a behavioural oracle, and a promotion step — and what breaks without each

### Requirement: A written rejection test arbitrates scope
The conventions rules-doc SHALL contain a scope test that answers, for a proposed addition, whether it belongs in gatedloop.

#### Scenario: A proposed addition would author an artifact
- **WHEN** a contributor proposes shipping an artifact template or authoring prompt that a maintained upstream schema already provides
- **THEN** the rejection test resolves it as out of scope, directing the work upstream or to schema selection

#### Scenario: A proposed addition names a stack command
- **WHEN** a contributor proposes hard-coding a test, build, or probe command into a shipped prompt
- **THEN** the rejection test resolves it as out of scope, directing it to a gate in the project's gate manifest

#### Scenario: A proposed addition makes a stated guarantee enforceable
- **WHEN** a contributor proposes converting a prompt-stated rule into a hook-enforced invariant
- **THEN** the rejection test resolves it as in scope

#### Scenario: The four questions disagree or none of them fits
- **WHEN** a proposed addition is not settled by the four questions
- **THEN** the test falls back to the single question they are instances of — does it move a phase from `act` to `close`, or move a team up a rung faster — which is answerable by scoring rather than by argument

### Requirement: Conventions rules are delivered to artifact steps
`openspec/config.yaml` SHALL express `rules` in the form the OpenSpec CLI accepts: keyed by artifact id, with each value an array of strings.

#### Scenario: Creating a change emits no rules warning
- **WHEN** `openspec new change <name>` is run in the gatedloop repo
- **THEN** the CLI does not report that rules are being ignored for any key

#### Scenario: Rules reach the artifact instruction
- **WHEN** `openspec instructions proposal --change <name> --json` is inspected
- **THEN** its `rules` field is a non-empty array containing the repo's proposal rules

### Requirement: Conventions have one source, and the config block is generated from it
The rule-id prose SHALL live in a single conventions source file outside `openspec/config.yaml`, and the `rules:` block in `openspec/config.yaml` SHALL be generated from that source rather than maintained by hand.

#### Scenario: A rule is added
- **WHEN** a new rule is written in the conventions source with the artifact steps it applies to
- **THEN** running the generation command produces the corresponding entries in `openspec/config.yaml` without either document being edited by hand

#### Scenario: A review-only rule is not emitted
- **WHEN** a rule applies to code review rather than to an artifact step
- **THEN** it is resolvable by the review gate and is absent from the generated config block, because no artifact step exists to receive it

#### Scenario: The generated block has drifted from its source
- **WHEN** `openspec/config.yaml`'s `rules:` no longer match what the conventions source would generate
- **THEN** manifest validation fails loudly and names the command that regenerates it

#### Scenario: An adopting project generates its own config
- **WHEN** the generation command is run in a project that is not this repository
- **THEN** it reads that project's conventions source and writes that project's `openspec/config.yaml`

### Requirement: The docs position gatedloop on the adoption ladder
`README.md` SHALL describe what gatedloop delivers in terms of the 0–4 rung scale — `none`, `advise`, `observe`, `act`, `close` — and SHALL state the rungs before relying on them.

#### Scenario: A reader asks what gatedloop adds over OpenSpec alone
- **WHEN** a reader reaches the positioning statement
- **THEN** it identifies gatedloop as supplying the advanced level — unattended subagents, hook-enforced gates, and oracles — that a team otherwise has to build itself

#### Scenario: Each shipped component is attributed to a rung
- **WHEN** the docs describe what is shipped
- **THEN** each component is mapped to the advanced-level need it satisfies, rather than listed as an undifferentiated feature set

#### Scenario: The limit is stated alongside the claim
- **WHEN** the docs claim phases that close
- **THEN** they also state that Requirements does not move and System design stops at `act`, because neither has a machine-readable verdict

### Requirement: Gate, oracle and hook are defined where the contract is introduced
`SETUP.md` SHALL define all three terms at the point a reader first meets the gate contract, and SHALL explain why the contract is an exit code.

#### Scenario: A reader meets the gate contract
- **WHEN** the gate contract is introduced
- **THEN** gate (the required checkpoint), oracle (the machine-readable verdict it reads back) and hook (what makes it non-optional) are each defined

#### Scenario: A reader asks why a gate cannot report prose
- **WHEN** the exit-code constraint is stated
- **THEN** the reason is given — a verdict a machine can read, rather than a human's recollection of having checked — instead of being asserted as a convention

### Requirement: Approval is recorded in the change's metadata
A change SHALL record who approved its plan, when, and against which artifact content, in its `.openspec.yaml` metadata file rather than in artifact prose.

#### Scenario: An approved change carries its provenance
- **WHEN** a change's plan has been approved
- **THEN** its `.openspec.yaml` carries `approved_by`, `approved_at`, and `approved_sha` pinning the artifact content that was approved

#### Scenario: The metadata remains valid to OpenSpec
- **WHEN** a change carrying the approval keys is validated with `openspec validate --strict`
- **THEN** it reports valid, and `openspec status --json` and `openspec instructions --json` behave as they do without the keys

#### Scenario: Approval is machine-readable
- **WHEN** a consumer needs to know whether a change is approved
- **THEN** it parses the metadata file directly, rather than pattern-matching a heading in generated markdown

#### Scenario: A post-approval edit is detectable
- **WHEN** an artifact is edited after approval was recorded
- **THEN** the artifact content no longer matches `approved_sha`, so the stale approval can be detected rather than continuing to read as valid

#### Scenario: Approval is not a fork of upstream templates
- **WHEN** the approval requirement is implemented
- **THEN** no upstream schema or template is forked or vendored to carry it

#### Scenario: The requirement survives a schema change
- **WHEN** a project switches to a different upstream schema
- **THEN** the approval requirement still applies, because change metadata travels with the change rather than with the schema

### Requirement: Onboarding is documented as an owned surface
`README.md` and `SETUP.md` SHALL present getting a project onto the loop as something gatedloop owns, alongside enforcement, rather than as a secondary benefit.

#### Scenario: A reader asks what gatedloop does for them
- **WHEN** a reader reaches the statement of what gatedloop owns
- **THEN** onboarding appears as an owned surface next to the loop and its enforcement, not only in a list of caveats or risks

#### Scenario: A brownfield adopter looks for a starting point
- **WHEN** a reader with an existing codebase follows SETUP
- **THEN** the path from an unconfigured project to a first passing gate run is stated as an ordered sequence with a named command for each step

### Requirement: The rules-doc explains why rule-ids exist
The conventions rules-doc SHALL record the rationale for identifying rules rather than inlining rule prose.

#### Scenario: A contributor proposes inlining rule prose
- **WHEN** someone proposes replacing rule-ids with prose written at each call site
- **THEN** the rules-doc supplies the counter-argument: findings become citable, surfaces can select a subset, dangling references are detectable, and one document serves both consumers

#### Scenario: A reviewer meets a rule-id for the first time
- **WHEN** a reader encounters a rule-id in a review finding or a surface definition
- **THEN** the rules-doc explains what an id is for at the point of use

### Requirement: Rule-ids remain resolvable by the review gate
Moving the conventions out of `openspec/config.yaml` SHALL NOT break `convention-review`: the rule-id prose SHALL remain at a location the shim's rule resolution reads.

#### Scenario: The review agent cites a rule-id
- **WHEN** `convention-review` runs on a diff and reports a finding
- **THEN** it can still resolve and cite the rule-id from the configured `conventions.rules-doc`

#### Scenario: A surface references an undefined rule-id
- **WHEN** a surface in the gate manifest names a rule-id absent from the rules-doc
- **THEN** manifest validation fails loudly rather than silently dropping the rule

### Requirement: The plugin is named gatedloop

The plugin, its marketplace, its command namespace, its state directory, its change
metadata keys, its commit-status contexts, its record branches, its built-in rule ids
and its hook markers SHALL use the name `gatedloop`. The `gates` shim, `.gates.yaml`
and the gate names SHALL keep their names.

#### Scenario: A fresh install

- **WHEN** a project installs the plugin and runs onboarding
- **THEN** its commands are `/gatedloop:*`, its state is under `.gatedloop/`, and the
  statuses it publishes are `gatedloop/<gate>`

### Requirement: The earlier name is read loudly for one release

Through 0.8.x the shim SHALL read every earlier `specloop` identifier when the new one
is absent, preferring the new, and SHALL warn once per command that the earlier name
stops working in 0.9.0 and names `gates migrate-name`. Publishing a gate status SHALL
post both contexts. A project holding both state directories SHALL be refused, naming
the command.

#### Scenario: A project not yet migrated

- **WHEN** a project has only `.specloop/` and `x-specloop-*` keys
- **THEN** every command works, reading the earlier names, and prints the one-line
  migration warning naming 0.9.0

#### Scenario: Both state directories

- **WHEN** a project has both `.specloop/` and `.gatedloop/`
- **THEN** the shim refuses, naming `gates migrate-name`

### Requirement: A project migrates to the new name by one command

`gates migrate-name` SHALL move the state directory, rewrite earlier metadata keys in
active changes and earlier markers in a composed hook, and print each settings and
branch-protection edit it does not make. It SHALL never commit or push, SHALL leave
archived changes untouched, and SHALL exit 0 when nothing remains to migrate.

#### Scenario: Migrating a project

- **WHEN** `gates migrate-name` runs in a project with `.specloop/` and one active
  change carrying `x-specloop-approved-by`
- **THEN** the directory is `.gatedloop/`, the key reads `x-gatedloop-approved-by`
  with the same value, and the printed list names the branch-protection context to
  rename

#### Scenario: Nothing to migrate

- **WHEN** a project already uses only the new names
- **THEN** `gates migrate-name` changes nothing and exits 0
