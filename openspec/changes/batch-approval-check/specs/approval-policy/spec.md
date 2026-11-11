## ADDED Requirements

### Requirement: Many changes are checked in one call

`gates approval check --json [<change> ...]` SHALL give each named change the verdict and
reason that `gates approval check <change>` gives it, printed as one JSON document with the
policy, the target, a `fingerprint` and one result per change. With no names it SHALL check
every change under `openspec/changes/`, excluding `archive/`, on the resolved ref. It SHALL
exit 0 when every result passes and 1 otherwise.

#### Scenario: The same verdicts as the single form

- **WHEN** three changes are on the target, one approved, one never attested and one
  edited after approval
- **THEN** `gates approval check --json a b c` reports each with the `ok` and `reason`
  that `gates approval check` gives it alone, and exits 1

#### Scenario: Every change, with no names

- **WHEN** `gates approval check --json` runs with no names
- **THEN** it reports every change under `openspec/changes/` except `archive/`, in name
  order

#### Scenario: A plan file with CRLF line endings

- **WHEN** an approved change's plan includes a file with CRLF line endings
- **THEN** the batch reports it approved, as the single form does

#### Scenario: The single form is unchanged

- **WHEN** `gates approval check <change>` runs without `--json`
- **THEN** its output and exit code are as before, and two names without `--json` exit 2

### Requirement: The batched check costs the same for many changes and names its inputs

The batched check's number of git invocations SHALL NOT grow with the number of changes.
Its `fingerprint` SHALL change whenever the policy, the target's commit, or a consulted
local counterpart's commit changes, and SHALL NOT change otherwise.

#### Scenario: Git calls do not scale with the changes

- **WHEN** the batch checks 2 changes and then 20 changes on the same target
- **THEN** both runs make the same number of git invocations

#### Scenario: The fingerprint follows the inputs

- **WHEN** the batch runs twice with no ref moved, and again after the target's commit
  moves
- **THEN** the first two fingerprints are equal, and the third differs
