## MODIFIED Requirements

### Requirement: An ungated commit is detected after the fact and taints the change

The `Stop` hook SHALL audit commits created since the last audited point by joining
each commit's tree to the durable ledger's green-`ci` rows for the change. A commit
whose tree has no matching green-`ci` row SHALL be reported loudly, naming the
offending commit, and SHALL record a taint on the change's durable ledger. This is
detection after the effect, not prevention, and SHALL NOT be presented as prevention.

The audit SHALL scope itself to the change branch's own commits: a commit already
reachable from the resolved merge target SHALL be exempt from tainting, because it
was gated by its own change before landing there. Merge-target ancestry SHALL be the
only exemption from auditing — authorship, committer identity, or timestamps SHALL NOT
exempt a commit.

A commit whose tree has no green-`ci` row of its own SHALL be recorded as `vouched`,
not tainted, when it is an ancestor of the branch head being audited and a green,
unscoped `ci` row names that head's tree, compared ledger-blind as the tree join is.
A `vouched` row SHALL name the commit and SHALL NOT count as an incident or as an
individually gated commit. A scoped `ci` on the head SHALL NOT vouch, and with no
green unscoped `ci` on the head the commit SHALL be tainted as before. Commit
timestamps SHALL NOT be read for vouching. When no merge target can be resolved, the audit SHALL keep its current
behaviour and consider every commit in the walk (erring toward auditing more, never
toward silently skipping any).

The same walk SHALL classify a commit whose matching green-`ci` rows were all written
outside an agent session as a `human-commit` intervention (see the escalation-record
capability); classification is additive to tainting and never replaces it. The merge
gate SHALL run this audit before its taint check, so a commit created after the last
session stop is tainted or classified before the merge decision is made.

#### Scenario: All commits are gated

- **WHEN** the audit runs and every new commit's tree matches a green-`ci` ledger row
  for the change
- **THEN** no taint is recorded and nothing is reported as an incident

#### Scenario: A commit has no green-CI record

- **WHEN** the audit finds a new commit whose tree matches no green-`ci` ledger row
  (it slipped the invocation and git-layer hooks)
- **THEN** the audit reports the offending commit loudly and records a taint on the
  change's ledger

#### Scenario: The audit does not re-report the same commit

- **WHEN** the audit runs again after a commit was already audited
- **THEN** it only considers commits new since the last audited point and does not
  re-report an already-audited commit

#### Scenario: Adopted merge-target commits do not taint

- **WHEN** the change branch is fast-forwarded (or otherwise updated) onto a moved
  merge target and the audit runs, so commits already reachable from the merge
  target enter the range since the last audited point
- **THEN** those adopted commits are exempt and record no taint, even though their
  trees have no green-`ci` ledger row for this change

#### Scenario: A local ungated commit still taints after adoption

- **WHEN** after adopting merge-target commits, a new commit is created on the change
  branch without a green-`ci` ledger row for its tree
- **THEN** the audit taints that commit exactly as before — merge-target ancestry
  exempts only commits already on the merge target, never new local commits

#### Scenario: No merge target resolves

- **WHEN** the audit runs in a repository where no merge target can be resolved
- **THEN** the walk since the last audited point is unchanged from today and every
  commit in it is audited — the exemption never widens into a silent skip

#### Scenario: The merge gate audits before deciding

- **WHEN** a merge is attempted after a commit landed on the change branch since the
  last session stop
- **THEN** the merge gate runs the audit first, so that commit is tainted (no green
  record) or classified (human-gated) before the taint check that follows

#### Scenario: A rebased branch whose head passed a full ci

- **WHEN** a change branch is rebased, so its commits have trees no `ci` saw, then
  `gates run ci` passes unscoped on the new head, and the audit runs (as at `gates
  merge` step 1)
- **THEN** each rebased commit is recorded as `vouched`, no taint is recorded, and the
  merge is not blocked on that basis

#### Scenario: A scoped ci on the head vouches for nothing

- **WHEN** the same rebased branch's head passed only a scoped `ci`, and the audit runs
- **THEN** the rebased commits are tainted as before

#### Scenario: A commit after the head ci is not vouched

- **WHEN** a commit is created on the branch after the green unscoped `ci` on the
  previous head, without a green-`ci` row of its own, and the audit runs
- **THEN** that commit is the new head, no green unscoped `ci` row names its tree, and
  it is tainted

#### Scenario: A vouched commit is not re-reported

- **WHEN** the audit runs again after a commit was recorded as `vouched`
- **THEN** the commit is neither re-vouched nor tainted
