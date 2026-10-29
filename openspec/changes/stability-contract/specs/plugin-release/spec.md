## ADDED Requirements

### Requirement: Contract removals since the tag are reported as breaking

`scripts/release status` SHALL compare `tests/contract.json` at the latest `v*` tag with the one at `HEAD`. It SHALL list each removed `public` entry, and a raised ledger row version, under `breaking`, in text and in `--json`. Additions, `internal` entries and a tag that has no snapshot SHALL NOT count as breaking. The suggested level SHALL NOT change, so `status` still never suggests `major`.

#### Scenario: A flag was removed since the tag

- **WHEN** a public flag in the snapshot at the latest tag is absent at `HEAD`
- **THEN** `status` reports it under breaking

#### Scenario: Only additions

- **WHEN** the snapshot at `HEAD` only adds entries to the one at the tag
- **THEN** `status` reports nothing as breaking

#### Scenario: The tag predates the snapshot

- **WHEN** the latest tag has no `tests/contract.json`
- **THEN** `status` reports nothing as breaking, and says the comparison was skipped

### Requirement: A breaking release carries a migration step for each entry

`cut` SHALL draft a `### Breaking` subsection listing each entry `status` reports, each with `TODO` in place of its migration step. `publish` SHALL refuse while any `TODO` remains in that subsection.

#### Scenario: Cut drafts the entries

- **WHEN** `cut` runs with one public flag removed since the tag
- **THEN** the drafted section has a `### Breaking` entry naming the flag, with a `TODO` migration

#### Scenario: A breaking entry without its migration step

- **WHEN** `publish` runs and the version's `### Breaking` subsection still holds a `TODO`
- **THEN** it exits non-zero before its first write, naming the entry
