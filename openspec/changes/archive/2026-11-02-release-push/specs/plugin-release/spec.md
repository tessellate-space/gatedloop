## ADDED Requirements

### Requirement: Publishing runs outside an agent session

`scripts/release publish` SHALL refuse before its first write when `gates discipline agent-session` reports an agent session. The refusal SHALL write the release notes to `.gatedloop/out/release-notes-vX.Y.Z.md` and print the command sequence `publish` would run, in its fixed order, for the maintainer to run outside an agent session.

#### Scenario: Publish from an agent session

- **WHEN** the maintainer's agent session runs `scripts/release publish` with every other precondition met
- **THEN** it exits 1 having made no commit, tag or release, writes the notes file, and prints the command sequence ending in `gh release create … --notes-file .gatedloop/out/release-notes-vX.Y.Z.md`

#### Scenario: Publish outside an agent session

- **WHEN** `scripts/release publish` runs with no agent-env variable set and every precondition met
- **THEN** it commits, pushes, tags, pushes the tag and creates the release as before
