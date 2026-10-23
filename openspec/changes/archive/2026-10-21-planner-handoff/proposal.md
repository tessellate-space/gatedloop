# Proposal

## Why

Issue #41: an adopter splits planning from orchestrating into separate sessions, with any number of planner sessions and one orchestrator, using plan PRs as the vehicle. A manual run worked end to end, with three gaps that are Specloop's:
- no way to count the merge as the approval;
- no checked handoff;
- no written contract.

**Merge-as-approval (item 2).** GitHub never lets an account approve its own pull request, which is why `approval.plan: self` and `gates approval attest --local` exist. For a solo maintainer the real act of approval is **merging** the plan PR, but Specloop doesn't count it. After every merge, the maintainer, or an agent, runs `attest --local` and pushes one more commit to the default branch. That approval's identity is only the local git config, and anyone can set it.

The forge already records the stronger fact: who merged the plan PR, and when.

## What Changes

- **`gates approval attest <change> --merged <pr>`**, legitimate only under `approval.plan: self`. It reads the PR through `gh`, refuses unless the PR meets all of D2's conditions, then writes the approval keys:
  - `x-specloop-approved-by`: the forge's `merged_by` login, marked as a merge;
  - `x-specloop-approved-at`: the PR's `merged_at`;
  - `x-specloop-approved-sha`: computed by the shim over the plan as it stands in the merge commit.

  Under `review` it refuses and names `--pr`, so an `APPROVED` review stays the only source of a review-policy approval.
- **The approval rides the record job.** `gates record-merged <sha>` handles a merged plan PR whose head is `plan/<change>`, which it skips today. Under `self`, for an active change with no approval yet, it attests `--merged` and commits the keys in its one local commit. In pull-request mode the CI job lands that commit through the follow-up PR already in place, so no human or agent commit is left in the approval path.
- **`--local` is unchanged** and remains the path for a project without a forge, or a plan not merged through a PR.
- **Docs.** SETUP's approval section gets the merge path, and `docs/running-at-scale.md` covers plan PRs.

- **`gates handoff <change> [--json]`** (item 3a). It runs the same approval check `check-implement` runs, against the merge target, and refuses unless the plan is approved there and unchanged since. On success it prints a fixed payload for a planner to send to the orchestrator, and the orchestrator re-runs the check named in it before queueing. The message is only a doorbell: git stays the source of truth, so a lost message loses nothing.
- **The planner/orchestrator contract, as docs** (item 3, the contract part). `docs/running-at-scale.md` gains a section:
  - planners author and propose only, each in its own worktree, and never dispatch;
  - exactly one orchestrator dispatches;
  - the queue is derivable from approved, unblocked changes;
  - the handoff payload is what a planner's agent sends with its own messaging tool.
- **The plan-check job, as a docs example** (item 1). It runs on planning-only PRs: `openspec validate --strict` for each changed change, `gates validate`, and `gates approval sha` printed to the job summary, so the content an approval will pin is visible before merge. Branch protection requires the job's own check. Following the specloop PR 94 decision, nothing is shipped as a CI template.

Not in this change:
- **`handoff --to <session>` sending the message.** The shim can't reach an agent's messaging tool; the agent sends the payload.
- **An `orchestrator.session-name` manifest key.** Session naming is the adopter's orchestration.
- **#41's report of a planning-only commit refused for a stale `ci` marker.** Planning-only commits are allowed without `ci`, so a refusal that names a stale marker means the staged diff held a non-planning path. It needs the refused commit's staged paths before it can be treated as a defect.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `approval-policy`:
  - a merged plan PR is a legitimate attestation source under `self`;
  - a handoff is refused unless the plan is approved on the target.

## Impact

- `bin/gates`:
  - `cmd_approval_attest` gains `--merged`;
  - `cmd_record_merged` gains the `plan/<change>` branch;
  - one helper reads the PR fields through `gh`;
  - a new `handoff` command.
- `SETUP.md`, README's command list, and `docs/running-at-scale.md`: the contract and the plan-check job.
- Tests use the fake-`gh` fixture `tests/_forge_fixture.py`.
