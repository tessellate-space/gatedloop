# Design

## Context

Approval today has two sources:
- **`--pr <n>`:** the first `APPROVED` review, under `review`;
- **`--local`:** the git identity and the time, under `self` only.

Both write the same three keys. `check-implement` then requires the keys on the target, with an `approved_sha` matching the plan's current content (proposal, design, specs; never `tasks.md` or `.openspec.yaml`).

`gates record-merged <sha>` already:
1. finds the PR a squash commit came from, through `gh api repos/{repo}/commits/{sha}/pulls`;
2. records a change PR's merge and archive;
3. skips a PR whose head names no active change. A `plan/<change>` head lands here today.

Only one local commit is made, and it is never pushed. The record job lands it through a follow-up PR.

## Decisions

### D1. The identity and time come from the forge

Read with `gh pr view <n> --json state,mergedAt,mergedBy,baseRefName,mergeCommit,headRefName`:

| Key | Value |
|---|---|
| `x-specloop-approved-by` | `<mergedBy.login> (merged #<n>)` |
| `x-specloop-approved-at` | `mergedAt` |
| `x-specloop-approved-sha` | `gates approval sha <change>` over the plan as it stands in `mergeCommit` |

The sha is computed with `git show <mergeCommit>:…`, never by the caller and never from the working tree. So the approval pins exactly what was merged, and a later edit on the target makes it stale, as with every other source.

### D2. When `--merged` refuses

`--merged` refuses, writing nothing and naming the unmet condition, when any of these holds:
1. the policy is `review`; the message names `--pr`;
2. the PR's `state` is not `MERGED`;
3. `baseRefName` is not the resolved merge target;
4. `mergeCommit` is not an ancestor of the target's head;
5. the change's `proposal.md` is absent from the tree of `mergeCommit`;
6. `gh` is missing or unauthenticated, which fails loud as every forge call does.

There is no check that the PR touched only planning paths. Merging is the approval act whatever else the PR carried, and `check-implement` still pins only the plan content.

### D3. `record-merged` attests a plan PR

In `cmd_record_merged`, after the PR is found, the order is:
1. **A change head:** `<change>` is a directory-backed active change. This is the merge and archive path, unchanged.
2. **A plan head, new:** `plan/<change>` where `<change>` is an active change on the target. If the policy is `self` and the change carries no approval keys, run D1/D2 with `--merged <n>`, then make the one local commit, `attest approval: <change> (merged #<n>)`, which is planning-grade. If the change already carries an approval, or the policy is `review`, skip with a message saying why.
3. **Anything else:** skip, unchanged.

It never pushes. The CI job's existing follow-up-PR step lands the commit, and when that follow-up merges, its `specloop/*` head names no change, so it is skipped as today.

**Local-squash mode** has no forge merge to read, because the merge is `gates merge`'s own. `--merged` doesn't apply there, and `--local` stays the path.

### D4. Ledger

The attest appends the same `approval` row `--local` and `--pr` write. Its `approved_by` carries the merge marker, so `gates stats` can tell the sources apart without a new field.

### D5. `gates handoff <change> [--json]`

1. Run `_approval_check(root, change)`, the function behind `check-implement`, against the resolved merge target. It checks that the plan is present there, carries approval keys, and that `approved_sha` matches the plan's current content there.
2. On failure, exit 1, printing the check's own reason and nothing else.
3. On success, exit 0, printing the payload:

```json
{"handoff": 1, "change": "add-thing", "schema": "spec-driven",
 "target": "main", "target_head": "<sha>",
 "approval": {"by": "...", "at": "...", "sha": "..."},
 "epic": "<x-specloop-epic or null>", "tasks": {"done": 0, "total": 7},
 "verify": "gates approval check add-thing"}
```

Without `--json`, the same fields are printed as plain lines. The payload carries no `depends_on`, because Specloop has no such concept. Ordering between changes is the adopter's queue, or an epic's (`epic-linkage`).

The command only reads, and never sends or writes. The receiver re-runs `verify` before acting, because a doorbell is not evidence.

### D6. The docs

In `docs/running-at-scale.md`, a new section "Planners and one orchestrator", headed "an example to adapt" like the rest of the document:
- **Roles.** Planners author and propose in their own worktrees and never dispatch. One orchestrator dispatches, merges and archives.
- **The flow.** A planner runs `/specloop:propose`, which opens the plan PR. A human merges it. Under `self` with pull-request mode, the record job attests from the merge (D3). The planner runs `gates handoff <change>` and sends the payload to the orchestrator with its own messaging tool. The orchestrator runs `verify` and queues the change.
- **Recovery.** The queue is derivable without any message: approved changes on the target that no lane holds.
- **The plan-check job.** It runs on PRs whose diff is planning-only. A planning-only diff is one where every path is under `openspec/` or is the rules-doc, the same set the shim calls planning-grade. The job runs `openspec validate --strict` per changed change, `gates validate`, and `gates approval sha` written to the job summary. Branch protection requires the job.

## Risks

- **A plan PR merged by someone other than its author** records the merger. Under `self` that is the intent: the merger is the one taking responsibility.
- **A force-merged PR whose head branch was deleted.** `headRefName` is still reported by the forge, so D3 works from the PR record, not from the branch.
