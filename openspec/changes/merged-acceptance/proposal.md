## Why

A solo project that declares `approval.acceptance: self` and integrates through pull requests has no way to record its acceptance (#75). The owner's merge of the implementation PR is the acceptance, but `gates acceptance attest` takes only `--pr`, which needs an APPROVED review the forge refuses on one's own PR, or `--local`, which is run by hand before the merge. After the forge merge the ledger holds a merge row and no accept row, nobody may write one by hand, and `gates stats --outcomes` counts every such change as not hands-off.

Plan approval already solved the same problem: `gates approval attest --merged <pr>` reads the forge's record of the merge, and `gates record-merged` writes it. Acceptance needs the same writer.

Working on this also showed that `record-merged` skips a merged plan amendment. It treats a change that names an approver as approved, without checking that `approved_sha` still matches the plan, so every amendment has needed a hand re-attest (#76 → #78).

## What Changes

- `gates acceptance attest <change> --merged <pr>`, legitimate only under `approval.acceptance: self`. It reads the forge's record of the merged implementation PR. `accepted_by` is the merger's login marked `(merged #<pr>)`, the time is the merge time, and the pinned tree is the ledger-normalized tree of the merge commit, which is the same tree the merge row records. It refuses what is not a merged PR of that change into the target, and writes nothing when an accept row for that tree already exists.
- `gates record-merged <sha>`, under `approval.acceptance: self`, writes that acceptance row in the same local commit as the merge row and the archive. A solo pull-request-mode project then ends with a complete ledger, and `--outcomes` sees the acceptance.
- `gates merge` in pull-request mode, under `acceptance: self` with no acceptance recorded, says that the owner's merge in the forge will be recorded as the acceptance, instead of reporting the acceptance as unsatisfied.
- `gates record-merged` re-attests a merged plan PR when the change's `approved_sha` no longer matches the plan in the merge commit, instead of skipping it as already approved.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `approval-policy`: a merged-PR acceptance writer under `acceptance: self`.
- `acceptance-gate`: an acceptance row may pin the merge commit's tree when it is written from a merge.
- `merge-step`: `record-merged` writes the acceptance row under `self`, and re-attests a stale plan approval.

## Impact

- `bin/gates`: the acceptance writer, `cmd_record_merged`, `_record_merged_plan`, and the pull-request-mode step 4 message.
- `SETUP.md` and `AUTOMATION.md`: the acceptance writers and what `record-merged` records.
- No manifest key is added, and no existing behaviour changes for a project without `approval.acceptance: self`.
- Ships in 0.9.0.
