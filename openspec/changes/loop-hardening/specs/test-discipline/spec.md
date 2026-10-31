## ADDED Requirements

### Requirement: Placement accepts the content the branch received from main

`gates tests place` SHALL accept a file whose current content equals its content at the merge base of the branch and the merge target, as well as its base and its placed content. A pre-existing file that main changed and the branch synced SHALL NOT be reported as a test defect. When no merge target resolves, the accepted set SHALL be unchanged.

#### Scenario: Main changed a file the task's tests replace

- **WHEN** a task's handoff recorded a base for `tests/x`, main then changed `tests/x`, the branch synced main, and the task is placed
- **THEN** placement succeeds, and the refusal naming a test defect is not printed

#### Scenario: A file nobody but the lane changed

- **WHEN** the file differs from its base, from its content at the merge base, and from every placed blob
- **THEN** placement refuses as a test defect, as today

### Requirement: A full handoff never drops a placed task

`gates tests handoff <change>` without `--task` SHALL refuse when a task holding a placement under the current authoring state is absent from the holding area. The refusal SHALL name each such task and the `--task` route, and nothing SHALL be written.

#### Scenario: A full handoff after a partial placement

- **WHEN** task 1.1 is placed, and a full handoff is run with only task 1.2 in the holding area
- **THEN** it exits 1 naming task 1.1 and `gates tests handoff <change> --task 1.2`, and the authoring state, characterization declarations included, is unchanged
