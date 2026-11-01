## ADDED Requirements

### Requirement: An unparseable manifest fails loud in one line

When `.gates.yaml` cannot be parsed, every subcommand SHALL exit 1 with one message naming the file and the line and column of the error, on both the PyYAML and the `_mini_yaml` path, and SHALL print no traceback. When the file holds a line starting with `<<<<<<<`, `=======` or `>>>>>>>`, the message SHALL say it holds merge-conflict markers.

#### Scenario: A manifest with conflict markers

- **WHEN** `.gates.yaml` holds an unresolved merge conflict and any `gates` subcommand runs
- **THEN** it exits 1 with one `gatedloop:` line naming `.gates.yaml`, the position, and the conflict markers, and no traceback

#### Scenario: Both parse paths agree

- **WHEN** the same unparseable manifest is read with PyYAML importable and without it
- **THEN** both runs exit 1 with a message of the same shape
