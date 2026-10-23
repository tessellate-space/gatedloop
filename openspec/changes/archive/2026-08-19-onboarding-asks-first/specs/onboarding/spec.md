# Onboarding

## ADDED Requirements

### Requirement: The bootstrapper offers candidates and binds only what is chosen

`/specloop:gates-init` SHALL detect build-system candidates from a curated list,
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

After writing the manifest, `/specloop:gates-init` SHALL run the `ci` gate once and
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

`/specloop:gates-init` SHALL ask which integration process the project uses, presenting
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
step — `/specloop:gates-init` — and SHALL NOT present loop commands that read a
manifest which does not exist.

#### Scenario: OpenSpec is initialised but no manifest exists

- **WHEN** a session starts in a project with `openspec/` present and no `.gates.yaml`
- **THEN** the brief offers `/specloop:gates-init` as the single next step
- **AND** the loop menu is suppressed

#### Scenario: The existing two states are unchanged

- **WHEN** a session starts in a project with no OpenSpec, or in a fully onboarded one
- **THEN** the brief behaves exactly as it did before this change
