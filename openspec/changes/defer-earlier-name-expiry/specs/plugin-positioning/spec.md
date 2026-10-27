# Spec Delta

## MODIFIED Requirements

### Requirement: The earlier name is read loudly for one release

Through 0.8.x the shim SHALL read every earlier `specloop` identifier when the new one
is absent, preferring the new, and SHALL warn once per command that the earlier name
stops working in 0.9.0 and names `gates migrate-name`. Publishing a gate status SHALL
post both contexts. A project holding both state directories SHALL be refused, naming
the command.

#### Scenario: A project not yet migrated

- **WHEN** a project has only `.specloop/` and `x-specloop-*` keys
- **THEN** every command works, reading the earlier names, and prints the one-line
  migration warning naming 0.9.0

#### Scenario: Both state directories

- **WHEN** a project has both `.specloop/` and `.gatedloop/`
- **THEN** the shim refuses, naming `gates migrate-name`
