# onboarding Delta Specification

## ADDED Requirements

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
