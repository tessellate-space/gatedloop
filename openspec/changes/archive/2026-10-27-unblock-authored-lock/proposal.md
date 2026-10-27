# Proposal

## Why

Under `loop.test-author: separate`, the authored-test lock can leave a finished, reviewed, accepted change unable to merge, with no route through it that respects the gate (issue #56; #49 is the same root). An adopter reports four such changes in one project. 0.6.0 needed a human `--no-verify` for every bookkeeping commit. 0.7.0 moved the lock into `gates merge` itself (`test-lock-remote-check`), so that override no longer helps. The lock is meant to stop an implementer editing its own oracle. Today it also blocks ledger rows, halts at finished tasks, and tests that are right but green on their first run.

## What Changes

- **A ledger-grade commit skips the authored-test lock.** Both commit hooks already classify a staged diff of only ledger paths as ledger-grade, and then run `gates tests check` anyway. A ledger row cannot change a test. The merge's own commits (step 1, proving the head; step 5, recording `confirm`) go through.
- **A halt at a completed task leaves its placement in force.** A halt means "wait" and says nothing about the tests. Today it voids the placement, so the task's committed holding-file removal and its `NO-TESTS` reason read as drift for the rest of the branch's life.
- **A test defect at a completed task reopens it.** The author re-hands off, and the task is placed again as usual. The red run recorded after the task's first placement stays the record, so no second red run is demanded against code that is already committed.
- **A truthful record for tests that are green on first run.** A new defect kind `green` replaces filing an untrue `setup` or `assertion` defect when placed tests pass before implementation. It sends the task back to the author, who either re-declares it (`CHARACTERIZATION`, or `NO-TESTS` with no tests) or rewrites the tests. It has its own cap. Only the author declares a task's kind, as today.
- **The attempt budget counts from the latest placement.** Red runs from a test-defect cycle no longer spend the budget before anything is implemented.
- **`gates attempt restart` treats a task's placed tests as clean.** It no longer counts them as partial work to discard while they match their placed content exactly.
- All of this is evaluated by the one shared lock evaluator, so `gates tests check --ref` (the merge's head proof) applies the same rules as the commit hooks. That is what lets the stuck changes merge.

None of these adds behaviour to an adopter who does not use authored tests. Each one narrows the lock to what it exists for, and none adds a manifest key.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-discipline`: the lock's conditions learn task completion (halts at completed tasks, reopening after a defect). A `green` defect kind and its cap. The "placed tests are already green" scenario records `green`. The lock-at-any-commit conditions follow.
- `gate-binding`: a ledger-grade commit is exempt from the authored-test lock in both commit hooks.
- `retry-budget`: failed attempts are counted from the later of the task's start and its latest placement. A restart accepts the task's placed tests at their placed content.

## Impact

- `bin/gates`: `_active_placements`, `_lock_problems`, task-completion reading from `tasks.md` in the evaluated tree, `TEST_DEFECT_KINDS` and the defect caps, `_attempt_state`, `_attempt_restart`, and the `gates stats` defect-kind counts.
- `hooks/gate-commit.sh` and `templates/git-hooks/pre-commit`: skip `tests check` on a ledger-grade verdict. Adopters who installed the git-layer hook re-run its install to pick this up, so the release notes say so.
- `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`, `agents/test-author.md`: the `green` kind and the author's answer to it, and the reopen of a completed task.
- `tests/`: one test per decision, using real git repositories, including a `tests check --ref` case shaped like the reported stuck change.
- Out of scope: per-task oracle tags in `tasks.md` (`task-oracle`, the follow-up change). That is the root fix for the author having to infer each task's kind from prose. This change only makes a wrong guess recoverable.
- Rejection test: it authors no artifact and names no stack command. It keeps a stated guarantee (an implementer cannot weaken its oracle) enforceable without blocking work that cannot violate it. Ships as a patch.
