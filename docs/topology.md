# The topology in use

> **2026-10-23. An example to adapt.** This is how the maintainer runs gatedloop on
> their own projects as of this date: several sessions, three roles, git in between.
> Every command it names ships with gatedloop and is tested where it is implemented.
> The sessions, how they message each other and the CI job are not shipped; they are
> yours to set up. [`running-at-scale.md`](./running-at-scale.md) covers the same
> pieces in general form, and this page links to it instead of repeating it.

The short version:

| Role | Where it runs | How many | What it does |
|---|---|---|---|
| Planner | a local Claude Code session, in its own worktree | one per idea | writes the plan and opens the plan PR |
| Implementer | a Claude Code on the web session | one per change | runs the loop on the change branch and records READY |
| Orchestrator | a local Claude Code session, in the primary checkout | exactly one | queues approved changes and merges finished ones |

The planner and the orchestrator load their roles with `/gatedloop:planner` and
`/gatedloop:orchestrator`, and re-run them after a compaction.

A person approves each plan by merging its PR, and reviews each change before the
forge merges it. Everything else runs without a human turn.

## 1. Planning

One planner session per idea, each in its own worktree on a `plan/*` branch based on
`main`, so planners never share a checkout or an index with each other or with the
orchestrator:

```bash
git worktree add ../plans/<change> -b plan/<change> main
```

In that worktree, the planner runs `/gatedloop:propose`. `/opsx:propose` writes the
proposal, design, specs and tasks, and `/gatedloop:propose` commits them and opens
the plan PR. A planner never dispatches an implementer.

**Approval is the merge.** The project declares `approval: { plan: self }`, so a
person approves the plan by merging the plan PR, and the merge is attested:

- the record job (CI on every push to `main`) runs `gates record-merged <sha>`; it
  sees the `plan/<change>` head and attests the plan from the merge: the merger,
  marked `(merged #<n>)`, the merge time, and a sha over the plan;
- without that job, `gates approval attest <change> --merged <n>` on `main` does the
  same, and its output is committed.

[`running-at-scale.md`](./running-at-scale.md) §8 has the record job and the
plan-check job that validates planning-only PRs.

**The handoff.** Once the approval is on `main`, the planner runs:

```bash
gates handoff <change> --json
```

It exits 1 with the reason unless the plan is approved on the merge target and
unchanged since. On success it prints the payload, and the planner sends it to the
orchestrator session with Claude Code's own messaging. gatedloop sends nothing.

## 2. Implementing

One Claude Code on the web session per change, with the plugin enabled, working on
the change branch: branch name = change name, cut from `main`. Cutting it is
hook-gated, so it fails unless the plan is merged and attested.

The session runs `/gatedloop:tdd-apply <change>` the way the `tdd-implementer` agent
does: test authoring first, then per task red and green on the task's oracle gate (`unit`
by default, or the gate the plan's `[oracle: …]` tag names), `gates run ci` and convention
review, and one commit per task with its `[x]` and its ledger rows. It stops before the
merge. At the end it records readiness and commits it on its own:

```bash
gates ledger record-ready <change>
git add .gatedloop/runs/<change>.jsonl && git commit -m 'record ready'
git push
```

**Long gates run in the background.** A `ci` that takes longer than the host's
tool-call cap (600 seconds) can't finish in one foreground call. The shipped skill
says to run gates in the foreground; on the web, the session instead starts the gate
in the background with its output and exit code going to a file, and ends its turn:

```bash
gates run ci > ci.log 2>&1; echo "exit=$?" >> ci.log    # started as a background task
```

The completion notice wakes the session, and it reads the `exit=` line before doing
anything else. It never commits on a red `ci`, and the commit hook refuses the commit
anyway without a green marker for the staged tree. This is the one place the topology
departs from the shipped prompts; [`status.md`](./status.md) lists it as a sharp edge.

## 3. Merging

One local orchestrator session, in the primary checkout. It is the only session that
dispatches or merges.

**Queueing.** For each handoff it receives, it runs the payload's `verify` command,
`gates approval check <change>`, and queues the change only if that passes. It reads a
lane's state from the ledger committed on its branch, never from a message:

```bash
git fetch origin
git show origin/<change>:.gatedloop/runs/<change>.jsonl    # newest `ready` row, or a `halt` with its cause
```

[`running-at-scale.md`](./running-at-scale.md) §1 and §3 give the selection rule and
how to read the rows.

**Proving the head again.** Markers are kept per checkout, so a green `ci` earned in
a web session is not evidence on the orchestrator's machine. The orchestrator checks
the change branch out in a worktree of its own and runs `gates run ci` and
`gates run live-check` there. If it skips this, `gates merge` refuses at step 1 and
names the missing marker.

**The merge.** From that worktree, `gates merge <change>`, or the `merge-runner` agent
when an agent should handle a mechanical conflict. What it does depends on the
declared `integration.mode`:

- **`local-squash-merge`**: prove the head, squash onto `main`, an unscoped `ci` on
  the merged tree, the merge row, `confirm` where declared, the archive, and one push.
- **`pull-request`**: prove the head, push the branch, publish its markers as
  `gatedloop/live-check` and `gatedloop/ci` commit statuses, and open or update the PR
  with the acceptance brief as its body. A person reviews and merges it in the forge.
  The record job then runs `gates record-merged <sha>`, which writes the merge row and
  the archive in one commit that lands through a follow-up PR.

Branch protection requires `gatedloop/ci` from the CI provider, so a status posted
from a laptop doesn't satisfy it. [`running-at-scale.md`](./running-at-scale.md) §4
and §5 have the modes, the workflow and the protection settings. `gates stats
--outcomes --all` shows what merged, what halted and what is still running.

## 4. The doorbell

Messages between sessions are only a doorbell. The planner's message says "look at
this change"; it is not evidence that the change is approved, and the orchestrator
re-checks it with `gates approval check` before acting. An implementer's READY is a
committed `ready` row on its branch, not a message.

Git is the source of truth, so a lost message loses nothing. The orchestrator can
always rebuild its queue from git: the changes approved on `main` that no branch has
finished, and the branches whose committed ledger ends in a `ready` row. A late or
missing message delays a change and nothing else.
