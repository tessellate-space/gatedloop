## Context

The acceptance gate records an acceptance as a ledger row pinned to a tree (acceptance-gate D2). It has two writers: `--pr`, read from the PR's APPROVED review, and `--local`, under `self`, run by hand on the change branch before the merge. Plan approval has a third writer, `--merged`, which reads the forge's record of a merged plan PR, and `record-merged` uses it so a solo pull-request-mode project never attests a plan by hand.

A solo pull-request-mode project under `acceptance: self` has no matching writer. GitHub refuses a review on one's own PR, so `--pr` never applies. `--local` would have to be run on the branch before the owner merges, which is the same step done twice. After the merge, `gates stats --outcomes` (`outcomes_from_rows`) finds a merge row and no `accept` row for the merge tree, so it classifies the change as `merged` with "missing acceptance".

`record-merged` also writes the plan approval only when the change has none (`_record_merged_plan` checks `approved_by`). A merged amendment to an approved plan therefore leaves a stale `approved_sha`, and the change fails `check-implement` until someone re-attests by hand.

## Goals / Non-Goals

**Goals:**

- A solo pull-request-mode project under `acceptance: self` ends a merged change with a complete ledger: merge row, accept row, archive, in one commit.
- The accept row joins the merge row by tree, so `--outcomes` reads `accepted` with no change to the outcomes code.
- A merged plan amendment is re-attested by `record-merged`.

**Non-Goals:**

- Changing what `acceptance: review` requires. A second party still accepts through a review.
- Enabling forge auto-merge without a recorded acceptance. The owner's merge is the human act; an auto-merge is not.
- A new manifest key.

## Decisions

### D1. `--merged` mirrors plan approval's writer

`gates acceptance attest <change> --merged <pr>` reads `state, mergedAt, mergedBy, baseRefName, headRefName, mergeCommit` through the same forge call `_merged_plan_approval` uses. It refuses, writing nothing and naming the unmet condition, when:

- the PR is not MERGED;
- its base is not the merge target;
- its head branch is not `<change>`;
- its merge commit is not on the target;
- the forge client is missing or unauthenticated;
- the policy is not `self` (`review` names `--pr`, and none names `approval.acceptance`).

`accepted_by` is `<login> (merged #<pr>)`, the same marker plan approval uses, so the ledger tells a merge-recorded acceptance apart from `--local`. The timestamp is `mergedAt`. A shared reader beside `_merged_plan_approval` holds the forge checks; the two differ only in the head-branch check (`plan/<change>` against `<change>`) and in what they compute from the merge commit.

### D2. The pinned tree is the merge commit's

An accept row written from a merge pins the ledger-normalized tree of the PR's merge commit, not the change branch's head. Three reasons:

- After a forge merge the change branch may be deleted locally and remotely, while the merge commit is on the target.
- The merge row records `_normalize_tree(_commit_tree(sha))` for the same commit, so `outcomes_from_rows` joins them as is.
- It is the tree that shipped, which is what the owner accepted by merging it.

For a squash of an up-to-date branch the two trees are the same. They differ only when the target moved and the forge merged anyway; then the merge commit's tree is the honest pin.

### D3. `record-merged` writes the row first, in the same commit

Under `acceptance: self`, `cmd_record_merged` calls the D1 writer before `ledger record-merge`, so the ledger reads accept, then merge, then the archive commit holds both. If an `accept` row for that tree already exists (an auto-merge enabled after `--local`, or a re-run), it writes nothing. A refusal from the writer, such as the forge being unreachable, discards the attempt the way an archive failure already does, so `record-merged` never commits a merge without its acceptance under `self`.

### D4. `gates merge` says what will record the acceptance

In pull-request mode, step 4 reports "auto-merge not enabled — the declared acceptance is not satisfied" whenever no row exists. Under `acceptance: self` that is misleading, because the owner's merge will satisfy it. The message becomes: merge the pull request in the forge, and `gates record-merged` records that merge as the acceptance. Auto-merge stays off without a recorded acceptance (non-goal).

### D5. A stale plan approval is re-attested from its merge

`_record_merged_plan` skips only when the recorded `approved_sha` equals `_approval_sha_ref` at the merge commit. A stale sha is re-attested through `cmd_approval_attest_merged`, which already rewrites all three keys and records the approval row. The skip message names the approver, as now.

## Risks / Trade-offs

- **An auto-merge is recorded as a person's acceptance.** `mergedBy` on an auto-merged PR is whoever enabled it. Under D3 that only happens when an acceptance row already exists, because `gates merge` enables auto-merge only then, so nothing new is written. → Covered by the "already accepted" no-op.
- **The forge's record is trusted.** Same trust as `approval attest --merged` and `--pr`. → No new exposure.

## Migration Plan

Additive. A project without `approval.acceptance: self` sees no change in `record-merged`'s acceptance step. Changes already merged without an accept row can be backfilled with `gates acceptance attest <change> --merged <pr>` only while the change is active; archived changes stay as they are. The D5 fix applies to every `approval.plan: self` project and only removes a hand step.
