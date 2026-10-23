## ADDED Requirements

### Requirement: The doctor preflight reports the optional YAML dependency

`gates doctor` SHALL report whether PyYAML is importable. Its absence SHALL be an
advisory warning, never a failure, because every gate, hook and dispatch decision works
without it. The warning SHALL name what does need it and give an install hint that
works under an externally managed Python.

#### Scenario: PyYAML is present

- **WHEN** `gates doctor` runs where PyYAML is importable
- **THEN** it reports the dependency as ok

#### Scenario: PyYAML is absent

- **WHEN** `gates doctor` runs where PyYAML is not importable
- **THEN** it warns that full schema inspection needs it, states that the loop and its
  dispatch do not, and gives an install hint that does not rely on a plain
  `pip install` into a system Python

#### Scenario: The prerequisite is documented

- **WHEN** an adopter reads the setup prerequisites
- **THEN** PyYAML is listed as optional, with what it enables
