## ADDED Requirements

### Requirement: `gates merge` performs local integration as six ordered steps

Under `integration.mode: local-squash-merge`, `gates merge <change>` SHALL run these
steps in order:

1. prove the branch head;
2. squash it onto the integration target's tip;
3. prove the merged tree with an unscoped `ci`;
4. record the merge against the squash commit;
5. run the `confirm` gate on the merged tree where declared;
6. archive the change, then publish every commit to the remote target in one push.

It SHALL stop at the first failing step with that step's refusal, and nothing SHALL
be pushed unless every step passed.

#### Scenario: Every step passes

- **WHEN** `gates merge <change>` runs on an accepted, live-checked change branch whose
  squash is green and whose `confirm` gate passes
- **THEN** the remote target gains the squash commit, the ledger-grade merge row
  commit and the archive commit, in one push, and the merge row names the squash
  commit's sha

#### Scenario: The merged tree is red

- **WHEN** the unscoped `ci` fails on the squashed tree
- **THEN** nothing is committed to the target, the primary checkout is restored to
  where it was, and the command exits non-zero naming step 3

#### Scenario: The live confirmation fails

- **WHEN** the `confirm` gate fails on the merged tree
- **THEN** nothing is pushed, the local commits are discarded, and the failure is
  recorded in the change's ledger on its branch

#### Scenario: The target moved during the merge

- **WHEN** the push is rejected because the remote target advanced
- **THEN** the merge restarts from step 2 once against the new tip, and halts if the
  second push is also rejected

### Requirement: Proving the head uses the merge gate's own checks and commits trailing ledger rows

Step 1 SHALL commit any uncommitted ledger rows on the change branch at ledger grade.
It SHALL then require everything the merge hook requires of the incoming tree: the
live-check marker, a green `verify` where declared, no unresolved taint, and an
acceptance where a policy is declared. It SHALL print each scenario's coverage from
the acceptance brief.

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

### Requirement: A squash conflict halts without touching the target

When the squash conflicts, `gates merge` SHALL abort the squash, restore the primary
checkout, and exit non-zero naming the conflicting paths. The target SHALL be
unchanged.

#### Scenario: The branch conflicts with the target

- **WHEN** the change branch and the target changed the same lines
- **THEN** the command exits non-zero listing the conflicting paths, and the target
  and the working tree are exactly as before the command

### Requirement: Merges are serialized per machine

`gates merge` SHALL hold a machine-wide `merge` lock for its whole duration, shared by
every worktree of the repository and bounded like other serialized gates.

#### Scenario: Two merges at once

- **WHEN** two worktrees run `gates merge` concurrently
- **THEN** one waits for the other, and both integrate against the target tip current
  when they start their step 2

### Requirement: Who may merge is unchanged by owning the merge

`gates merge` SHALL enforce the declared process's human boundaries in code. It SHALL
refuse while a declared acceptance policy is unsatisfied. The `tdd-implementer` agent
SHALL NOT run it. The `merge-runner` agent SHALL resolve only mechanical conflicts,
SHALL re-run the head's gates after any resolution, and SHALL halt on a conflict that
needs judgement.

#### Scenario: The merge runner meets a semantic conflict

- **WHEN** a squash conflict cannot be resolved without choosing between two
  behaviours
- **THEN** the merge runner halts with cause `other`, naming the paths and the two
  sides, and does not choose

#### Scenario: The implementer finishes a change

- **WHEN** `tdd-implementer` reaches the end of a change
- **THEN** it stops before the merge as before, and never invokes `gates merge`
