## ADDED Requirements

### Requirement: The adopter-facing docs are checked against what ships before a release is cut

`scripts/release docs` SHALL build an inventory of every shipped command, agent,
skill, `gates` subcommand, gate name and top-level manifest key, taken from the
plugin's own files. It SHALL report every inventory item that README.md and SETUP.md
do not mention, and every such name they mention that no longer exists, each with its
file and line. It SHALL exit non-zero when it finds any gap. `cut` SHALL run it before
any other check, and SHALL refuse while it fails.

#### Scenario: A new command is undocumented

- **WHEN** `commands/merge.md` exists and neither README.md nor SETUP.md mentions
  `/specloop:merge`
- **THEN** `scripts/release docs` reports it as undocumented and exits non-zero, and
  `cut` refuses before writing anything

#### Scenario: The docs name a removed subcommand

- **WHEN** SETUP.md mentions a `gates` subcommand the shim no longer has
- **THEN** `scripts/release docs` reports the stale mention with its file and line

#### Scenario: The docs are complete

- **WHEN** every inventory item is mentioned and no stale name is found
- **THEN** `scripts/release docs` exits 0, and `cut` proceeds

### Requirement: The release procedure includes a reviewed docs pass

The documented release procedure SHALL place a docs pass between `status` and `cut`.
The pass reconciles README.md, SETUP.md, AUTOMATION.md, the field guide and this
repository's `CLAUDE.md` with the changes archived since the last tag. It lands as a
reviewed pull request. The session-start release reminder SHALL name the docs pass as
the next step.

#### Scenario: A release is due

- **WHEN** a session starts in this repository with a release due
- **THEN** the reminder names the docs pass before `cut`

### Requirement: Changes to an adopter-facing surface update the docs in the same change

This repository's conventions SHALL require that a change adding, removing or altering
an adopter-facing surface update README.md and SETUP.md in the same change, and
AUTOMATION.md when it changes enforcement. The rule SHALL reach task authoring and
convention review.

#### Scenario: A plan adds a command

- **WHEN** a change's tasks add a command
- **THEN** OpenSpec's tasks instructions carry the rule, and convention review flags
  a task diff that adds the command without a docs update
