## MODIFIED Requirements

### Requirement: A missing source is recorded, never a failure

When no readable transcript is available, `usage record` SHALL append a row with null counts and a `source` naming the reason, exit 0, and never block the commit or the stop that invoked it. A row recorded by a commit hook, at the Claude layer or the git layer, SHALL be staged into the commit being made, so a commit leaves the change's ledger with no unrecorded rows.

#### Scenario: A human session commits

- **WHEN** a commit passes the hook in a session with no transcript path
- **THEN** the commit proceeds and the usage row records null counts with the reason

#### Scenario: An unreadable transcript

- **WHEN** the transcript path exists but cannot be parsed
- **THEN** the row records null counts, names the parse failure, and the hook exits 0

#### Scenario: A git-layer commit leaves the ledger clean

- **WHEN** a commit on a change branch passes the git-layer pre-commit hook, whether made with `git commit`, `git commit -a` or `git commit <paths>`
- **THEN** the hook's `no-transcript` usage row is part of that commit, and the change's ledger shows no changes against the new head

#### Scenario: A merge reaches integration with the git hook installed

- **WHEN** `gates merge` runs on a change whose lane has the shipped git pre-commit hook installed and trailing ledger rows to commit
- **THEN** step 1 commits the trailing rows together with the hook's own usage row, the ledger is clean afterwards, and step 2 detaches onto the target
