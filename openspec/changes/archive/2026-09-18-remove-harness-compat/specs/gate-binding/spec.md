## REMOVED Requirements

### Requirement: The old name keeps working for one release and says so
**Reason**: The one-release compatibility window from `rename-to-gates` has
elapsed. Keeping the forwarder and the legacy-filename/legacy-key fallback
indefinitely would mean the "harness"/"gates" collision never actually goes
away — a reader would still find `.harness.yaml` working in real projects,
which is the entire cost `rename-to-gates` paid to remove (see its design D3).
**Migration**: Any project still invoking `harness` or shipping a
`.harness.yaml` / `harnessVersion` manifest must switch to `gates` /
`.gates.yaml` / `gatesVersion` before this change lands — `rename-to-gates`'s
deprecation notices named the replacement for exactly this purpose.

#### Scenario: An adopter invokes the old shim name
- **WHEN** the previous `harness` entry point is invoked with any arguments
- **THEN** it forwards to the new shim with the same arguments and the same exit code, and prints a deprecation notice to stderr naming `gates`

#### Scenario: A project still has the old manifest filename
- **WHEN** the shim runs in a project that has `.harness.yaml` and no `.gates.yaml`
- **THEN** it reads the old file, succeeds, and warns loudly that the file should be renamed to `.gates.yaml`

#### Scenario: The deprecation is never silent
- **WHEN** either compatibility path is exercised
- **THEN** a message is emitted; neither path succeeds quietly, so migration cannot be indefinitely postponed by accident

#### Scenario: Both manifests are present
- **WHEN** a project contains both `.gates.yaml` and `.harness.yaml`
- **THEN** the new file wins and the shim reports that the old one is being ignored and can be deleted

### Requirement: The manifest version key discriminates the format
**Reason**: Once the legacy filename fallback is gone, discriminating a
manifest's vintage by which version key it carries has no remaining purpose —
there is only one recognized filename and one recognized key.
**Migration**: Rename `harnessVersion` to `gatesVersion` in any manifest that
still carries the old key; this was already required by `rename-to-gates`'s
own deprecation warning.

#### Scenario: A current manifest is loaded
- **WHEN** a manifest carrying `gatesVersion: 1` is read
- **THEN** it loads without any deprecation warning

#### Scenario: A legacy manifest is loaded
- **WHEN** a manifest carrying `harnessVersion: 1` is read
- **THEN** it loads, and the shim warns that the key should be renamed to `gatesVersion`
