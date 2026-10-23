## ADDED Requirements

### Requirement: The session brief adds a fallback PATH entry for the shim

When the SessionStart hook runs with `CLAUDE_ENV_FILE` and `CLAUDE_PLUGIN_ROOT` set and
the plugin's `bin/gates` is executable, it SHALL append one line to `CLAUDE_ENV_FILE`
that adds the plugin's `bin/` to the end of PATH, unless that exact line is already
present. It SHALL NOT truncate the file, and SHALL write nothing when either variable
is absent.

#### Scenario: A fresh session

- **WHEN** the brief runs with both variables set and an empty env file
- **THEN** the file holds exactly one line appending `<plugin root>/bin` to PATH

#### Scenario: A second SessionStart in the same session

- **WHEN** the brief runs again with the same env file
- **THEN** the line is not duplicated, and other lines in the file are kept

#### Scenario: No env file offered

- **WHEN** `CLAUDE_ENV_FILE` is not set
- **THEN** the brief writes no file and prints as before

### Requirement: The doctor reports whether `gates` resolves and where the shim runs from

`gates doctor` SHALL report whether `gates` resolves on PATH, warning when it does
not and naming a remedy computed from the running shim's own location. It SHALL
report where the running shim lives (an installed plugin copy with its version, a
checkout, or another path) without warning, and SHALL NOT warn merely because
`CLAUDE_PLUGIN_ROOT` is unset.

#### Scenario: `gates` is not on PATH

- **WHEN** `gates doctor` runs in a shell where `gates` does not resolve
- **THEN** the `gates-on-path` row warns and names an export line built from the
  shim's own `bin/` directory

#### Scenario: Run from the Bash tool of a working session

- **WHEN** `gates` resolves and `CLAUDE_PLUGIN_ROOT` is unset
- **THEN** no doctor row warns about plugin registration, and the shim-location row
  names where the shim runs from
