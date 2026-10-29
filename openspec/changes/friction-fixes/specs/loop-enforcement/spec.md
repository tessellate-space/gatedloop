## MODIFIED Requirements

### Requirement: Only integration merges are gated

The merge hook SHALL gate only a merge whose destination is the integration target. A
merge into any other branch SHALL pass the hook without a marker check.

When the same command switches branches before it merges, the hook SHALL judge the destination from the branch that switch names. A switch to a named branch other than the integration target's SHALL pass. A switch the hook cannot resolve to one named branch SHALL keep the merge gated, and the denial SHALL say to run the merge as its own command after the switch.

#### Scenario: Syncing the target into a change branch

- **WHEN** a change branch is checked out and the integration target is merged into it
- **THEN** the merge hook allows it without requiring a live-check marker

#### Scenario: Integrating a change

- **WHEN** the integration target is checked out and a change branch is merged into it
- **THEN** the merge hook applies its marker checks as before

#### Scenario: Switching to a change branch and syncing it

- **WHEN** one command runs `git checkout my-change && git merge --ff-only origin/main`
- **THEN** the merge hook allows it without requiring a live-check marker

#### Scenario: Switching to the target and merging

- **WHEN** one command runs `git checkout main && git merge --ff-only my-change`
- **THEN** the merge hook applies its marker checks as before

#### Scenario: A switch the hook cannot resolve

- **WHEN** one command runs `git checkout --detach origin/main && git merge my-change`
- **THEN** the merge hook applies its marker checks, and its denial says to run the merge as its own command after the switch
