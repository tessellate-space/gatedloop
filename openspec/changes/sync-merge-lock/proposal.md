# Proposal: sync-merge-lock

## Why

Under the separate test author, a lane can't bring the merge target into its branch once a task has started but its tests aren't placed yet. The documented sync is `git merge --no-commit <target>`, then the commit gate, then `git commit`. The commit lock (`gates tests check`) counts every staged path outside `.gatedloop/` as implementing the current task. So it refuses the merge commit as "its authored tests are not placed" (#221).

Placing the tests first doesn't work either. The placed tests are red until the task is implemented, so the merge commit's gate can't go green, and the lane deadlocks. The sync is needed most right after a plan amendment, because an amended task line or tag has to reach the lane before the author can re-author against it. Today a halted lane that needs an amendment can only be retired and cut again from the target.

Rejection test: this makes a stated guarantee enforceable without blocking the loop's own documented route. The lock still refuses any implementation of an unplaced task, and a sync is let through only where the shim can prove the staged content is the target's. It authors no artifact and names no stack command.

## What Changes

- **A sync of the merge target is not implementation.** While a merge is in progress (`MERGE_HEAD` exists), its one incoming commit is reachable from the resolved merge target, and a staged path holds the sync's own result, the lock no longer counts that path as implementing the current task. The sync's own result is one of: the target's content for the path, git's automatic merge of the two sides, or, for the change's `tasks.md`, the target's file with the ticks `HEAD` carries. Anything else staged in the same commit still counts. A merge of any other ref counts exactly as today.
- **Placement refuses held tests that contradict the task's tag.** A sync can bring an amended tag, for example a new `rewrites:` clause or a move to `[oracle: none]`, after the task was handed off. `gates tests place <task>` now applies the handoff's tag checks for that task against the tag in the working tree. When they fail, it refuses and names the re-handoff route (`gates tests handoff <change> --task <N.M>`).
- **The loop says what to do after a sync that amends a pending task.** `skills/tdd-apply/SKILL.md`'s sync paragraph and `agents/tdd-implementer.md` cover three things. They say how to resolve the two conflicts an amendment sync usually raises: `tasks.md` (the target's file, with `HEAD`'s ticks) and the change's ledger (the branch's rows, then the target's new ones). They also say that a task whose line the sync changed, and that is not yet placed, goes back to the author before it is placed. At the top level, the loop re-dispatches the author. A lane halts `weak-spec` with a `re-author` detail, and `commands/orchestrator.md` routes that detail to the test author, the way it routes a `test-defect` detail.
- No new subcommand, flag, manifest key or ledger field. Nothing changes for a project that doesn't run the separate test author.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-discipline`: the lock tells a sync of the merge target apart from implementation, and placement holds a task's held tests to its current tag.

## Impact

- `bin/gates`:
  - the in-flight half of `_lock_problems`, through a new helper for a sync's own paths;
  - `_tests_place`, through the existing per-task tag checks of `_oracle_handoff_problems`.
- `skills/tdd-apply/SKILL.md` (the sync paragraph after 5h), `agents/tdd-implementer.md` (the sync rule in §5) and `commands/orchestrator.md` step 4.
- `SETUP.md` and `AUTOMATION.md`, where they describe the lock and placement. `README.md`'s "How tests flow" list, step 3.
- New tests on real repositories with a bare `origin`, through `tests/_lock_fixture.py`.
- Out of scope: #213. Its two parts (a human-only attempt grant, and a restart inside an open sync merge) are a separate guarantee. design.md D6 explains why.
