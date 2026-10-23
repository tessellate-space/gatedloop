# Spec Delta

## MODIFIED Requirements

### Requirement: The plan-approval policy is declared in the manifest

The manifest SHALL accept an optional `approval` block declaring the plan-approval
policy: `plan: review` (a second party approves via the forge) or `plan: self`
(standing self-approval). When the block is absent, the policy SHALL be `review`.
The same block SHALL accept an optional `acceptance` key declaring the acceptance
policy for the increment after the loop: `acceptance: review` (a second party accepts
via the forge) or `acceptance: self` (standing self-acceptance). When `acceptance` is
absent, no acceptance SHALL be required anywhere and behaviour SHALL match today's.
`gates validate` SHALL reject any other value for either key with a message naming
the accepted ones, and SHALL reject `acceptance: review` when the declared integration
mode produces no pull request to review, naming the conflict.

#### Scenario: No block declared

- **WHEN** a manifest has no `approval` block
- **THEN** the effective plan policy is `review`, no acceptance is required, and
  behavior matches today's

#### Scenario: An invalid policy value

- **WHEN** a manifest declares an `approval.plan` value other than `review` or `self`
- **THEN** `gates validate` exits non-zero naming the value and the accepted ones

#### Scenario: Acceptance declared alongside plan approval

- **WHEN** a manifest declares `approval: { plan: self, acceptance: self }`
- **THEN** `gates validate` accepts it and acceptance becomes required for the merge

#### Scenario: An invalid acceptance value

- **WHEN** a manifest declares `approval.acceptance` as anything other than `review`
  or `self`
- **THEN** `gates validate` exits non-zero naming the value and the accepted ones

#### Scenario: Review acceptance without a pull request

- **WHEN** a manifest declares `approval.acceptance: review` and its integration mode
  is `local-squash-merge` (or the `integration` block is absent)
- **THEN** `gates validate` exits non-zero stating that a review-based acceptance needs
  a pull request to review, and names `self` or `integration.mode: pull-request` as
  the ways to resolve it

### Requirement: Local attestation is legitimate only under the self policy

A local attestation command SHALL write the approval keys machine-side: it computes
the content hash over the change's artifacts itself, records the configured git
identity and the current time, and never accepts a caller-supplied hash or identity
override for the hash. Under the `review` policy it SHALL refuse and name the
PR-based attestation path. The same rule SHALL govern acceptance: `gates acceptance
attest <change> --local` is legitimate only under `acceptance: self`, computes the
tree it pins itself, records the configured git identity as `accepted_by`, and
refuses under `acceptance: review` naming the `--pr` path; when no acceptance policy
is declared, both acceptance writers SHALL refuse and name the manifest key to
declare.

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

#### Scenario: Solo acceptance under self policy

- **WHEN** `approval.acceptance` is `self` and `gates acceptance attest <change>
  --local` runs on the change branch
- **THEN** an `accept` row is appended with the normalized head tree and the
  configured git identity as `accepted_by`

#### Scenario: Local acceptance under review policy

- **WHEN** `approval.acceptance` is `review` and `--local` acceptance is attempted
- **THEN** it refuses, exits non-zero, and names `gates acceptance attest <change>
  --pr <n>`

#### Scenario: Acceptance attested with no policy declared

- **WHEN** the manifest has no `approval.acceptance` and either acceptance writer runs
- **THEN** it refuses, exits non-zero, writes nothing, and names `approval.acceptance`
  as the key to declare

## ADDED Requirements

### Requirement: Forge-attested acceptance is read from the pull request's approving review

`gates acceptance attest <change> --pr <n>` SHALL derive `accepted_by` and the
acceptance timestamp from the pull request's actual review in the `APPROVED` state,
SHALL compute the pinned tree itself from the change branch's head, and SHALL NOT
accept a caller-supplied identity, timestamp or tree. When the forge CLI is missing,
unauthenticated or offline, or the pull request has no `APPROVED` review, it SHALL
fail closed: exit non-zero, write nothing, and say why. Under `acceptance: self` the
`--pr` writer SHALL remain legitimate — a real review is always acceptable evidence.

#### Scenario: The implementation PR carries an approving review

- **WHEN** the change's pull request has an `APPROVED` review and `--pr <n>` runs on
  the change branch
- **THEN** an `accept` row is appended with `accepted_by` set to that review's author
  and the normalized head tree

#### Scenario: No approving review

- **WHEN** the pull request has no review in the `APPROVED` state
- **THEN** the writer exits non-zero, appends nothing, and states that merged or
  commented is not accepted

#### Scenario: The forge is unreachable

- **WHEN** the forge CLI is missing, unauthenticated or offline
- **THEN** the writer exits non-zero, appends nothing, and never falls back to a local
  identity

#### Scenario: A supplied identity is rejected

- **WHEN** `--pr <n>` is combined with an identity override
- **THEN** the writer refuses, explaining that a forge attestation's identity comes
  from the review
