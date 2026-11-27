## MODIFIED Requirements

### Requirement: ci runs on the declared environment, and a scheduled run watches OpenSpec's latest

The pull-request ci SHALL run `gates run ci` on each supported OS, with the minimum and the latest Python, and with the OpenSpec minimum and highest tested version. The OpenSpec minimum SHALL run on every OS and Python leg; the highest tested version, when it differs from the minimum, SHALL run on at least one leg. Only one leg, on the OpenSpec minimum, SHALL publish the `gatedloop/ci` and `gatedloop/tests` statuses. A scheduled job SHALL run the same `ci` against OpenSpec's latest release. It SHALL NOT be a required status.

#### Scenario: A construct the minimum Python lacks

- **WHEN** a change uses syntax the declared minimum Python cannot parse
- **THEN** the minimum-Python leg of the pull-request ci fails

#### Scenario: OpenSpec ships a breaking release

- **WHEN** a new OpenSpec release changes a JSON shape the shim reads
- **THEN** the scheduled job fails within a week, while pull-request ci on the declared range stays green

#### Scenario: The highest tested OpenSpec breaks the suite

- **WHEN** a change passes on the OpenSpec minimum but fails `gates run ci` on the highest tested version
- **THEN** the highest-tested leg fails the workflow run, and it publishes no `gatedloop/ci` or `gatedloop/tests` status
