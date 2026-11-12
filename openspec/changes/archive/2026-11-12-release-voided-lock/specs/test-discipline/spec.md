## ADDED Requirements

### Requirement: The lock releases a voided path the approved plan moved out

A path whose every placement is void SHALL be released from the lock when every task
that placed it is declared `NO-TESTS` in the latest handoff and tagged `[oracle: none]`
both in the approved plan on the merge target and in the evaluated tree, and no task in
the latest handoff holds it. A path SHALL never be released when the approved plan cannot
be read. A
released path MAY differ from its content before the change. Otherwise the lock SHALL
refuse it, naming the first unmet condition.

#### Scenario: A task re-declared none after re-approval

- **WHEN** task 2.1's placement of `scripts/check.sh` was voided by a defect, the
  re-approved plan tags 2.1 `[oracle: none]`, the latest handoff declares 2.1 `NO-TESTS`,
  and the implementer stages an edit to `scripts/check.sh`
- **THEN** `gates tests check` passes the commit

#### Scenario: The tag still names a gate

- **WHEN** the same, but 2.1 is still tagged `[oracle: unit]`
- **THEN** `gates tests check` refuses, saying 2.1 is not tagged `[oracle: none]` in the
  approved plan

#### Scenario: Only the branch tags it none

- **WHEN** the same as the first scenario, but the merge target's `tasks.md` still tags
  2.1 `[oracle: unit]` and only the branch tags it `none`
- **THEN** `gates tests check`, `gates tests check --task 1.2` and `gates tests check
  --ref <commit>` each refuse, naming the approved plan's tag

#### Scenario: No approved plan to read

- **WHEN** the merge target does not resolve, or does not hold the change
- **THEN** the path is not released

#### Scenario: The handoff still holds the path

- **WHEN** the same as the first scenario, but task 3.1's handoff holds
  `scripts/check.sh`
- **THEN** `gates tests check` refuses, saying 3.1's handoff holds it

#### Scenario: The merge's remote check agrees

- **WHEN** `gates tests check --ref <commit>` evaluates a commit in the released state of
  the first scenario
- **THEN** it reports no problem for the path
