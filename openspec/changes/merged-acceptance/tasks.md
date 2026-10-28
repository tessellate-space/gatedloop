# Tasks

## 1. The merged-PR acceptance writer (D1, D2)

- [x] 1.1 Add `gates acceptance attest <change> --merged <pr>`, sharing the forge checks with `_merged_plan_approval`, writing the accept row with `accepted_by: "<login> (merged #<pr>)"`, the merge time and the merge commit's normalized tree, and doing nothing when an accept row for that tree exists. Verify with tests for a merged PR under self, the review policy, no policy, an open PR, a PR into another base, a PR from another head branch, a merge commit not on the target, and the already-accepted no-op, with the forge faked as the `approval attest --merged` tests fake it [oracle: unit]

## 2. record-merged (D3, D5)

- [x] 2.1 Make `gates record-merged`, under `approval.acceptance: self`, write the acceptance row before the merge row in the same local commit, skip it when an accept row for the tree exists, and discard the whole attempt when the writer refuses. Verify with tests for the self case (`gates stats --outcomes` reads `accepted`), an existing accept row, the review policy (no row written), no policy, and a forge refusal leaving nothing committed [oracle: unit]
- [ ] 2.2 Make `_record_merged_plan` re-attest a change whose `approved_sha` no longer matches the plan in the merge commit, and skip only a matching one. Verify with tests for a merged amendment re-attested (and `check-implement` passing), a matching approval skipped, and a change with no approval attested as now [oracle: unit]

## 3. The merge message and the docs (D4)

- [ ] 3.1 In pull-request mode under `acceptance: self` with no acceptance recorded, make `gates merge` step 4 say that the owner's merge in the forge is recorded as the acceptance by `gates record-merged`. Verify with a test of the step 4 output under self and under review [oracle: unit]
- [ ] 3.2 Document `--merged` beside `--pr` and `--local` in SETUP.md's acceptance writers, and what `record-merged` records under `acceptance: self` in SETUP.md and AUTOMATION.md. Verify that `scripts/release docs` reports no gap and `gates run ci` is green [oracle: none]

## Workflow follow-up

- Open the implementation PR with "Fixes #75".
