## MODIFIED Requirements

### Requirement: The OpenSpec contract version is probed, not assumed

The shim SHALL record the OpenSpec CLI range it supports, as a minimum and the highest version it was verified against. The values SHALL match the range `docs/stability.md` declares. A doctor check SHALL compare the installed `openspec --version` against that range. It SHALL warn loudly when the version is below the minimum or above the highest verified. A version outside the range SHALL NOT fail `gates validate` or block onboarding.

#### Scenario: The installed OpenSpec CLI matches the tested version

- **WHEN** the doctor check runs and the installed OpenSpec CLI version is between the recorded minimum and the highest verified version, inclusive
- **THEN** no warning is produced

#### Scenario: The installed OpenSpec CLI version differs

- **WHEN** the doctor check runs and the installed version is above the highest verified version
- **THEN** it warns loudly, naming the installed version and the range
- **AND** it does not fail `gates validate` or stop onboarding on that basis alone

#### Scenario: The installed OpenSpec CLI is older than the minimum

- **WHEN** the doctor check runs and the installed version is below the recorded minimum
- **THEN** it warns loudly, naming the installed version and the range
