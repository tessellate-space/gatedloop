## ADDED Requirements

### Requirement: The bootstrapper covers the OpenSpec prerequisite chain

`/specloop:gates-init` SHALL detect whether the OpenSpec CLI is installed and, if
not, offer to install it. It SHALL then run `openspec init --tools claude` (subject
to the local-edit confirmation gate below) before proceeding to gate binding, rather
than requiring the adopter to have already run these steps by hand.

#### Scenario: The OpenSpec CLI is missing

- **WHEN** onboarding starts in a project with no OpenSpec CLI available
- **THEN** it offers to install it
- **AND** it waits for the adopter's confirmation before doing so

#### Scenario: OpenSpec is not yet initialized in the project

- **WHEN** onboarding starts in a project with the OpenSpec CLI present but no
  `openspec/` directory
- **THEN** it runs `openspec init --tools claude` (subject to the local-edit
  confirmation gate) rather than stopping and telling the adopter to run it manually

### Requirement: Onboarding confirms before an `openspec init` run that could overwrite local edits

`/specloop:gates-init` SHALL check for local edits to generated OpenSpec assets
before invoking `openspec init --tools claude`. Where edits are detected, it SHALL
stop and require the adopter's explicit confirmation before proceeding, and SHALL
name `openspec schema fork <source> <name>` as the durable alternative to editing a
generated file. A warning that the adopter can silently pass through SHALL NOT
satisfy this requirement.

#### Scenario: Generated OpenSpec files look locally modified

- **WHEN** onboarding is about to run `openspec init --tools claude` and detects
  local edits to previously generated files
- **THEN** it stops and asks the adopter to confirm before proceeding
- **AND** it names `openspec schema fork <source> <name>` as the alternative

#### Scenario: The adopter declines to proceed

- **WHEN** the adopter declines to run `openspec init --tools claude` after being
  warned about local edits
- **THEN** onboarding leaves the existing generated files untouched
- **AND** it reports which downstream steps cannot proceed as a result

#### Scenario: No local edits are detected

- **WHEN** onboarding is about to run `openspec init --tools claude` and no local
  edits to generated files are detected
- **THEN** it proceeds without asking for confirmation

### Requirement: Conventions capture is a core onboarding step

`/specloop:gates-init` SHALL harvest existing conventions material — contributing
guides, agent instruction files, linter or formatter configuration, and an existing
OpenSpec project's `openspec/config.yaml` `context:` block — into candidate
rule-doc entries, present them to the adopter, and write only confirmed entries
into the project's rules-doc. It SHALL then wire the confirmed rule ids into
`.gates.yaml` `surfaces[].rules` and run `gates conventions sync`. This step SHALL
run as part of every onboarding pass, not as an optional step the adopter must
separately request.

#### Scenario: Harvestable material exists

- **WHEN** onboarding finds a contributing guide, an agent instruction file, linter
  configuration, or an `openspec/config.yaml` `context:` block with checkable
  conventions in it
- **THEN** it drafts candidate rule-doc entries from that material
- **AND** it presents each candidate to the adopter before writing anything
- **AND** confirmed entries are written into the project's rules-doc

#### Scenario: A candidate rule-doc entry is confirmed

- **WHEN** the adopter confirms a drafted rule-doc entry
- **THEN** onboarding writes it with an `Applies to:` line defaulting to `code`
  unless the adopter specifies an artifact id
- **AND** onboarding wires the surfaces the adopter selects to reference it
- **AND** onboarding runs `gates conventions sync` after all confirmed entries are
  written

#### Scenario: No harvestable material exists

- **WHEN** onboarding finds no contributing guide, agent instruction file, linter
  configuration, or `context:` block with checkable content
- **THEN** onboarding says so plainly and completes the step without writing
  placeholder content

### Requirement: The conventions source projects differently into its two consumers

Documentation and onboarding output describing how the conventions source reaches
`convention-review` and OpenSpec's artifact-authoring steps SHALL state that they
are two different projections of the same source, not two consumers of identical
content: the rules-doc entire and unfiltered feeds `convention-review` via
`.gates.yaml`'s `conventions.rules-doc`, and only the subset of rules whose
`Applies to:` line names a real artifact id is projected by `gates conventions
sync` into `openspec/config.yaml`'s `rules:` block. A rule scoped `Applies to: code`
SHALL NOT be described as reaching `openspec/config.yaml`.

#### Scenario: A rule is scoped to `code` only

- **WHEN** a rule-doc entry's `Applies to:` line names only `code`
- **THEN** `gates conventions sync` does not write it into `openspec/config.yaml`
- **AND** onboarding does not describe this as a defect or a gap to be fixed later

#### Scenario: A rule is scoped to an artifact id

- **WHEN** a rule-doc entry's `Applies to:` line names a real artifact id from the
  project's active schema
- **THEN** `gates conventions sync` projects it into `openspec/config.yaml`'s
  `rules:` block for that artifact id

### Requirement: The OpenSpec contract version is probed, not assumed

The shim SHALL record the OpenSpec CLI version it was last verified against. A
doctor check SHALL compare it against the installed `openspec --version` and warn
loudly on a mismatch. A version mismatch SHALL NOT fail `gates validate` or block
onboarding.

#### Scenario: The installed OpenSpec CLI matches the tested version

- **WHEN** the doctor check runs and the installed OpenSpec CLI version matches the
  recorded tested version
- **THEN** no warning is produced

#### Scenario: The installed OpenSpec CLI version differs

- **WHEN** the doctor check runs and the installed OpenSpec CLI version differs from
  the recorded tested version
- **THEN** it warns loudly, naming both versions
- **AND** it does not fail `gates validate` or stop onboarding on that basis alone

### Requirement: A doctor preflight diagnoses the reachable states of an invisible install

`/specloop:gates-init` SHALL run a `gates doctor` check as its first step, covering
at minimum: OpenSpec CLI presence and version (per the previous requirement),
whether `.gates.yaml`'s `gatesVersion` is current, and whether the plugin's own
commands and hooks are registered for the active session. Where the failure is that
no Specloop surface is reachable at all, project documentation SHALL carry a
troubleshooting note naming `CLAUDE_CONFIG_DIR` config-profile mismatch as the first
thing to check, runnable independently of any Specloop command.

#### Scenario: A partial-visibility failure is present

- **WHEN** the plugin's commands are registered but a hook is stale, or the OpenSpec
  CLI is missing, or `gatesVersion` is out of date
- **THEN** `gates doctor` names the specific missing or stale piece

#### Scenario: Nothing is wired at all

- **WHEN** no Specloop command, skill, or session-brief output appears in a session
- **THEN** no in-session diagnostic can run, and project documentation names
  `CLAUDE_CONFIG_DIR` as the first thing to check from a plain shell

### Requirement: Onboarding stops honestly when a project has no scaffold to bind to

`/specloop:gates-init` SHALL distinguish a project whose stack is simply unlisted
(real code and build targets exist, but none match the curated detector list) from
a project with no scaffold at all (no source files, no build targets, nothing to
run). In the former case it SHALL ask the adopter to supply the `ci` gate body by
hand, as today. In the latter case it SHALL NOT ask the adopter to invent a gate
command; it SHALL name what is missing and stop, and the adopter MAY return once a
scaffold exists.

#### Scenario: The stack is unlisted but a real project exists

- **WHEN** onboarding detects no curated-list match but finds source files and some
  existing build or run target
- **THEN** it asks the adopter to supply the `ci` gate body by hand
- **AND** onboarding completes with a valid manifest, as today

#### Scenario: No scaffold exists at all

- **WHEN** onboarding finds no source files, build markers, or targets of any kind
- **THEN** it names what is missing
- **AND** it stops without asking the adopter to invent a gate command
- **AND** it does not write a `.gates.yaml` binding a fabricated `ci` command
