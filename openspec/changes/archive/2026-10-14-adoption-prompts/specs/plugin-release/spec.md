## ADDED Requirements

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
