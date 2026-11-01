# public-contract Specification

## Purpose
TBD - created by archiving change stability-contract. Update Purpose after archive.

## Requirements

### Requirement: The public surface is recorded in one checked-in snapshot

The repository SHALL hold `tests/contract.json`, a snapshot of the public surface:
- `gates` subcommands and flags;
- exit codes;
- status contexts;
- manifest keys;
- the `handoff` and `stats` document keys;
- ledger fields.

Each subcommand SHALL be marked `public` or `internal`. It is `internal` only when it is listed, with a reason, as invoked solely by bundled hooks or prompts.

#### Scenario: The snapshot names an internal subcommand

- **WHEN** `tests/contract.json` is generated
- **THEN** `discipline` is recorded as `internal`, with its reason, and `run` as `public`

#### Scenario: The snapshot names every listed surface

- **WHEN** `tests/contract.json` is generated
- **THEN** it holds the reserved exit codes, every `gatedloop/<gate>` context, the top-level keys of `schema/gates.schema.json`, the top-level keys of `gates handoff --json` and `gates stats --json`, the ledger row fields and the row version

### Requirement: ci fails when the code and the snapshot disagree

A test module SHALL regenerate the snapshot from the code and compare it with `tests/contract.json`. On any difference, it SHALL fail, printing the difference and the command that rewrites the snapshot. An addition fails as well as a removal, so no surface enters the contract unreviewed.

#### Scenario: A flag is renamed

- **WHEN** a change renames a `gates` flag and does not update `tests/contract.json`
- **THEN** `gates run ci` fails, naming the removed flag and the added one

#### Scenario: The snapshot is updated deliberately

- **WHEN** the same change also rewrites the snapshot with the printed command
- **THEN** the test passes, and the PR's diff shows the rename in `tests/contract.json`

#### Scenario: A subcommand is added unreviewed

- **WHEN** a change adds a `gates` subcommand without updating the snapshot
- **THEN** the test fails, naming the new subcommand

### Requirement: Every ledger row carries a row version

Every row the shim appends SHALL carry `v`, an integer starting at `1`. The shim sets it itself, so no caller can omit or forge it. A row without `v` SHALL be read as version 1, the version every row written before the field had.

#### Scenario: New rows are versioned

- **WHEN** any gate run appends a row
- **THEN** the row carries `"v": 1`

#### Scenario: A ledger written before versioning

- **WHEN** `gates stats` reads a ledger whose rows have no `v`
- **THEN** it reports them exactly as before this change

### Requirement: A reader refuses a ledger row newer than it knows

Every ledger reader SHALL go through one shared check. A row whose `v` is greater than the highest version the shim reads SHALL make the command exit non-zero, naming the ledger file and both versions, and saying to update the plugin. Such a row SHALL NOT be skipped silently, and SHALL NOT be read as an older one.

#### Scenario: A ledger written by a newer plugin

- **WHEN** a teammate on a newer plugin commits a ledger row with `v: 2`, and `gates merge` runs on a plugin that reads version 1
- **THEN** the merge exits non-zero, naming the file and both versions, and no merge row is written

#### Scenario: A committed row read from a tree

- **WHEN** a `v: 2` row is read out of a commit's ledger blobs rather than the working tree
- **THEN** the same refusal applies

### Requirement: The supported environment is declared in one place and stated the same everywhere

The repository SHALL declare a minimum Python version, a supported OpenSpec range (a minimum and the highest version tested), and the supported operating systems. `README.md`, `SETUP.md` and `docs/stability.md` SHALL state the same values, and a test SHALL check that the shim's range constants match `docs/stability.md`.

#### Scenario: The page and the code drift

- **WHEN** a change raises the shim's highest tested OpenSpec version without editing `docs/stability.md`
- **THEN** `gates run ci` fails, naming both values

### Requirement: ci runs on the declared environment, and a scheduled run watches OpenSpec's latest

The pull-request ci SHALL run `gates run ci` on each supported OS, with the minimum and the latest Python, and with the OpenSpec minimum and highest tested version. A scheduled job SHALL run the same `ci` against OpenSpec's latest release. It SHALL NOT be a required status.

#### Scenario: A construct the minimum Python lacks

- **WHEN** a change uses syntax the declared minimum Python cannot parse
- **THEN** the minimum-Python leg of the pull-request ci fails

#### Scenario: OpenSpec ships a breaking release

- **WHEN** a new OpenSpec release changes a JSON shape the shim reads
- **THEN** the scheduled job fails within a week, while pull-request ci on the declared range stays green

### Requirement: The contract and its deprecation policy are written down

`docs/stability.md` SHALL state what the contract covers and what it does not. It SHALL also state the deprecation policy:
1. a surface is deprecated with a warning on use;
2. it is kept for at least one further release;
3. it is removed under a `### Breaking` changelog entry with a migration step.

The page SHALL NOT state when the project reaches 1.0.

#### Scenario: A removal while the version is 0.x

- **WHEN** a maintainer reads the policy before removing a deprecated flag on a 0.x version
- **THEN** it says that the removal may ship in a minor release, and that from 1.0 it may ship only in a major

#### Scenario: What is outside the contract

- **WHEN** an adopter checks whether a prompt's wording or a human-readable line is covered
- **THEN** the page says that neither is covered, and neither is an `internal` subcommand
