# Design

## Decisions

### D1. Two prompts, no code

Both files are flat `commands/*.md` (`commands-flat-skills-nested`), naming no stack tool (`stack-agnostic-prompts`). Each has the same shape:
1. **Role**, five lines at most, written to be restated verbatim in a summary.
2. **Never**: the actions outside the role.
3. **Loop**: the steps, each naming the shipped command it uses.
4. **If unsure**: re-run this command; rebuild state from git.

### D2. The planner

**Never:** dispatch an implementer, run `tdd-apply`, merge, archive, or work in the orchestrator's checkout.

**Loop:**
1. Create a worktree, unless already in one.
2. Run `/gatedloop:propose`.
3. When the plan PR merges (under `self`, the record job attests it), run `gates handoff <change> --json`.
4. On exit 0, send the payload to the orchestrator session with the host's messaging tool. The session name is given by the user. On exit 1, report the reason to the user and send nothing.

### D3. The orchestrator

**Never:** author or amend a plan, or act on a handoff whose `verify` fails.

**Loop:**
1. On a handoff, run the payload's `verify` command, then queue.
2. Rebuild the queue from git when unsure. Candidates are approved changes on the target with no READY or merge row, and `gates epics` for ordering within an epic.
3. Dispatch one implementer per change, in its own worktree, with the shipped `tdd-implementer`. Tell it to run long gates in the background and end its turn.
4. On READY, merge with `/gatedloop:merge` or `merge-runner`. In pull-request mode, hand off to the forge, and archive through `record-merged`.
5. Report each outcome to the user.

**Concurrency.** The orchestrator's lane ceiling is the adopter's choice, stated by the user, and the commands carry no default number.

### D4. Compaction

The role block ends: "If your context was compacted, or you're unsure of your role, run `/gatedloop:<role>` again before acting." The commands can't detect compaction themselves, so this is the most a prompt can guarantee, and the docs say so.
