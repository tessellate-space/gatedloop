## ADDED Requirements

### Requirement: The approval covers the saved snapshot

`gates plan save` SHALL record the snapshot's tree in the change's `.openspec.yaml` as
`x-gatedloop-preflight-tree`. When that key is present the approval sha SHALL cover its
value, and when it is absent the approval sha SHALL be unchanged from before this key
existed.

#### Scenario: A plan saved before approval

- **WHEN** the planner saves the store, commits the plan with the key, and the plan is
  approved
- **THEN** the recorded `approved_sha` covers the snapshot's tree

#### Scenario: The snapshot changed after approval

- **WHEN** the store is saved again with different content after approval, and the key
  is committed
- **THEN** `gates approval check` reports that the plan was edited after approval

#### Scenario: A plan without a snapshot

- **WHEN** a change's `.openspec.yaml` has no `x-gatedloop-preflight-tree`
- **THEN** its approval sha is the same as before this change

### Requirement: Saving writes the key without disturbing the change's metadata

`gates plan save` SHALL replace an existing preflight key line in place, else append it,
keeping every other line of `.openspec.yaml`. When `.openspec.yaml` is absent it SHALL
still save the snapshot and say that the approval will bind none.

#### Scenario: Other keys survive

- **WHEN** `.openspec.yaml` carries `schema` and approval keys and the store is saved twice
- **THEN** those lines are unchanged and the preflight key appears once

#### Scenario: No metadata file

- **WHEN** the change has no `.openspec.yaml`
- **THEN** `gates plan save` saves the snapshot, exits 0 and says no snapshot will be bound

### Requirement: Saving the store does not move the plan loop

The plan loop's digests (`plan_sha` on plan rows and in the snapshot message) SHALL NOT
include the preflight key, so a save never moves an open or green round.

#### Scenario: A save after the green round

- **WHEN** the planner runs `gates plan save` after the round it recorded green
- **THEN** `gates plan status` does not report the green round moved, and `gates plan
  record` in an open round does not refuse because of the save

### Requirement: The snapshot branch is deleted after archive

After a change is merged and archived, its `gatedloop/preflight/<change>` branch SHALL be
deleted locally and on the remote: by `gates merge` after its push in direct mode, and by
`gates record-merged` after its record commit succeeds in pull-request mode. A failed
deletion SHALL be printed with the command to run and SHALL NOT change the exit status.

#### Scenario: Recording a merged change in pull-request mode

- **WHEN** `gates record-merged` archives a change whose preflight branch exists on
  `origin`
- **THEN** the remote branch is deleted

#### Scenario: The record commit is refused

- **WHEN** `gates record-merged` archives a change but its record commit is refused
- **THEN** the record is discarded and the preflight branch is left in place

#### Scenario: Recording a merged plan

- **WHEN** `gates record-merged` records a merged `plan/<change>` PR
- **THEN** the preflight branch is left in place, because the change is not yet
  implemented
