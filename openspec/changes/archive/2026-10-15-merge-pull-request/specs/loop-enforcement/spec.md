## ADDED Requirements

### Requirement: Gate markers can be published as commit statuses and verified remotely

`gates marker publish <gate>` SHALL post a `specloop/<gate>` commit status on a commit
whose ledger-normalized tree matches a green local marker for that gate, carrying that
tree hash. `gates marker check-remote <gate> <sha>` SHALL succeed only when that
status exists, is successful, and names the normalized tree of `<sha>` itself. Both
SHALL fail loud when the forge CLI is unavailable.

#### Scenario: Publishing a green marker

- **WHEN** `gates marker publish live-check` runs on a head whose tree has a green
  live-check marker
- **THEN** a `specloop/live-check` success status appears on the head's sha, carrying
  that tree hash

#### Scenario: A status for a different tree

- **WHEN** a `specloop/ci` status on a sha names a tree other than that sha's normalized
  tree
- **THEN** `check-remote` fails and names both trees

#### Scenario: No local marker

- **WHEN** `gates marker publish ci` runs with no green `ci` marker for the head's tree
- **THEN** it refuses and posts nothing

#### Scenario: The forge CLI is missing

- **WHEN** the forge CLI is not installed or not authenticated
- **THEN** both commands exit non-zero naming the missing prerequisite, and `gates
  doctor` reports it as a warning where pull-request mode is declared

### Requirement: Scale is documented as an example built from shipped primitives

The documentation SHALL include a worked example of running parallel lanes and a CI
integration using only commands and agents Specloop ships. The example SHALL mark its
orchestrator loop and CI workflow as examples for the adopter to adapt, not as
supported components. It SHALL direct pull-request-mode adopters to require the
`specloop/*` statuses from their CI provider as the expected source.

#### Scenario: An adopter wants lanes and CI

- **WHEN** an adopter reads the scale documentation
- **THEN** it shows selection, authoring, lane dispatch, readiness, merge in both modes,
  status publishing and forge-merge recording, each through a named Specloop command,
  with the orchestration and workflow presented as the adopter's own
