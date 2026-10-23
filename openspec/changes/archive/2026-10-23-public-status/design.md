# Design

## Decisions

### D1. Public, not launched

The status paragraph is the first thing under the title:

| Element | What it says |
|---|---|
| Status | Built for the author's own projects, and works there. 0.x, so it changes without notice. Tested against OpenSpec 1.14.3. No support promised. |
| Who it's for | People already running unattended coding agents, who have been burned by "the agent said it ran the tests". |
| How to report | `/gatedloop:feedback`, or a GitHub issue. |
| History | Issue numbers before 0.7.0 were remapped when the issues moved from the private archive; PR references name the archive. |

There are no badges and no adoption claims, and no audience bigger than the evidence: one maintainer running it.

### D2. README order

The new order is:
1. the title;
2. the status paragraph;
3. one paragraph saying what gatedloop does, in plain words: gates are exit codes, hooks make them non-optional, a task is done exactly when it's committed, and a skipped gate taints the change;
4. the quickstart;
5. the existing sections (the boundary, the ladder, the components, the loop diagram), unchanged in substance.

Vocabulary like rung and oracle stays, below the quickstart, where it's defined.

### D3. `docs/status.md` from the field guide

Carried over:
- every sharp edge with its status label (shipped, shipped hole, planned);
- the roadmap section, retitled "What's next" and pointing at open issues instead of private plans.

Added:
- a short "Tested by" line stating one maintainer;
- an "Upstream coupling" section: OpenSpec's `--json` output, its generated `/opsx:*` commands, and the tested version, plus what breaks first when upstream changes.

Dropped:
- the collaborator-access step zero;
- the journeys-for-testers list;
- the trial's time-scope.

`docs/field-guide.md` keeps one line pointing at `docs/status.md`, for one release. `remove-specloop-forwarders` deletes it with the rest.

### D4. `docs/topology.md`

It is headed with its date and "an example to adapt", and has four parts:
1. **Planning.** One planner session per idea, each in its own worktree, using `/gatedloop:propose`. The plan PR is approved by merging, and the record job attests it (`planner-handoff`). Then `gates handoff` hands the change to the orchestrator.
2. **Implementing.** Implementer sessions in Claude Code on the web, one per change: the change branch, tdd-apply, the background-gate pattern, and READY recorded at the end.
3. **Merging.** One local orchestrator: `gates merge` in local mode, or in pull-request mode with `gatedloop/*` statuses, branch protection and `record-merged` follow-ups.
4. **The doorbell.** Messages between sessions are only a doorbell. Git is the truth, and a lost message loses nothing.

It uses only shipped commands. It links to `running-at-scale.md` for the parts already written there, and doesn't repeat them.

### D5. The feedback skill

It's a text change only: "tester" becomes "you" or "the reporter", and the trial wording goes. The `feedback-channel` requirements are unchanged.
