## ADDED Requirements

### Requirement: A non-test rewrite path is advisory in plan checks

`gates plan check` and `gates plan round` SHALL report a `rewrites:` path that does not
look like a test path as an advisory of kind `rewrite-not-test-path`. An advisory SHALL be
printed, SHALL NOT set the exit status, and SHALL NOT stop a round from opening. Every
other oracle warning SHALL remain a finding.

#### Scenario: Rewriting a feature file

- **WHEN** task 1.1 is tagged `[oracle: unit rewrites: e2e/features/login.feature]` and
  the file exists
- **THEN** `gates plan check` prints an advisory for task 1.1, says the plan is clean and
  exits 0, and its JSON lists the path under `advisories` with no finding

#### Scenario: A round opens past an advisory

- **WHEN** the plan's only static problem is a non-test rewrite path
- **THEN** `gates plan round` prints the advisory and opens the round

#### Scenario: A clean plan

- **WHEN** the plan has no static problem
- **THEN** `gates plan check --json` carries `advisories: []` and `findings: []`

#### Scenario: An absent rewrite path still blocks

- **WHEN** task 1.1 declares `rewrites:` for a path absent from the working tree
- **THEN** `gates plan check` reports an `oracle-warning` finding and exits 1
