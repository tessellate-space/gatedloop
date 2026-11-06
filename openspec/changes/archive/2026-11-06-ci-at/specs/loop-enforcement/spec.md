# Spec Delta

## MODIFIED Requirements

### Requirement: Commit is blocked unless CI passed on the tree being committed
A `git commit` SHALL be denied unless a fresh `ci` marker exists whose recorded tree matches the tree that would be committed (the staged index). The gate SHALL be an O(1) marker/hash comparison and SHALL NOT re-run CI.

Under `loop.ci-at: ready`, on a branch that names an active change, a fresh `unit` marker for the staged tree SHALL also allow the commit; a `ci` marker still does. Off such a branch, and under `loop.ci-at: task` or with the key absent, only a `ci` marker allows it.

#### Scenario: Commit after green CI on the same staged tree
- **WHEN** `gates run ci` passed and recorded the current index tree, and no tracked file changed since
- **THEN** the `PreToolUse` hook allows the `git commit`

#### Scenario: Commit attempted with no CI marker
- **WHEN** a `git commit` is attempted and no `ci` marker exists for the staged tree
- **THEN** the hook denies the commit (exit 2) and reports that `ci` must pass first

#### Scenario: Commit attempted after an edit invalidates the marker
- **WHEN** a tracked file is edited after a green `ci`, so the staged tree no longer matches the marker
- **THEN** the hook denies the commit — a marker cannot survive an edit

#### Scenario: A task commit on a green unit under ready

- **WHEN** `loop.ci-at: ready` is declared, the branch names an active change, and
  `gates run unit` passed on the staged tree with no `ci` run for it
- **THEN** the commit hook allows the `git commit`, and its allow line names
  `loop.ci-at: ready`

#### Scenario: A unit marker is not enough under task

- **WHEN** `loop.ci-at` is absent, and only a green `unit` run recorded the staged tree
- **THEN** the hook denies the commit and reports that `ci` must pass first

#### Scenario: Off a change branch the ci marker is required under ready

- **WHEN** `loop.ci-at: ready` is declared, a non-planning diff is staged on `main` or
  on a detached HEAD (as during `gates merge`), and only a `unit` marker matches
- **THEN** the commit check denies the commit

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

Under `loop.ci-at: ready`, a green `unit` row SHALL count as a matching row for
this join, in the audit and in the merge's read-only check of a branch no worktree
holds, so a commit the commit hook allowed on a `unit` marker is gated, not tainted or
vouched. The mode SHALL be read from the manifest when the audit runs. A green `unit`
row SHALL NOT vouch for another commit, and under `loop.ci-at: task` it SHALL NOT
match.

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

#### Scenario: A unit-gated task commit under ready is not tainted mid-change

- **WHEN** `loop.ci-at: ready` is declared, a task commit's tree matches a green
  `unit` row and no `ci` row, no unscoped `ci` names the head yet, and the `Stop`
  hook's audit runs
- **THEN** no taint and no `vouched` row is recorded for that commit, and it is
  classified by its row's session as a `ci`-gated commit is

#### Scenario: A unit row does not gate a commit under task

- **WHEN** `loop.ci-at` is absent and a commit's tree matches only a green `unit` row
- **THEN** the audit taints the commit, as before

#### Scenario: An ungated commit under ready still taints

- **WHEN** `loop.ci-at: ready` is declared and a commit's tree matches no green `ci`
  row and no green `unit` row, and no unscoped `ci` names the head
- **THEN** the audit taints the commit

#### Scenario: The read-only merge check accepts the unit row under ready

- **WHEN** `loop.ci-at: ready` is declared, no worktree holds the change branch, and
  each of its commits matches a green `unit` or `ci` row
- **THEN** `gates merge` step 1 names no commit as having no green record

### Requirement: The READY report's gate fields are read from the ledger

`gates ledger record-ready <change>` SHALL print the report's `gates` block, derived from the ledger and the markers for the head tree: `ci` as `pass` or `fail`; `review` as `clean`, `findings`, `partial` (some completed task has no review row) or `none` (no review row); `live_check` as `pass`, `fail` or `na`. The implementer SHALL copy that block into its final report unchanged. Under `loop.ci-at: ready`, `record-ready` SHALL refuse with exit 1 and append no row unless a green unscoped `ci` row names the head's tree, ledger-blind, and its refusal SHALL name `gates run ci` with nothing staged as the remedy.

#### Scenario: No review was recorded

- **WHEN** a change reaches READY with no review row in its ledger
- **THEN** `record-ready` prints `"review": "none"`, and the implementer's report carries `"review": "none"`

#### Scenario: Every completed task was reviewed clean

- **WHEN** each completed task's latest review row is clean
- **THEN** `record-ready` prints `"review": "clean"`

#### Scenario: READY without a full ci under ready

- **WHEN** `loop.ci-at: ready` is declared and no green unscoped `ci` row names the
  head's tree
- **THEN** `gates ledger record-ready` exits 1, appends no `ready` row, and names an
  unscoped `gates run ci` on the head as the remedy

#### Scenario: READY after a full ci under ready

- **WHEN** `loop.ci-at: ready` is declared and `gates run ci` passed unscoped on the
  head
- **THEN** `record-ready` appends the `ready` row and prints `"ci": "pass"`

#### Scenario: READY without a full ci under task

- **WHEN** `loop.ci-at` is absent and no green unscoped `ci` row names the head's tree
- **THEN** `record-ready` appends the `ready` row and prints `"ci": "fail"`, as before

## ADDED Requirements

### Requirement: When the full ci runs is declared by `loop.ci-at`

`.gates.yaml` MAY declare `loop.ci-at` as `task` (the default) or `ready`. `gates
validate` SHALL fail, naming the key, on any other value, and SHALL fail on `ready`
when no global `unit` gate is declared, naming the missing gate. Absent, the loop
SHALL behave as under `task`.

#### Scenario: Key absent

- **WHEN** `.gates.yaml` declares no `loop.ci-at`
- **THEN** every task commit needs a `ci` marker, as before

#### Scenario: An unknown value

- **WHEN** `loop.ci-at: merge` is declared
- **THEN** `gates validate` fails and names `loop.ci-at` and its two values

#### Scenario: ready without a unit gate

- **WHEN** `loop.ci-at: ready` is declared and `gates.unit` is not
- **THEN** `gates validate` fails, naming `loop.ci-at: ready` and the missing `unit`
  gate

### Requirement: The shim names the commit gate in effect

`gates task start` and a successful `gates tests handoff` SHALL print, on stderr, the
gate a commit on the current change needs: `gates run ci`, or `gates run unit` under
`loop.ci-at: ready` together with the fact that the full `ci` runs before `gates ledger
record-ready`. A commit denial under `ready` SHALL name `gates run unit` as the remedy.

#### Scenario: Under task

- **WHEN** `loop.ci-at` is absent and `gates task start 1.1` runs
- **THEN** its stderr names `gates run ci` as the commit gate, and its stdout is as
  before

#### Scenario: Under ready

- **WHEN** `loop.ci-at: ready` is declared and `gates task start 1.1` runs
- **THEN** its stderr names `gates run unit` as the commit gate and says the full
  `ci` runs before `gates ledger record-ready`

#### Scenario: A denial under ready

- **WHEN** `loop.ci-at: ready` is declared, the branch names an active change, and no
  `unit` or `ci` marker matches the staged tree
- **THEN** the commit denial names `gates run unit`
