## ADDED Requirements

### Requirement: An acceptance is refused for a plan that is not the approved one

Every acceptance writer (`gates acceptance attest --local`, `--pr` and `--merged`) SHALL refuse to write an `accept` row for a change whose plan does not hash to its recorded `approved_sha`, as `gates merge` step 1 checks it. Under `approval.acceptance: self`, `gates record-merged` SHALL still record the merge row, write no `accept` row, and exit non-zero naming the reason.

#### Scenario: Local acceptance of an amended plan

- **WHEN** `gates acceptance attest <change> --local` runs and the change's plan was amended after approval without re-attesting
- **THEN** it exits 1 naming the stale approval, and no `accept` row is written

#### Scenario: A merged implementation PR of an amended plan

- **WHEN** `gates record-merged` records an implementation PR under `approval.acceptance: self` and the merged plan does not match its approval
- **THEN** the merge row is written, no `accept` row is written, and the command exits non-zero naming the re-approval route
