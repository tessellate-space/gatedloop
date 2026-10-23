## ADDED Requirements

### Requirement: Under the self policy a merged plan PR attests the plan

`gates approval attest <change> --merged <pr>` SHALL be legitimate only under
`approval.plan: self`. It SHALL write the approval keys from the forge's record of the
merge: the merger's login marked as a merge, the merge time, and an approval sha the
shim computes over the plan in the merge commit. Under `review` it SHALL refuse and
name `--pr`.

#### Scenario: A merged plan PR under self

- **WHEN** plan PR specloop PR 42 for `add-thing` was merged into the target by `alice` and the
  policy is `self`
- **THEN** `add-thing`'s approval reads `alice (merged #42)` at the PR's merge time,
  and `check-implement` accepts it

#### Scenario: The review policy

- **WHEN** the policy is `review` and `--merged 42` is given
- **THEN** the command refuses, writes nothing, and names `--pr`

### Requirement: A merged-PR attestation refuses what is not a merged plan

`--merged` SHALL refuse, writing nothing and naming the unmet condition, when the PR
is not merged, its base is not the merge target, its merge commit is not on the
target, the change's proposal is absent from the merge commit, or the forge client is
missing or unauthenticated.

#### Scenario: An open PR

- **WHEN** PR specloop PR 42 is still open
- **THEN** `--merged 42` refuses, naming the PR's state

#### Scenario: A PR into another branch

- **WHEN** PR specloop PR 42 was merged into a branch other than the target
- **THEN** `--merged 42` refuses, naming the base and the target

### Requirement: A handoff is refused unless the plan is approved on the target

`gates handoff <change>` SHALL run the same approval check `check-implement` runs,
against the merge target, and SHALL exit 1 with that check's reason when it fails. On
success it SHALL print a fixed payload naming the change, the target and its head, the
approval, the change's epic if any, its task counts, and the command a receiver re-runs
to verify. It SHALL NOT send, write or commit anything.

#### Scenario: Handing off an approved plan

- **WHEN** `add-thing` is merged to the target with a matching approval
- **THEN** `gates handoff add-thing --json` exits 0 and prints the payload, including
  `"verify": "gates approval check add-thing"`

#### Scenario: Handing off an unmerged plan

- **WHEN** `add-thing` exists only on a planner's branch
- **THEN** `gates handoff add-thing` exits 1 naming why the approval check failed,
  and prints no payload

### Requirement: Recording a merged plan PR attests it

`gates record-merged <sha>` SHALL, for a merged PR whose head is `plan/<change>` naming
an active change without an approval, attest it from the merge under the `self`
policy and commit the keys in its single local commit, never pushing. Under `review`,
or when the change is already approved, it SHALL skip with a message saying why.

#### Scenario: The record job after a plan PR merges

- **WHEN** `gates record-merged` runs on the squash of plan PR specloop PR 42 for `add-thing`
  under `self`
- **THEN** one local commit carries `add-thing`'s approval keys from the merge, and
  nothing is pushed

#### Scenario: Already approved

- **WHEN** `add-thing` already carries approval keys
- **THEN** `record-merged` skips it, saying it is already approved
