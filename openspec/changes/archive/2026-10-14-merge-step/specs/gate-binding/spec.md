## ADDED Requirements

### Requirement: An optional `confirm` gate proves the merged tree live

The gate contract SHALL include an optional `confirm` gate. The project binds it to a
command that brings the merged tree up and checks it on the project's own
environment. The plugin SHALL NOT read the command's body. An undeclared `confirm`
SHALL be skipped with a printed note, never treated as a failure. A declared `confirm`
SHALL block publication when it fails.

#### Scenario: Confirm is undeclared

- **WHEN** `gates merge` reaches step 5 in a project that declares no `confirm` gate
- **THEN** it prints that live confirmation was skipped because no `confirm` gate is
  declared, and continues

#### Scenario: Confirm has a precondition failure

- **WHEN** the `confirm` gate exits 75 because its declared environment is absent
- **THEN** the merge halts before publishing and reports the precondition message, as
  for any gate precondition
