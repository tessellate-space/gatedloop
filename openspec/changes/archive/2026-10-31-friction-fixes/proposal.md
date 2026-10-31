## Why

Three friction reports from adopters are still open against 0.9.0. Each one makes a lane stop for a reason the plan or the hook should have handled:

- **#46, lettered task ids.** A plan amendment that adds a task as `1.2a` crashes `gates tests show`. The crash is the visible part. The task-line parser reads only `N.M` ids, so it never sees `1.2a`'s oracle tag, its brief line, its completion tick or its place in the approval digest. Today `gates validate` can only warn that the tag is ignored.
- **#44, syncing a lane branch.** The report's main case was fixed in 0.7.0. Since then, a merge into a change branch is not integration and passes the merge hook. One shape is still refused: a command that switches to the change branch and then merges, such as `git checkout my-change && git merge --ff-only origin/main`. The hook cannot tell which branch the merge lands on, so it fails closed and asks for a live-check marker that cannot exist for a sync.
- **#47, the authored-set review.** In 0.9.0, task-oracle narrowed the misread: a `NO-TESTS` on a task tagged `[oracle: none]` is now the plan's declaration. An untagged plan that splits "write the test" (1.1, `NO-TESTS`) from "implement it" (2.1, holding the test) still draws a false "missing oracle" finding. The reviewer judges 1.1's wording and never notices that 2.1 holds the test.

## What Changes

- One task-id grammar, `N.M` with any number of further numeric segments and an optional lowercase letter on the last one (`1.2a`), read by every `tasks.md` consumer:
  - oracle tags and their validation;
  - the test author's brief;
  - the completion walk;
  - the approval digest;
  - `gates tests show`.
- Tasks are listed in natural order wherever the shim lists them: `1.2`, `1.2a`, `1.2b`, `1.10`.
- `gates validate` stops warning about lettered ids, because they are now read. It still warns about a tag on an unnumbered task line.
- The merge hook judges a command that switches branches before merging by the branch the switch names. A switch to a named branch other than the integration target is not integration, so the merge passes. A switch it cannot resolve, such as a detached checkout, a path checkout or more than one candidate, stays gated, and the denial says to run the merge as its own command.
- `convention-review`'s authored-set mode judges oracle coverage over the whole authored set. A behaviour lacks an oracle only when no task of the change holds a test for it. A `NO-TESTS` on a task whose work is writing a test that another task holds is not a missing oracle.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-discipline`: task ids may carry a letter suffix and are read by every consumer; the authored-set review judges coverage across the set.
- `loop-enforcement`: the merge hook decides the scope of a switch-then-merge command from the branch the switch names.

## Impact

- `bin/gates`: the task-line and checked-task parsers, a shared task sort key used by `tests show`, `stats` usage and cost listings, the `validate` warning, and `discipline merge-scope` (a `--branch` argument).
- `hooks/_gate_match.py` and `hooks/gate-merge.sh`: report the switch target, pass it to `merge-scope`, and word the denial for an unresolved switch.
- `agents/convention-review.md`: the authored-set coverage rule.
- `SETUP.md`: the task-id grammar beside the oracle tag syntax. `AUTOMATION.md`: the switch-then-merge case in the merge hook's scope.
- Approval: a plan whose `tasks.md` holds a tag on a lettered line gets a new approval sha, because the digest now includes that line. 0.9.0's `gates validate` already warned about any such plan.
- No manifest key is added. Ships in 0.10.0.
