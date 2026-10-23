## ADDED Requirements

### Requirement: `gates merge` in pull-request mode proves the head locally and hands integration to the forge

Under `integration.mode: pull-request`, `gates merge <change>` SHALL:

- commit trailing ledger rows;
- run the incoming-tree checks on the head;
- push the branch;
- publish the head's gate markers as commit statuses;
- open or update the pull request, with the acceptance brief as its body.

It SHALL enable squash auto-merge only when `requireApproval` is false and any
declared acceptance policy is satisfied. Otherwise it SHALL stop and print the pull
request's URL.

#### Scenario: No approval required and acceptance satisfied

- **WHEN** `requireApproval` is false and no acceptance policy is declared, or the
  declared one is satisfied
- **THEN** the pull request is opened with auto-merge enabled, and the command reports
  that the forge will integrate it once required checks pass

#### Scenario: Approval required

- **WHEN** `requireApproval` is true
- **THEN** the pull request is opened, auto-merge is not enabled, and the command prints
  the URL and stops

#### Scenario: The head is not proven

- **WHEN** the head has no live-check marker
- **THEN** nothing is pushed and no pull request is opened

### Requirement: A forge merge can be recorded and archived by one command

`gates record-merged <sha>` SHALL:

- resolve the change a squash commit came from, through the head branch of the pull
  request that produced it;
- record that change's merge row against `<sha>`;
- archive the change;
- commit both in the local checkout.

It SHALL NOT push. It SHALL do nothing, and exit 0 with a note, when the commit came
from no active change, including a change already archived.

#### Scenario: A change's pull request was merged in the forge

- **WHEN** `gates record-merged` runs on the squash commit of a pull request whose head
  branch names an active change
- **THEN** one local commit holds the change's merge row naming that sha, together with
  its archive, and `gates stats --outcomes` counts the change as merged

#### Scenario: An ordinary pull request was merged

- **WHEN** the pull request's head branch names no active change
- **THEN** nothing is recorded or committed

#### Scenario: Run twice

- **WHEN** `gates record-merged` runs again for a change it already archived
- **THEN** it does nothing and exits 0

### Requirement: Readiness is a committed ledger fact

`gates ledger record-ready <change>` SHALL append a `ready` row to the change's ledger.
The implementer SHALL record it and commit it, at ledger grade, immediately before
reporting READY TO MERGE.

#### Scenario: An implementer finishes a change

- **WHEN** `tdd-implementer` reaches READY TO MERGE
- **THEN** the change's committed ledger ends with a `ready` row newer than its last
  task row, readable by any process with the repository
