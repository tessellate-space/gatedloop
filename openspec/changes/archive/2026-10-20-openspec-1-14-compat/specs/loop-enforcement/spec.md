## ADDED Requirements

### Requirement: Specloop's change metadata uses OpenSpec's tool-metadata prefix

The approval keys SHALL be written to `.openspec.yaml` as `x-specloop-approved-by`,
`x-specloop-approved-at` and `x-specloop-approved-sha`, which OpenSpec reserves for
tool metadata. Every reader SHALL accept the earlier spellings `approved_by`,
`approved_at` and `approved_sha`, preferring the new ones. Other requirements naming
the earlier spellings refer to these keys.

#### Scenario: Attesting writes the new keys

- **WHEN** `gates approval attest <change> --local` runs on a change whose
  `.openspec.yaml` carries `approved_by`
- **THEN** the file carries the three `x-specloop-approved-*` keys and none of the
  earlier ones, and `openspec validate <change> --strict` reports no unrecognized key

#### Scenario: An approval written by 0.5.0

- **WHEN** a change merged to the target carries only `approved_by`, `approved_at`
  and `approved_sha`
- **THEN** `check-implement` accepts its approval exactly as before

### Requirement: Old-spelled approval keys can be migrated and are diagnosed

`gates approval migrate [<change>]` SHALL rename the earlier approval keys to the new
spelling in each active change's `.openspec.yaml`, keeping values, without changing
the approval sha. `gates doctor` SHALL warn when an active change carries an earlier
spelling, naming the change and the command.

#### Scenario: Migrating an active change

- **WHEN** `gates approval migrate` runs and one active change carries `approved_by`
- **THEN** that file is rewritten to the new keys with the same values, and
  `gates approval check` still passes for it

#### Scenario: Doctor on an unmigrated change

- **WHEN** an active change carries `approved_sha`
- **THEN** `gates doctor` warns, naming the change and `gates approval migrate`

### Requirement: The shim runs OpenSpec non-interactively

Every `openspec` process the shim starts SHALL have `OPEN_SPEC_INTERACTIVE=0` in its
environment.

#### Scenario: A hook validates a change

- **WHEN** a planning-grade commit check runs `openspec validate`
- **THEN** the process environment carries `OPEN_SPEC_INTERACTIVE=0`
