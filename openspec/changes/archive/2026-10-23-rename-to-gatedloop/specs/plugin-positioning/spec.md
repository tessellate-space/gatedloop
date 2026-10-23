## ADDED Requirements

### Requirement: The plugin is named gatedloop

The plugin, its marketplace, its command namespace, its state directory, its change
metadata keys, its commit-status contexts, its record branches, its built-in rule ids
and its hook markers SHALL use the name `gatedloop`. The `gates` shim, `.gates.yaml`
and the gate names SHALL keep their names.

#### Scenario: A fresh install

- **WHEN** a project installs the plugin and runs onboarding
- **THEN** its commands are `/gatedloop:*`, its state is under `.gatedloop/`, and the
  statuses it publishes are `gatedloop/<gate>`

### Requirement: The earlier name is read loudly for one release

Through 0.7.x the shim SHALL read every earlier `specloop` identifier when the new one
is absent, preferring the new, and SHALL warn once per command that the earlier name
stops working in 0.8.0 and names `gates migrate-name`. Publishing a gate status SHALL
post both contexts. A project holding both state directories SHALL be refused, naming
the command.

#### Scenario: A project not yet migrated

- **WHEN** a project has only `.specloop/` and `x-specloop-*` keys
- **THEN** every command works, reading the earlier names, and prints the one-line
  migration warning

#### Scenario: Both state directories

- **WHEN** a project has both `.specloop/` and `.gatedloop/`
- **THEN** the shim refuses, naming `gates migrate-name`

### Requirement: A project migrates to the new name by one command

`gates migrate-name` SHALL move the state directory, rewrite earlier metadata keys in
active changes and earlier markers in a composed hook, and print each settings and
branch-protection edit it does not make. It SHALL never commit or push, SHALL leave
archived changes untouched, and SHALL exit 0 when nothing remains to migrate.

#### Scenario: Migrating a project

- **WHEN** `gates migrate-name` runs in a project with `.specloop/` and one active
  change carrying `x-specloop-approved-by`
- **THEN** the directory is `.gatedloop/`, the key reads `x-gatedloop-approved-by`
  with the same value, and the printed list names the branch-protection context to
  rename

#### Scenario: Nothing to migrate

- **WHEN** a project already uses only the new names
- **THEN** `gates migrate-name` changes nothing and exits 0
