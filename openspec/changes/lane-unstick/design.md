# Design: lane-unstick

## Context

`_task_completion` (unblock-authored-lock D2) returns, for each task, the index of the first commit that checked it, and for each ledger row, the index of the first commit that carried it. It builds both from one pass over `merge-base..ref` on the first-parent line, and seeds the pass with the merge-base. A lane that syncs by merging the target keeps its own first-parent line. Its ledger's rows only grow along that line, and union-resolved conflicts append the target's rows. The merge-base is a commit on the target, though, and its ledger is the target's copy.

`_attempt_restart` (retry-budget D4, unblock-authored-lock D7) filters `git status` twice. First it drops usage-only ledger appends (`_dirt_beyond_usage`). Then it drops the restarted task's own placements (`_restart_dirt`).

## Decisions

### D1. The walk starts on the lane's own line

The walk's first element is the first walked commit's first parent, not the merge-base. When the walk is empty (the ref is the merge-base, or the ref is on the target), it stays `[ref]` as today. In the usual case, a lane forked at the base and never synced, the first parent of the first walked commit *is* the base, so nothing changes. It changes only once the target has moved past the fork and the lane merged it in. The base is then a target commit, and the first walked commit's first parent is the lane's own commit before it.

Row indices stay positional. Only a `halt` or `test-defect` row's commit index is read, and those rows are written on the lane, so rows that a union merge appends from the target never move them.

*Rejected:* dropping the shrink refusal. It guards a real case, a rewritten lane ledger. Also rejected: comparing each commit with every parent. A sync merge's second parent is the target's line, which is the mistake being fixed.

### D2. Every placement a restart can resume is clean

`_restart_dirt` exempts the placed paths and holding-file removals of every task whose latest placement is either active or voided only by a `halt`. A placement voided by a `test-defect` is excluded, because those tests go back to the author. The halted task matters most here. Its own halt voids its placement (unblock-authored-lock D3), and a stalled halt is what a restart follows, so an exemption limited to active placements would refuse the very task being restarted. A path from either set that holds anything but its placed blob is `edited`, and the refusal names the path and its task.

A restart does not re-activate the placement. The fresh agent runs `gates tests place <task>` as usual. That command already accepts a path holding its placed blob once the holding file is gone ("already placed by an earlier, uncommitted run"), records a new `tests-placed` row, and needs a new red run. So the lock's record stays one placement, then red, then green. A batch placed together can restart either task, and a sibling's placed test is still protected from edits.

*Rejected:* letting a `restart` row reinstate the voided placement. It saves one `place` call, but it adds a second way for a placement to become active.

### D3. Bookkeeping rows are clean for a restart

A new predicate, used only by `_attempt_restart`, accepts an uncommitted ledger change that appends rows whose `gate` is `usage`, `restart` or `halt` to the `HEAD` copy. `_usage_only_append` and the `Stop` hook's boundary check keep their meaning. A restart after a restart, or after an uncommitted halt, goes through, and the rows reach the next commit with its work.

The dirty-tree refusal names the paths and says: commit the ledger (a ledger-grade commit), and set aside any other uncommitted work. It no longer says "discard the halted run's partial work".

## Risks

- D1 relies on the lane never rewriting its own first-parent line. A rewrite is what the refusal still catches.
- D3 lets a restart proceed with an uncommitted `halt` row. That is the row the dispatcher acts on, so it is consistent, and the next commit records it.
