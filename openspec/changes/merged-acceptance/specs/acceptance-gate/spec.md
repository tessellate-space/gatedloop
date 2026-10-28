## MODIFIED Requirements

### Requirement: An acceptance is a ledger row pinned to the tree it accepts

An acceptance SHALL be recorded as one row in the change's durable ledger with the
event name `acceptance`, a `verdict` of `accept` or `reject`, the ledger-normalized
tree of the change branch's head at the moment of recording (computed with the same
normalization the gate markers use, so the writer and the merge gate agree on "same
tree"), and an `accepted_by` identity. An acceptance written from a merged pull
request SHALL instead pin the ledger-normalized tree of that pull request's merge
commit, which is the tree the change's merge row records. The ledger row fields SHALL
gain `accepted_by` as an additive union field, absent on every other row kind. A
`reject` row SHALL additionally carry a cause of `weak-spec` or `missing-oracle` and a
non-empty detail. An acceptance row SHALL never be written into any file that the
accepted tree contains, because that would change the tree it pins.

#### Scenario: An accept row pins the head tree

- **WHEN** an acceptance is attested on a change branch whose head tree normalizes to T
- **THEN** one `acceptance` row with `verdict: "accept"` and `tree: T` is appended to
  `.gatedloop/runs/<change>.jsonl`, and no other file in the tree changes

#### Scenario: An accept row written from a merge pins the merge commit's tree

- **WHEN** an acceptance is attested from merged PR #42, whose merge commit's tree
  normalizes to M
- **THEN** the `accept` row's `tree` is M, the same tree as the change's merge row,
  and `gates stats --outcomes` reads the change as `accepted`

#### Scenario: A reject row is an escalation

- **WHEN** `gates acceptance reject <change> --cause weak-spec --detail "the spec
  says X, the product owner meant Y"` runs
- **THEN** one `acceptance` row with `verdict: "reject"`, `cause: "weak-spec"` and the
  detail is appended, pinned to the head tree

#### Scenario: A reject needs one of two causes

- **WHEN** `gates acceptance reject` is given a cause other than `weak-spec` or
  `missing-oracle`, or no detail
- **THEN** it exits non-zero, writes nothing, and explains that a rejection at
  acceptance means either the spec was wrong or no oracle caught it

#### Scenario: Acceptance rows are not gate rows

- **WHEN** `gates stats` aggregates a ledger holding `acceptance` rows
- **THEN** they contribute nothing to any gate's runs, failures or time
