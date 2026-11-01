# acceptance-gate Specification

## Purpose
After the loop has satisfied its own oracles, a human accepts the behaviour — reading a
generated brief in scenario language and recording accept or reject against the exact
tree, through the same attested, never-self-reported mechanism plan approval uses — so
that "done" means accepted, not merged, wherever a project declares it.

## Requirements

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

### Requirement: The merge gate requires acceptance of the incoming tree when the policy is declared

`gates acceptance check <tree>` SHALL exit zero when the manifest declares no
acceptance policy (stating that acceptance is not required), or when the ledger's
latest `acceptance` row for the normalized `<tree>` has verdict `accept`. It SHALL exit
non-zero when the policy is declared and no `accept` row matches the tree, or the
latest row for that tree is a `reject`, naming the remedy (generate the brief, obtain
acceptance, attest). The merge gate SHALL call this check on the same tree its
live-check marker matched, after its taint check, so every piece of merge evidence
speaks about one tree. The check SHALL be an O(1)-class ledger read and SHALL NOT run
any gate.

#### Scenario: Policy undeclared, merge proceeds as today

- **WHEN** the manifest has no `approval.acceptance` and a merge is attempted with a
  green live-check and no taint
- **THEN** the acceptance check exits zero and the merge is allowed exactly as before
  this change

#### Scenario: Policy declared, no acceptance yet

- **WHEN** `approval.acceptance` is declared and the incoming tree has no `accept` row
- **THEN** the merge is denied and the message names `gates acceptance brief` and
  `gates acceptance attest` as the path to satisfy it

#### Scenario: Accepted, then edited

- **WHEN** an `accept` row pins tree T and the branch head then changes to a tree T′
- **THEN** a merge of T′ is denied — an acceptance cannot survive an edit

#### Scenario: Accepted, then rejected

- **WHEN** an `accept` row for tree T is followed by a `reject` row for T
- **THEN** the merge of T is denied and the message names the rejection's cause

#### Scenario: Rejected, then re-accepted

- **WHEN** a `reject` row for tree T is followed by a later `accept` row for T
- **THEN** the merge of T is allowed — the latest verdict for the tree wins

### Requirement: The acceptance brief is generated from the specs and the ledger, in scenario language

`gates acceptance brief <change> [--out <path>]` SHALL print (or write) a brief that
contains: one section per capability under the change's `specs/**/spec.md`, listing
every `#### Scenario:` title; for each scenario, `covered` when an acceptance scenario
with the same title (compared case-insensitively) exists in the files matched by the
manifest's optional `acceptance.match` glob, else `check by hand`; the change-level
verdicts recorded in the ledger for the current head tree — the latest `verify`,
`live-check`, `integration` and `ci` rows (gate, exit, timestamp) and the latest
`review` verdict — each marked `absent` when no row exists for that tree; a "check
these by hand" list of every uncovered scenario; and a footer stating that `covered`
means an acceptance artifact of that name exists and the declared gate ran green on
this tree, not that the artifact asserts the scenario's outcome. When `acceptance.match`
is undeclared, every scenario SHALL be `check by hand` and the brief SHALL say why. The
brief SHALL be a deterministic function of the change's spec files, the ledger and the
head tree, SHALL name no stack tool, and SHALL NOT be authored or amended by a model.
The brief is not hashed into the acceptance; the tree is what is accepted.

#### Scenario: A covered and an uncovered scenario

- **WHEN** the change's spec has scenarios "Login succeeds" and "Password reset
  emails expire", the files under `acceptance.match` contain a scenario titled "login
  succeeds", and a green `verify` row exists for the head tree
- **THEN** the brief lists "Login succeeds" as `covered`, "Password reset emails
  expire" as `check by hand`, shows the `verify` verdict, and the check-by-hand list
  contains exactly the second scenario

#### Scenario: No acceptance artifacts declared

- **WHEN** the manifest has no `acceptance.match`
- **THEN** every scenario is `check by hand` and the brief states that no acceptance
  artifact location is declared

#### Scenario: The brief is deterministic

- **WHEN** `gates acceptance brief <change>` runs twice with the same specs, ledger and
  head tree
- **THEN** the two outputs are byte-identical

#### Scenario: Verdicts are for this tree only

- **WHEN** the ledger holds a green `live-check` row for an earlier tree and none for
  the current head
- **THEN** the brief marks `live-check` as `absent` for this tree rather than showing
  the earlier verdict

#### Scenario: Writing the brief does not disturb the accepted tree

- **WHEN** the brief is written with `--out` to the documented default location under
  the ledger directory and committed
- **THEN** the head tree's normalized hash is unchanged, so an acceptance recorded
  before or after the write still matches

### Requirement: The manifest may declare where acceptance scenarios live

The manifest SHALL accept an optional top-level `acceptance` block with a `match` glob
naming the files that hold the project's acceptance scenarios. `gates validate` SHALL
reject an `acceptance` block without `match` or with any other key, naming the accepted
shape. The glob SHALL be the only thing the shim knows about acceptance artifacts; it
SHALL never assume a format beyond "a line whose text, after a scenario marker, equals
a spec scenario title", and the marker set SHALL be documented.

#### Scenario: A declared match glob

- **WHEN** the manifest declares `acceptance: { match: "features/**/*.feature" }`
- **THEN** `gates validate` accepts it and the brief's coverage rule reads those files

#### Scenario: A malformed block

- **WHEN** the manifest declares `acceptance: { dir: "features" }`
- **THEN** `gates validate` exits non-zero naming `match` as the required key

### Requirement: An acceptance is refused for a plan that is not the approved one

Every acceptance writer (`gates acceptance attest --local`, `--pr` and `--merged`) SHALL refuse to write an `accept` row for a change whose plan does not hash to its recorded `approved_sha`, as `gates merge` step 1 checks it. Under `approval.acceptance: self`, `gates record-merged` SHALL still record the merge row, write no `accept` row, and exit non-zero naming the reason.

#### Scenario: Local acceptance of an amended plan

- **WHEN** `gates acceptance attest <change> --local` runs and the change's plan was amended after approval without re-attesting
- **THEN** it exits 1 naming the stale approval, and no `accept` row is written

#### Scenario: A merged implementation PR of an amended plan

- **WHEN** `gates record-merged` records an implementation PR under `approval.acceptance: self` and the merged plan does not match its approval
- **THEN** the merge row is written, no `accept` row is written, and the command exits non-zero naming the re-approval route
