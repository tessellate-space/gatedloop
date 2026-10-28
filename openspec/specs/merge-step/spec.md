# merge-step Specification

## Purpose
Merge a verified change onto its target in code: `gates merge <change>` re-checks the incoming tree, squashes, runs `ci` and the optional `confirm` gate, records the merge and archives, then pushes once — serialized by a merge lock, restoring the checkout on any refusal, and exiting with the number of the step that refused.

## Requirements

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

### Requirement: Readiness is a committed ledger fact

`gates ledger record-ready <change>` SHALL append a `ready` row to the change's ledger.
The implementer SHALL record it and commit it, at ledger grade, immediately before
reporting READY TO MERGE.

#### Scenario: An implementer finishes a change

- **WHEN** `tdd-implementer` reaches READY TO MERGE
- **THEN** the change's committed ledger ends with a `ready` row newer than its last
  task row, readable by any process with the repository

### Requirement: A merge step whose gate did not run is reported as not run

When the `ci` gate at step 3 or the `confirm` gate at step 5 of `gates merge` exits 75,
the merge SHALL restore the checkout, commit nothing, exit 75, and report that the
gate did not run, naming the lock holder and wait or the failed precondition. It SHALL
NOT report the merged tree as failed.

#### Scenario: The ci lock is busy past its bound

- **WHEN** step 3's `ci` cannot take the serialized lock within its bound
- **THEN** `gates merge` exits 75, names the holder, says nothing about the merged tree
  is known yet, and leaves the target and checkout unchanged

#### Scenario: The merged tree is red

- **WHEN** step 3's `ci` runs and exits 1
- **THEN** the merge reports the merged tree as failed, as before

### Requirement: A waiting merge takes a serialized lock before other waiters

While `gates merge` waits on a serialized gate's lock it SHALL hold a priority claim,
and any other waiter SHALL NOT acquire that lock while the claim's process is alive.
The current holder SHALL never be pre-empted, and a claim whose process is dead SHALL
be ignored. The merge's own wait SHALL be bounded by `concurrency.merge-wait-seconds`,
defaulting to `concurrency.max-wait-seconds`.

#### Scenario: A lane and a merge wait on the same lock

- **WHEN** a lane holds the `ci` lock, and a merge and a second lane are both waiting
- **THEN** when the lock is released the merge acquires it, and the second lane
  acquires it only after the merge releases it

#### Scenario: A stale claim

- **WHEN** a priority claim names a process that no longer exists
- **THEN** waiters ignore it and the lock is taken in the usual order

### Requirement: The permission scaffolding's checkpoint is the integrating command

`gates-init`'s permission scaffolding SHALL write its `ask` rule for
`Bash(gates merge *)`, not for every `git merge`. `gates doctor` SHALL warn when the
project's local settings still ask on `Bash(git merge *)`, naming the replacement.

#### Scenario: Scaffolding written fresh

- **WHEN** the adopter accepts permission scaffolding in `gates-init`
- **THEN** the written `ask` list is `["Bash(gates merge *)"]`

#### Scenario: An older scaffolding

- **WHEN** `.claude/settings.local.json` asks on `Bash(git merge *)`
- **THEN** the doctor's `merge-checkpoint` row warns and names `Bash(gates merge *)`
