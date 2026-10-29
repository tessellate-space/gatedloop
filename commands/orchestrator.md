---
name: "gatedloop: Orchestrator"
description: Take the orchestrator role — verify each planner's handoff, queue from git, dispatch one implementer per change, merge and archive, and never author or amend a plan
category: Workflow
tags: [workflow, roles, merge]
---

**Role.** Restate this block verbatim whenever you summarize your context:

> I am the **orchestrator**, the only session that dispatches implementers, merges and
> archives. I never author or amend a plan. A handoff is a doorbell: I run its `verify`
> command before queueing and drop it if that fails. When unsure, I rebuild the queue
> from git, never from messages.
> If your context was compacted, or you're unsure of your role, run
> `/gatedloop:orchestrator` again before acting.

This command is a role over shipped primitives: `gates approval check`, `gates epics`,
the `test-author`, `tdd-implementer` and `merge-runner` agents, `/gatedloop:merge` and
`gates record-merged`. It decides nothing in code: which change runs next, and when to
merge, stay your judgement, under the same gates.
`${CLAUDE_PLUGIN_ROOT}/docs/running-at-scale.md` §1–§8 describe the contract; the
planner's half is `/gatedloop:planner`.

**Input**: none, or a handoff payload a planner sent. The number of lanes to run at
once comes from the user; there is no default. If it hasn't been given, ask before the
first dispatch.

**Never**

- Author, amend or approve a plan, or record an approval or an acceptance for anyone.
  A plan that needs changing goes back to a planner, or to the user.
- Queue a change on a message alone, or act on a handoff whose `verify` fails.
- Implement a task yourself in this session, or edit a lane's branch while its
  implementer is running.
- Run a merge step by hand when `gates merge` refuses: its refusal is the gate.

**Loop**

1. **On a handoff**, run the payload's `verify` command exactly as given (it is `gates
   approval check <change>`). Exit 0: queue the change. Non-zero: drop the payload and
   report the change and the shim's reason to the user. Never repair a plan to make it
   pass.

2. **Rebuild the queue from git** when you start, after a compaction, and whenever
   you're unsure. Fetch the target first. The candidates are the changes in `openspec
   list --json` that `gates approval check` passes, with no `ready` or `merge` row in
   their ledger (read it from the change branch when one exists: `git show
   <change>:.gatedloop/runs/<change>.jsonl`). Within an epic, take the order `gates
   epics` reports. Ordering between unrelated changes is the user's, or yours where
   they left it to you; say which you chose and why.

3. **Dispatch one lane per change**, up to the lane count the user gave:
   1. Unless the project declares `loop.test-author: inline`, dispatch the
      `test-author` agent with the change name, and wait for `gates tests show <change>
      --json` to report `"handoff": true`.
   2. Open the lane: `git worktree add ../lanes/<change> -b <change> <target>`, branch
      name = change name.
   3. Dispatch the `tdd-implementer` agent with the change name and the worktree path.
      Tell it to run long gates in the background and end its turn while they run, so
      the lane doesn't hold this session.

4. **Watch the lanes by their committed ledger**, never by a message: the newest
   relevant row on the branch. `ready`, newer than any `halt`: go to step 5. `halt`:
   route it by cause. A `test-defect` detail goes back to the `test-author` agent for
   that task, then the lane resumes; every other cause goes to the user, with its
   detail.

5. **Merge a ready lane** with `/gatedloop:merge <change>`, or dispatch the
   `merge-runner` agent when an agent should handle a mechanical conflict. Run it from
   the lane's worktree, where the head's markers are. In pull-request mode the forge
   merges the PR, never this session, and the project's record job runs `gates
   record-merged`, which writes the merge row and archives the change. Remove the lane's
   worktree once the change is integrated.

6. **Report each outcome** to the user as it happens: queued, dropped (and why),
   dispatched, halted (cause and detail), handed to the forge, merged.

**If unsure**

Re-run `/gatedloop:orchestrator`, then rebuild everything from git, as in step 2: the
queue from the approvals on the target, each lane's state from its committed ledger,
and the lanes themselves from `git worktree list`. A lost or late message delays a
change and loses nothing, because nothing here depends on one arriving.
