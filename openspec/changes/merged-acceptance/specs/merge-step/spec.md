## MODIFIED Requirements

### Requirement: A forge merge can be recorded and archived by one command

`gates record-merged <sha>` SHALL:

- resolve the change a squash commit came from, through the head branch of the pull
  request that produced it;
- under `approval.acceptance: self`, record that pull request's merge as the change's
  acceptance, as `gates acceptance attest <change> --merged <pr>` does, unless an
  `accept` row for the merge commit's tree already exists;
- record that change's merge row against `<sha>`;
- archive the change;
- commit all of them in one local commit.

When the pull request's head branch is `plan/<change>` under `approval.plan: self`, it
SHALL attest the plan from the merge when the change has no approval, or when its
`approved_sha` no longer matches the plan in the merge commit; it SHALL skip only a
change whose recorded approval still matches.

It SHALL NOT push. It SHALL do nothing, and exit 0 with a note, when the commit came
from no active change, including a change already archived.

#### Scenario: A change's pull request was merged in the forge

- **WHEN** `gates record-merged` runs on the squash commit of a pull request whose head
  branch names an active change
- **THEN** one local commit holds the change's merge row naming that sha, together with
  its archive, and `gates stats --outcomes` counts the change as merged

#### Scenario: A solo project's merge is its acceptance

- **WHEN** `approval.acceptance` is `self` and `gates record-merged` runs on the squash
  commit of the change's merged pull request #42, with no acceptance recorded
- **THEN** the same local commit holds an `accept` row from PR #42's merge, pinned to the
  merge commit's tree, and `gates stats --outcomes` counts the change as `accepted`

#### Scenario: A merged plan amendment

- **WHEN** plan PR #76 amends an approved change's specs and is merged under
  `approval.plan: self`
- **THEN** `gates record-merged` re-attests the change from #76's merge and
  `check-implement` accepts it

#### Scenario: An ordinary pull request was merged

- **WHEN** the pull request's head branch names no active change
- **THEN** nothing is recorded or committed

#### Scenario: Run twice

- **WHEN** `gates record-merged` runs again for a change it already archived
- **THEN** it does nothing and exits 0
