# Spec Delta

## MODIFIED Requirements

### Requirement: Gate markers can be published as commit statuses and verified remotely

`gates marker publish <gate>` SHALL post a `gatedloop/<gate>` commit status on a commit
whose ledger-normalized tree matches a green local marker for that gate, carrying that
tree hash. `gates marker publish tests` SHALL instead evaluate the authored-test lock
against the commit's tree and post `gatedloop/tests` as success only when the lock
holds, carrying the same tree hash; a change with no authored tests publishes success
saying so. `gates marker check-remote <gate> <sha>` SHALL succeed only when that
status exists, is successful, and names the normalized tree of `<sha>` itself. Both
SHALL fail loud when the forge CLI is unavailable.

#### Scenario: Publishing a green marker

- **WHEN** `gates marker publish live-check` runs on a head whose tree has a green
  live-check marker
- **THEN** a `gatedloop/live-check` success status appears on the head's sha, carrying
  that tree hash

#### Scenario: A status for a different tree

- **WHEN** a `gatedloop/ci` status on a sha names a tree other than that sha's normalized
  tree
- **THEN** `check-remote` fails and names both trees

#### Scenario: No local marker

- **WHEN** `gates marker publish ci` runs with no green `ci` marker for the head's tree
- **THEN** it refuses and posts nothing

#### Scenario: The forge CLI is missing

- **WHEN** the forge CLI is not installed or not authenticated
- **THEN** both commands exit non-zero naming the missing prerequisite, and `gates
  doctor` reports it as a warning where pull-request mode is declared

#### Scenario: Publishing the lock

- **WHEN** `gates marker publish tests` runs on a head whose placed tests all match
  their placed content and whose placed tasks have their red runs recorded
- **THEN** a `gatedloop/tests` success status appears on the head's sha, carrying the
  tree hash

#### Scenario: Publishing a broken lock

- **WHEN** `gates marker publish tests` runs on a head where a placed test was edited
  past the commit hooks
- **THEN** it posts a failure status naming the path, and exits non-zero
