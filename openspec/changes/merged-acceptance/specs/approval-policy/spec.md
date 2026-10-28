## ADDED Requirements

### Requirement: Under the self policy a merged implementation PR attests the acceptance

`gates acceptance attest <change> --merged <pr>` SHALL be legitimate only under `approval.acceptance: self`. It SHALL write one `accept` row from the forge's record of the merge: the merger's login marked `(merged #<pr>)`, the merge time, and the normalized tree of the PR's merge commit, which the shim computes. Under `review` it SHALL refuse and name `--pr`. When an `accept` row for that tree already exists, it SHALL write nothing and exit 0.

#### Scenario: A merged implementation PR under self

- **WHEN** PR #42 from branch `add-thing` was merged into the target by `alice` and `approval.acceptance` is `self`
- **THEN** one `accept` row is appended with `accepted_by: "alice (merged #42)"`, the PR's merge time, and the normalized tree of its merge commit

#### Scenario: The review policy

- **WHEN** `approval.acceptance` is `review` and `--merged 42` is given
- **THEN** the command refuses, writes nothing, and names `--pr`

#### Scenario: Already accepted

- **WHEN** an `accept` row for the merge commit's normalized tree is already in the ledger
- **THEN** the command writes nothing and exits 0

### Requirement: A merged-PR acceptance refuses what is not a merged PR of the change

`gates acceptance attest --merged` SHALL refuse, writing nothing and naming the unmet condition, when the PR is not merged, its base is not the merge target, its head branch is not the change's, its merge commit is not on the target, no acceptance policy is declared, or the forge client is missing or unauthenticated. It SHALL NOT accept a caller-supplied identity, time or tree.

#### Scenario: A PR from another branch

- **WHEN** PR #42's head branch is not `add-thing`
- **THEN** `gates acceptance attest add-thing --merged 42` refuses, naming the head branch

#### Scenario: An open PR

- **WHEN** PR #42 is still open
- **THEN** `--merged 42` refuses, naming the PR's state
