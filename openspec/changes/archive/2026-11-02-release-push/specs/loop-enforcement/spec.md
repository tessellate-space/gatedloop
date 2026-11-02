## ADDED Requirements

### Requirement: A push refusal names only a change the push carries in

A push gate refusal SHALL name only changes whose branch brings commits the target's remote-tracking ref lacks; a change branch whose tip is already an ancestor of that ref SHALL NOT be named. When the refused commit carries no change, the refusal SHALL say it belongs to no change in flight and name no `gates merge` command, while still listing the unmet checks.

#### Scenario: A fresh change branch is not blamed

- **WHEN** an agent session pushes an unproven commit to the target while a change branch exists locally whose tip is an ancestor of the target's remote-tracking ref
- **THEN** the push is denied and the refusal does not name that change

#### Scenario: A commit that belongs to no change

- **WHEN** an agent session pushes an unproven commit to the target that carries no change branch's commits
- **THEN** the push is denied and the refusal says the commit belongs to no change in flight, names no `gates merge` command, and still lists the unmet checks

#### Scenario: A change branch with its own commits is still named

- **WHEN** an agent session pushes an unproven commit to the target that contains one change branch's own commits
- **THEN** the refusal names that change in `gates merge <change>`
