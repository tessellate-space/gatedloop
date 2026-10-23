# Spec Delta

## MODIFIED Requirements

### Requirement: Proving the head uses the merge gate's own checks and commits trailing ledger rows

Step 1 SHALL commit any uncommitted ledger rows on the change branch at ledger grade.
It SHALL then require everything the merge hook requires of the incoming tree: the
live-check marker, a green `verify` where declared, no unresolved taint, and an
acceptance where a policy is declared. It SHALL also require the authored-test lock
to hold at the branch head, in both integration modes. It SHALL print each scenario's
coverage from the acceptance brief.

#### Scenario: A live-check row is uncommitted

- **WHEN** the lane's last live-check appended a ledger row that was never committed
- **THEN** step 1 commits it on the branch, and the detach in step 2 is not refused

#### Scenario: Acceptance is required and missing

- **WHEN** the project declares an acceptance policy and the head has no acceptance
- **THEN** step 1 refuses with the acceptance gate's own message, and nothing further
  runs

#### Scenario: Coverage is shown

- **WHEN** step 1 passes
- **THEN** its output lists every spec scenario as covered or to be checked by hand

#### Scenario: The lock is broken at the head

- **WHEN** a placed test at the branch head differs from its placed content and no
  defect voided the placement
- **THEN** step 1 refuses, naming the path and the task, and nothing is pushed, squashed
  or opened
