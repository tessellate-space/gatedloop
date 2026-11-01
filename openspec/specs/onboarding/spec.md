# onboarding Specification

## Purpose
Get a project onto the loop: `/gatedloop:gates-init` bootstraps the full prerequisite
chain — doctor preflight, OpenSpec CLI and init, gate binding by explicit choice,
conventions capture, the integration ask, permission scaffolding — and the
SessionStart brief meets a project honestly wherever it stands, including
half-onboarded and not-onboarded states.

## Requirements

### Requirement: The bootstrapper offers candidates and binds only what is chosen

`/gatedloop:gates-init` SHALL detect build-system candidates from a curated list,
present what it found, and bind a gate only from an adopter's explicit choice. It
SHALL NOT select a gate body automatically, even when exactly one candidate is
detected.

Naming a tool in order to offer it is permitted by `stack-agnostic-prompts`; naming
one in order to invoke it is not. Invocation SHALL go through `gates run <gate>`.

#### Scenario: Exactly one candidate is detected

- **WHEN** onboarding detects a single build system in the project
- **THEN** it presents that candidate and the gate body it would bind
- **AND** it waits for the adopter to confirm before writing anything

#### Scenario: The project's stack is not on the curated list

- **WHEN** onboarding detects no candidate it recognises
- **THEN** it says the list is a convenience, not a supported-stack list
- **AND** the adopter supplies the gate body by hand
- **AND** onboarding completes normally with a valid manifest

#### Scenario: The adopter declines every candidate

- **WHEN** candidates are presented and the adopter chooses none of them
- **THEN** onboarding treats that as a first-class outcome, not an error

### Requirement: Onboarding reports the state of the gate it bound

After writing the manifest, `/gatedloop:gates-init` SHALL run the `ci` gate once and
report its exit code. A failing gate SHALL NOT be treated as an onboarding failure —
binding a gate a project cannot yet pass is legitimate, and is often the reason for
adopting the loop.

#### Scenario: The bound gate is already failing

- **WHEN** onboarding writes a valid manifest whose `ci` gate exits non-zero
- **THEN** onboarding reports success in writing the manifest
- **AND** states plainly that the gate is currently failing
- **AND** states that `tdd-apply` will refuse to commit any task until it passes

#### Scenario: The bound gate passes

- **WHEN** the newly bound `ci` gate exits zero
- **THEN** onboarding reports that the gate is bound and passing

### Requirement: Onboarding asks how a change reaches main

`/gatedloop:gates-init` SHALL ask which integration process the project uses, presenting
preset options so the adopter picks rather than composes: at minimum a local
squash-merge, a pull request without required approvals, and a pull request with
required approvals. Where the process is detectable — a remote exists, branch
protection is visible — the detected answer SHALL be offered as the default option,
never bound automatically. The choice SHALL be recorded in `.gates.yaml`, and
`gates validate` SHALL accept a manifest that declares it.

This requirement covers the ask and the record only. The loop's completion step and
the enforcement hooks consuming the declared process are `harden-unattended-loop`'s
scope.

#### Scenario: The integration process is asked with presets

- **WHEN** onboarding reaches the integration question
- **THEN** it presents the preset options rather than a free-form prompt
- **AND** the adopter's choice is written to `.gates.yaml`

#### Scenario: The process is detectable from the repository

- **WHEN** the repository has a remote whose default branch is protected, or an
  existing PR-based history
- **THEN** the matching preset is offered first, as the default
- **AND** onboarding still waits for the adopter to confirm before recording it

#### Scenario: A manifest declaring an integration process validates

- **WHEN** `gates validate` reads a manifest carrying the recorded integration process
- **THEN** validation passes, and a manifest without the declaration also passes —
  the field is optional, and its absence means the loop's current behaviour

### Requirement: The session brief covers the half-onboarded project

The SessionStart brief SHALL distinguish three states: no OpenSpec, OpenSpec without a
gate manifest, and fully onboarded. In the second state it SHALL offer exactly one next
step — `/gatedloop:gates-init` — and SHALL NOT present loop commands that read a
manifest which does not exist.

#### Scenario: OpenSpec is initialised but no manifest exists

- **WHEN** a session starts in a project with `openspec/` present and no `.gates.yaml`
- **THEN** the brief offers `/gatedloop:gates-init` as the single next step
- **AND** the loop menu is suppressed

#### Scenario: The existing two states are unchanged

- **WHEN** a session starts in a project with no OpenSpec, or in a fully onboarded one
- **THEN** the brief behaves exactly as it did before this change

### Requirement: The bootstrapper covers the OpenSpec prerequisite chain

`/gatedloop:gates-init` SHALL detect whether the OpenSpec CLI is installed and, if
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

`/gatedloop:gates-init` SHALL check for local edits to generated OpenSpec assets
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

`/gatedloop:gates-init` SHALL harvest existing conventions material — contributing
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

The shim SHALL record the OpenSpec CLI range it supports, as a minimum and the highest version it was verified against. The values SHALL match the range `docs/stability.md` declares. A doctor check SHALL compare the installed `openspec --version` against that range. It SHALL warn loudly when the version is below the minimum or above the highest verified. A version outside the range SHALL NOT fail `gates validate` or block onboarding.

#### Scenario: The installed OpenSpec CLI matches the tested version

- **WHEN** the doctor check runs and the installed OpenSpec CLI version is between the recorded minimum and the highest verified version, inclusive
- **THEN** no warning is produced

#### Scenario: The installed OpenSpec CLI version differs

- **WHEN** the doctor check runs and the installed version is above the highest verified version
- **THEN** it warns loudly, naming the installed version and the range
- **AND** it does not fail `gates validate` or stop onboarding on that basis alone

#### Scenario: The installed OpenSpec CLI is older than the minimum

- **WHEN** the doctor check runs and the installed version is below the recorded minimum
- **THEN** it warns loudly, naming the installed version and the range

### Requirement: A doctor preflight diagnoses the reachable states of an invisible install

`/gatedloop:gates-init` SHALL run a `gates doctor` check as its first step, covering
at minimum: OpenSpec CLI presence and version (per the previous requirement),
whether `.gates.yaml`'s `gatesVersion` is current, and whether the plugin's own
commands and hooks are registered for the active session. Where the failure is that
no gatedloop surface is reachable at all, project documentation SHALL carry a
troubleshooting note naming `CLAUDE_CONFIG_DIR` config-profile mismatch as the first
thing to check, runnable independently of any gatedloop command.

#### Scenario: A partial-visibility failure is present

- **WHEN** the plugin's commands are registered but a hook is stale, or the OpenSpec
  CLI is missing, or `gatesVersion` is out of date
- **THEN** `gates doctor` names the specific missing or stale piece

#### Scenario: Nothing is wired at all

- **WHEN** no gatedloop command, skill, or session-brief output appears in a session
- **THEN** no in-session diagnostic can run, and project documentation names
  `CLAUDE_CONFIG_DIR` as the first thing to check from a plain shell

### Requirement: Onboarding stops honestly when a project has no scaffold to bind to

`/gatedloop:gates-init` SHALL distinguish a project whose stack is simply unlisted
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

### Requirement: Onboarding asks who approves plans

The bootstrapper SHALL ask how plans are approved — by a second party's review or by
standing self-approval — alongside the existing integration-mode question, and SHALL
write the answer as the manifest's declared approval policy. Declining to answer
leaves the block absent, which is the `review` default. The question SHALL state the
consequence of each answer in one line.

#### Scenario: A solo developer onboards

- **WHEN** the bootstrapper runs and the adopter answers that they approve their own
  plans
- **THEN** the manifest is written with the `self` policy and the summary names the
  local attestation command as the approval step

#### Scenario: The question is declined

- **WHEN** the adopter skips the approval question
- **THEN** no `approval` block is written and the effective policy is `review`

### Requirement: The session brief routes approved, unimplemented changes to the implementer

When a change's plan approval is valid and its task list has unchecked tasks with no
implementation started, the session brief and the project-brief command SHALL present
spawning the autonomous implementer as the default action for that change, naming the
change. The interactive path SHALL remain listed; neither path is started unprompted.

#### Scenario: An approved change awaits implementation

- **WHEN** a session starts in a project holding a change with valid approval keys
  and an untouched task list
- **THEN** the brief lists that change with "spawn the implementer" as its default
  entry and the interactive loop as the alternative

#### Scenario: Approval is missing or stale

- **WHEN** a change's approval keys are absent, or its artifacts changed after
  attestation
- **THEN** the brief does not offer the implementer for it and instead names the
  approval step that is missing

### Requirement: The doctor preflight reports the optional YAML dependency

`gates doctor` SHALL report whether PyYAML is importable. Its absence SHALL be an
advisory warning, never a failure, because every gate, hook and dispatch decision works
without it. The warning SHALL name what does need it and give an install hint that
works under an externally managed Python.

#### Scenario: PyYAML is present

- **WHEN** `gates doctor` runs where PyYAML is importable
- **THEN** it reports the dependency as ok

#### Scenario: PyYAML is absent

- **WHEN** `gates doctor` runs where PyYAML is not importable
- **THEN** it warns that full schema inspection needs it, states that the loop and its
  dispatch do not, and gives an install hint that does not rely on a plain
  `pip install` into a system Python

#### Scenario: The prerequisite is documented

- **WHEN** an adopter reads the setup prerequisites
- **THEN** PyYAML is listed as optional, with what it enables

### Requirement: Onboarding records the adoption decisions it covered

When `gates-init` finishes, it SHALL record a decision for every adoption catalogue item
it walked, and SHALL leave every item it did not walk undecided. A freshly onboarded
project SHALL therefore not be told to decide something onboarding just asked about.

#### Scenario: A project finishes onboarding

- **WHEN** `gates-init` completes and walked every catalogue item
- **THEN** `gates adoption status` lists nothing, and the next session brief carries no
  adoption line

#### Scenario: The adopter declines a step during onboarding

- **WHEN** the adopter declines the test-conventions capture during `gates-init`
- **THEN** the item is recorded `declined`, and it is never raised as undecided
  afterwards

### Requirement: The session brief adds a fallback PATH entry for the shim

When the SessionStart hook runs with `CLAUDE_ENV_FILE` and `CLAUDE_PLUGIN_ROOT` set and
the plugin's `bin/gates` is executable, it SHALL append one line to `CLAUDE_ENV_FILE`
that adds the plugin's `bin/` to the end of PATH, unless that exact line is already
present. It SHALL NOT truncate the file, and SHALL write nothing when either variable
is absent.

#### Scenario: A fresh session

- **WHEN** the brief runs with both variables set and an empty env file
- **THEN** the file holds exactly one line appending `<plugin root>/bin` to PATH

#### Scenario: A second SessionStart in the same session

- **WHEN** the brief runs again with the same env file
- **THEN** the line is not duplicated, and other lines in the file are kept

#### Scenario: No env file offered

- **WHEN** `CLAUDE_ENV_FILE` is not set
- **THEN** the brief writes no file and prints as before

### Requirement: The doctor reports whether `gates` resolves and where the shim runs from

`gates doctor` SHALL report whether `gates` resolves on PATH, warning when it does
not and naming a remedy computed from the running shim's own location. It SHALL
report where the running shim lives (an installed plugin copy with its version, a
checkout, or another path) without warning, and SHALL NOT warn merely because
`CLAUDE_PLUGIN_ROOT` is unset.

#### Scenario: `gates` is not on PATH

- **WHEN** `gates doctor` runs in a shell where `gates` does not resolve
- **THEN** the `gates-on-path` row warns and names an export line built from the
  shim's own `bin/` directory

#### Scenario: Run from the Bash tool of a working session

- **WHEN** `gates` resolves and `CLAUDE_PLUGIN_ROOT` is unset
- **THEN** no doctor row warns about plugin registration, and the shim-location row
  names where the shim runs from
