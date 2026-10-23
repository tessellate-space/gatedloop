# approval-policy Delta Specification

## Purpose

Plan approval is a declared policy: the manifest states who approves plans, that
declaration selects which attestation writers are legitimate, and every writer keeps
the approval content-pinned to the artifacts it approved.

## ADDED Requirements

### Requirement: The plan-approval policy is declared in the manifest

The manifest SHALL accept an optional `approval` block declaring the plan-approval
policy: `plan: review` (a second party approves via the forge) or `plan: self`
(standing self-approval). When the block is absent, the policy SHALL be `review`.
`gates validate` SHALL reject any other value with a message naming the accepted ones.

#### Scenario: No block declared

- **WHEN** a manifest has no `approval` block
- **THEN** the effective policy is `review` and behavior matches today's

#### Scenario: An invalid policy value

- **WHEN** a manifest declares an `approval.plan` value other than `review` or `self`
- **THEN** `gates validate` exits non-zero naming the value and the accepted ones

### Requirement: Local attestation is legitimate only under the self policy

A local attestation command SHALL write the approval keys machine-side: it computes
the content hash over the change's artifacts itself, records the configured git
identity and the current time, and never accepts a caller-supplied hash or identity
override for the hash. Under the `review` policy it SHALL refuse and name the
PR-based attestation path.

#### Scenario: Solo attestation under self policy

- **WHEN** the declared policy is `self` and local attestation runs for a change
- **THEN** the approval keys are written with the computed content hash and the
  configured git identity, and the implementation gate accepts them

#### Scenario: Local attestation under review policy

- **WHEN** the declared policy is `review` (or the block is absent) and local
  attestation is attempted
- **THEN** it refuses, exits non-zero, and names the PR-based attestation command

#### Scenario: Post-approval edits still invalidate

- **WHEN** a change was locally attested and any of its plan artifacts is edited
  afterwards
- **THEN** the recorded content hash no longer matches and the implementation gate
  refuses, exactly as with forge-attested approval

## RENAMED Requirements

<!-- None. -->
