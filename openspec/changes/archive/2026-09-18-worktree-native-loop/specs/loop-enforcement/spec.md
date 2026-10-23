# loop-enforcement Delta Specification

## ADDED Requirements

### Requirement: The gate marker store keys recorded evidence by tree

A gate's recorded green evidence SHALL be keyed by the tree it was recorded for, with
a bounded number of recent trees retained per gate, rather than a single slot that
each new run overwrites. A marker check SHALL pass when the requested tree is among
the recorded trees for that gate, so a lane alternating between trees (for example a
serialized merge lane) never invalidates its own still-valid evidence by recording a
newer one. The retained set SHALL be pruned oldest-first, and a tree evicted from it
SHALL simply require a re-run — eviction is never an error. Marker storage SHALL
remain per-worktree and outside version control.

#### Scenario: Two trees stay green in one lane

- **WHEN** a gate passes green on tree A, then passes green on tree B, and a guarded
  command then acts on tree A again
- **THEN** the marker check for tree A still passes — recording B did not overwrite A

#### Scenario: An evicted tree requires a re-run

- **WHEN** more trees have been recorded for a gate than the retention bound keeps,
  and a guarded command acts on the oldest, evicted tree
- **THEN** the marker check fails with the standard stale-marker message naming the
  re-run, and one green re-run restores it

#### Scenario: Markers do not leak across worktrees

- **WHEN** two worktrees of the same repository each record markers for the same gate
- **THEN** each worktree's checks read only its own store, and neither can satisfy or
  invalidate the other's

## MODIFIED Requirements

### Requirement: Implementation cannot begin before the plan is merged and approved

The apply flow SHALL refuse to start implementation for a change whose artifacts are
not present on the merge target, or whose artifacts do not carry a populated
approval. Under approval policy `review`, the merge target SHALL be the origin ref —
the approval is anchored to the forge's approving review, and a purely local ref
cannot evidence it. Under approval policy `self`, a local counterpart branch of the
merge target SHALL be accepted when it carries the change, with a loud advisory that
the plan is not yet on origin and should be pushed before the session ends.

#### Scenario: The plan has not been merged

- **WHEN** implementation is attempted for a change whose artifacts exist only on a
  local change branch, not on any counterpart of the merge target
- **THEN** it is refused, reporting that the plan must be reviewed and merged to the
  merge target first

#### Scenario: The plan is merged but unapproved

- **WHEN** implementation is attempted for a change present on the merge target whose
  `.openspec.yaml` has no populated `approved_by`
- **THEN** it is refused, because a merge proves the plan landed, not that a human
  agreed with it

#### Scenario: The plan is merged and approved

- **WHEN** the change's artifacts are present on the merge target and its
  `.openspec.yaml` carries `approved_by`, `approved_at`, and an `approved_sha`
  matching the current artifact content
- **THEN** implementation proceeds and the approver is recorded in the run's ledger
  rows

#### Scenario: The plan was edited after approval

- **WHEN** implementation is attempted for a change whose artifact content no longer
  matches its recorded `approved_sha`
- **THEN** it is refused, because the approved content and the current content have
  diverged

#### Scenario: An unattended run cannot approve its own plan

- **WHEN** a headless run authors a plan and attempts to proceed to implementation in
  the same session
- **THEN** it is refused at the approval check, so the human checkpoint survives full
  automation

#### Scenario: Solo policy accepts a merged-but-unpushed plan

- **WHEN** approval policy is `self`, the change is merged and locally attested on
  the local counterpart of the merge target, but not yet pushed to origin
- **THEN** implementation proceeds, and the check prints an advisory that the plan is
  not on origin and should be pushed before the session ends

#### Scenario: Review policy does not accept a local-only merge

- **WHEN** approval policy is `review` and the change is present only on the local
  counterpart of the merge target, not on the origin ref
- **THEN** implementation is refused — a forge-anchored approval cannot be evidenced
  by a local ref

### Requirement: The OpenSpec git discipline is enforced, not described

The ordering rules Specloop inherits from OpenSpec SHALL be enforced by hooks rather
than stated in prompt prose. The archive-follows-merge check SHALL accept a local
counterpart branch of the merge target that carries the change — the guarantee it
enforces is ordering, which a local merge proves — while printing a loud advisory
when the merge is not yet on origin, so a serialized merge lane needs no interim push
between each merge and its archive.

#### Scenario: Proposing from a change branch is refused

- **WHEN** a proposal artifact would be authored while a change branch is checked out
- **THEN** the hook denies it and reports that proposals run on `main`, where other
  in-flight changes and the authoritative specs are visible

#### Scenario: Archiving before merging is refused

- **WHEN** an archive is attempted for a change that has not yet been merged to the
  merge target on any counterpart, local or origin
- **THEN** the hook denies it, preserving merge-then-archive ordering

#### Scenario: Archiving a locally merged, unpushed change

- **WHEN** an archive is attempted for a change merged to the local counterpart of
  the merge target but not yet pushed to origin
- **THEN** the archive is allowed, with an advisory naming the unpushed merge and
  recommending a push before the session ends
