# plugin-release Specification

## Purpose
How this repository versions and publishes the plugin. Every change that reaches
adopters is released under a version bump, recorded in a changelog, tagged, and
published. The maintainer is reminded when shipped work is sitting on `main`
unreleased.

## Requirements

### Requirement: The plugin version has one value across every manifest field

The plugin's version SHALL be the same string in `.claude-plugin/plugin.json`
(`version`), and in `.claude-plugin/marketplace.json` in both `metadata.version` and
the `gatedloop` plugin entry's `version`. The value SHALL be a semantic version,
`MAJOR.MINOR.PATCH`. `scripts/release check` SHALL exit non-zero when the fields
disagree, naming each field and its value. It SHALL also exit non-zero when the value
is lower than the latest `v*` tag reachable from `HEAD`. This repository's `ci` gate
SHALL run this check.

#### Scenario: Fields agree

- **WHEN** all three fields read `0.4.0` and the latest tag is `v0.4.0`
- **THEN** `scripts/release check` exits zero

#### Scenario: One field was missed

- **WHEN** `plugin.json` reads `0.5.0` and either marketplace field reads `0.4.0`
- **THEN** `scripts/release check` exits non-zero, listing the three fields with their
  values

#### Scenario: Version behind the latest tag

- **WHEN** the fields agree on `0.3.0` and the latest reachable tag is `v0.4.0`
- **THEN** `scripts/release check` exits non-zero, naming both versions

#### Scenario: No tags yet

- **WHEN** the repository has no `v*` tag
- **THEN** only the agreement and format checks apply

### Requirement: Unreleased work is reported, with a suggested bump level

`scripts/release status` SHALL compare `HEAD` with the latest `v*` tag. It SHALL report
the commits since that tag that touch a shipped path. It SHALL also report the
OpenSpec changes archived since that tag, meaning archive directories added under
`openspec/changes/archive/`.

Shipped paths SHALL be a single documented list: `.claude-plugin/`, `commands/`,
`skills/`, `agents/`, `hooks/`, `bin/`, `templates/`, `schema/`, `README.md`,
`SETUP.md` and `AUTOMATION.md`.

`status` SHALL suggest a level:

- `minor` when any archived change created a capability or added a requirement;
- `patch` when shipped paths changed and no archived change qualifies for `minor`.

It SHALL never suggest `major`; a major release is always the maintainer's explicit
call. It SHALL exit zero when nothing shipped is unreleased and one otherwise. It
SHALL support `--json` for the reminder hook.

#### Scenario: Nothing to release

- **WHEN** no commit since the latest tag touches a shipped path
- **THEN** `status` prints that the release is current and exits zero

#### Scenario: A new capability is unreleased

- **WHEN** a change archived since the tag created a new capability spec
- **THEN** `status` lists that change and suggests `minor`, and exits one

#### Scenario: Only a fix is unreleased

- **WHEN** shipped files changed since the tag, and no archived change added a
  requirement or a capability
- **THEN** `status` suggests `patch`

#### Scenario: Planning-only commits do not count

- **WHEN** every commit since the tag touches only `openspec/`, `docs/`, `tests/` or
  `.gatedloop/`
- **THEN** `status` reports nothing to release

### Requirement: A release is cut and published in two steps, with human review between them

`scripts/release cut <patch|minor|major>` SHALL do two things. It SHALL set all three
version fields to the next version. It SHALL also insert a section at the top of
`CHANGELOG.md` headed with that version and the current date. The section SHALL list
the archived changes, each with its name and the first sentence of its proposal's
`## Why`. It SHALL then list the other shipped commit subjects, excluding the
bookkeeping prefixes `propose:`, `attest approval:`, `archive change:`, `candidates:`
and `Release`.

`cut` SHALL leave the result uncommitted and print the next command. It SHALL refuse
to run on a dirty tree, off `main`, when `status` reports nothing to release, or when
`CHANGELOG.md` already has a section for that version.

`scripts/release publish` SHALL check every precondition before its first write:

- a clean tree, apart from the three manifest fields and the changelog;
- `check` passing;
- no existing tag for the version;
- an authenticated forge CLI.

Only then SHALL it commit the release as `Release X.Y.Z`, create an annotated tag
`vX.Y.Z`, push both, and create the GitHub release titled `gatedloop X.Y.Z` with the
changelog section as its notes. If any precondition fails, it SHALL exit non-zero,
write nothing, and name the failure. If a step fails after the commit, it SHALL name
the completed steps and the command that finishes the rest. It SHALL never leave a
tag without a matching commit.

#### Scenario: Cut proposes, a human reviews

- **WHEN** `scripts/release cut minor` runs on a clean `main` at `0.4.0` with
  unreleased shipped work
- **THEN** the three fields read `0.5.0`, `CHANGELOG.md` has a new `0.5.0` section at
  the top, nothing is committed, and the output names `scripts/release publish` as the
  next step

#### Scenario: Cut with nothing to release

- **WHEN** `status` reports nothing unreleased
- **THEN** `cut` exits non-zero and changes no file

#### Scenario: Publish checks everything first

- **WHEN** `publish` runs and the forge CLI is not authenticated
- **THEN** it exits non-zero before committing, and the tree is unchanged

#### Scenario: A complete publish

- **WHEN** `publish` runs after a reviewed `cut`, and every precondition holds
- **THEN** one `Release X.Y.Z` commit and one `vX.Y.Z` annotated tag exist on the
  remote, and a GitHub release carries that version's changelog section

#### Scenario: A push failure after commit

- **WHEN** the release commit succeeded but the push failed
- **THEN** `publish` exits non-zero, states that the commit exists locally and no tag
  was pushed, and prints the command that resumes from the push

### Requirement: The maintainer is reminded in-session when a release is due

This repository SHALL carry a project-level SessionStart hook in
`.claude/settings.json` that runs `scripts/release status --json`. When shipped work
is unreleased, the hook SHALL inject one line of session context: the latest tag, the
number of unreleased shipped commits and archived changes, and the suggested level.
When the release is current, or the script fails, it SHALL inject nothing and SHALL
never block the session. The hook SHALL live only in this repository's project
settings, never in the plugin's `hooks/hooks.json`, so adopters are never reminded
about gatedloop's own releases.

#### Scenario: A session starts with work unreleased

- **WHEN** a session starts in this repository and one archived change is unreleased
- **THEN** the session context includes one line naming the tag, the count and the
  suggested level

#### Scenario: Adopters never see it

- **WHEN** an adopter's session starts with the plugin installed
- **THEN** no release reminder appears, because the plugin's hooks contain none

### Requirement: The changelog is the record of every release

`CHANGELOG.md` at the repository root SHALL hold one section per released version,
newest first. Each section SHALL be headed `## X.Y.Z — YYYY-MM-DD`. The releases
before this procedure (0.2.0, 0.3.0, 0.4.0) SHALL be backfilled from their release
commit messages. Every GitHub release's notes SHALL equal its version's section.

#### Scenario: Backfilled history

- **WHEN** the change lands
- **THEN** `CHANGELOG.md` holds sections for 0.4.0, 0.3.0 and 0.2.0, in that order

### Requirement: The adopter-facing docs are checked against what ships before a release is cut

`scripts/release docs` SHALL build an inventory of every shipped command, agent,
skill, `gates` subcommand, gate name and top-level manifest key, taken from the
plugin's own files. It SHALL report every inventory item that README.md and SETUP.md
do not mention, and every such name they mention that no longer exists, each with its
file and line. It SHALL exit non-zero when it finds any gap. `cut` SHALL run it before
any other check, and SHALL refuse while it fails.

#### Scenario: A new command is undocumented

- **WHEN** `commands/merge.md` exists and neither README.md nor SETUP.md mentions
  `/gatedloop:merge`
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

### Requirement: A release that adds an adopter decision carries a catalogue entry

`scripts/release cut` SHALL warn when a commit since the latest tag changed the manifest
schema or added a rules-doc target, and no adoption catalogue item has the new version
as its `since`. The warning SHALL NOT block the cut, because not every schema change is
a decision an adopter has to make.

#### Scenario: A new manifest key without a catalogue entry

- **WHEN** a release is cut after a commit that added a property to the manifest schema,
  and no catalogue item carries the new version
- **THEN** `cut` prints a warning naming the schema change and the catalogue file, and
  completes

#### Scenario: The entry exists

- **WHEN** a catalogue item carries the new version as `since`
- **THEN** `cut` prints no adoption warning

### Requirement: Contract removals since the tag are reported as breaking

`scripts/release status` SHALL compare `tests/contract.json` at the latest `v*` tag with the one at `HEAD`. It SHALL list each removed `public` entry, and a raised ledger row version, under `breaking`, in text and in `--json`. Additions, `internal` entries and a tag that has no snapshot SHALL NOT count as breaking. The suggested level SHALL NOT change, so `status` still never suggests `major`.

#### Scenario: A flag was removed since the tag

- **WHEN** a public flag in the snapshot at the latest tag is absent at `HEAD`
- **THEN** `status` reports it under breaking

#### Scenario: Only additions

- **WHEN** the snapshot at `HEAD` only adds entries to the one at the tag
- **THEN** `status` reports nothing as breaking

#### Scenario: The tag predates the snapshot

- **WHEN** the latest tag has no `tests/contract.json`
- **THEN** `status` reports nothing as breaking, and says the comparison was skipped

### Requirement: A breaking release carries a migration step for each entry

`cut` SHALL draft a `### Breaking` subsection listing each entry `status` reports, each with `TODO` in place of its migration step. `publish` SHALL refuse while any `TODO` remains in that subsection.

#### Scenario: Cut drafts the entries

- **WHEN** `cut` runs with one public flag removed since the tag
- **THEN** the drafted section has a `### Breaking` entry naming the flag, with a `TODO` migration

#### Scenario: A breaking entry without its migration step

- **WHEN** `publish` runs and the version's `### Breaking` subsection still holds a `TODO`
- **THEN** it exits non-zero before its first write, naming the entry
