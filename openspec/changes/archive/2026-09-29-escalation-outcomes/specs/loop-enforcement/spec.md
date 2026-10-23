# Spec Delta

## MODIFIED Requirements

### Requirement: The loop continues unattended without spinning
A `Stop` hook SHALL continue the loop when a change branch is checked out, `tasks.md`
has unchecked tasks, the tree is clean at a task boundary, and the change's ledger
carries no recorded halt since the last task began; and it SHALL NOT continue when
already re-entered. A recorded halt is a `halt` row with no later `task-start` row for
the change: the shim's continue check SHALL treat that state as halted, so a halt the
implementer recorded takes effect and a halt it merely narrated does not. Starting a
task again (a new `task-start` row) SHALL be what lifts the halt, so a resumed run
continues normally.

#### Scenario: More tasks remain
- **WHEN** the session stops with unchecked tasks and a clean tree on a change branch,
  and the ledger holds no `halt` row after the latest `task-start`
- **THEN** the hook blocks the stop and directs continuation from the next unchecked task

#### Scenario: Runaway is prevented
- **WHEN** the `Stop` hook input has `stop_hook_active` set
- **THEN** the hook does not re-block, so it cannot infinite-loop

#### Scenario: Halted or blocked run does not spin
- **WHEN** the run halted or a gate is red (tree not clean at a task boundary)
- **THEN** the hook does not continue

#### Scenario: A recorded halt with a clean tree does not continue
- **WHEN** the session stops on a change branch with unchecked tasks and a clean tree,
  and the ledger's latest `halt` row for the change is newer than its latest
  `task-start` row
- **THEN** the continue check exits non-zero naming the recorded cause, and the hook
  hands control back instead of continuing

#### Scenario: An unrecorded halt is re-entered
- **WHEN** an implementer stops with unchecked tasks and a clean tree after writing a
  HALTED report but recording no `halt` row
- **THEN** the hook continues the loop exactly as for a task boundary — the halt did
  not take, because only the ledger can make it take

#### Scenario: Resuming lifts the halt
- **WHEN** a `task-start` row is appended after the `halt` row and the session later
  stops at a clean task boundary
- **THEN** the hook continues the loop again

### Requirement: Every gate invocation is recorded in a durable ledger
`gates run <gate>` SHALL append one row to a durable, committed ledger recording the
outcome, separate from the ephemeral enforcement marker. The ledger SHALL survive a
squash-merge and SHALL NOT be stored anywhere that dies with the clone. Every row,
of every kind, SHALL carry a `session` value (`agent` or `human`) set by the ledger
writer from the presence of the Claude Code session marker.

#### Scenario: A gate runs and is recorded
- **WHEN** `gates run <gate>` completes, whether it passed or failed
- **THEN** a row is appended to `.specloop/runs/<change>.jsonl` recording at least the
  gate, exit code, duration, change, task, tree and session

#### Scenario: The marker and the ledger are different stores
- **WHEN** the enforcement marker and the ledger row are both written for the same gate run
- **THEN** the marker is under `.git/` and never committed, and the ledger row is under
  `.specloop/runs/` and is committed with the change

#### Scenario: The ledger survives a squash-merge
- **WHEN** a change branch with several per-task ledger rows is squash-merged to `main`
- **THEN** every row is present on `main`, because the ledger is append-only and the
  squashed commit carries the file's final state

#### Scenario: Rows are keyed on durable identifiers
- **WHEN** a ledger row is written
- **THEN** it is keyed on `(change, task)` rather than a commit SHA, so it is not
  orphaned when branch commits stop being ancestors of `main`

#### Scenario: The merge is linked back to main history
- **WHEN** a change is merged
- **THEN** exactly one row is appended mapping the change to the resulting squash
  commit on `main`

#### Scenario: Every row kind carries a session
- **WHEN** a row of any kind (gate, review, task-start, taint, merge, halt,
  intervention) is appended
- **THEN** it carries `session: "agent"` or `session: "human"`, decided by the writer
  and not by the caller

### Requirement: The implementer emits a machine-readable final report
`tdd-implementer` SHALL end with a structured report so headless runs are queryable
without parsing prose. When the outcome is a halt, the report SHALL carry the cause
that was recorded in the ledger, and the ledger row SHALL be written before the report
is emitted — the report echoes the record; it is never the record.

#### Scenario: Report is structured
- **WHEN** an autonomous run finishes or halts
- **THEN** its final report contains `change`, `tasks_done`, `tasks_total`, `branch`,
  `gates`, `outcome` and `cause` as parseable fields

#### Scenario: A halt names its cause
- **WHEN** the run halts
- **THEN** `gates halt record <cause> --task <N.M>` has already appended the `halt`
  row, and the report's `cause` equals that row's cause

#### Scenario: A completed run has no cause
- **WHEN** the run ends `READY TO MERGE`
- **THEN** `cause` is `null`

### Requirement: An ungated commit is detected after the fact and taints the change

The `Stop` hook SHALL audit commits created since the last audited point by joining
each commit's tree to the durable ledger's green-`ci` rows for the change. A commit
whose tree has no matching green-`ci` row SHALL be reported loudly, naming the
offending commit, and SHALL record a taint on the change's durable ledger. This is
detection after the effect, not prevention, and SHALL NOT be presented as prevention.

The audit SHALL scope itself to the change branch's own commits: a commit already
reachable from the resolved merge target SHALL be exempt from tainting, because it
was gated by its own change before landing there. Merge-target ancestry SHALL be the
only exemption — authorship, committer identity, or timestamps SHALL NOT exempt a
commit. When no merge target can be resolved, the audit SHALL keep its current
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
