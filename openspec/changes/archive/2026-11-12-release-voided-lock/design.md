# Design: release-voided-lock

## Context

`_lock_problems` (bin/gates ~7240) condition 1 works in three steps:
1. It builds `expected[path] = (base blob, None)` for every path that any `tests-placed` row named.
2. It overwrites that with `(placed blob, task)` for the placements in force (from `_active_placements` and `_reopened_tasks`).
3. For a path with task `None`, a staged blob that differs from the base yields "no placement of it is in force".

Two other pieces matter:
- `state["no_behaviour"]` maps the tasks the latest handoff declares `NO-TESTS`, and `state["tests"]` maps the tasks the latest handoff holds tests for.
- `_oracles_in_tree(root, change, staged)` reads the evaluated tree's tags. A `none` tag parses to an oracle whose `gate` is `None`, and an untagged task maps to `None`, which means `unit`.

## Decisions

### D1. The release rule

While building `expected`, the shim records `placers[path]`: the set of tasks whose `tests-placed` rows named the path. After applying the placements in force, a path whose entry is still `(base, None)` is dropped from `expected` (released) when all of these hold:
- every task in `placers[path]` is in `state["no_behaviour"]`;
- every task in `placers[path]` is tagged `[oracle: none]` in the **approved plan**: the change's `tasks.md` on the merge target (`_resolve_merge_target`, then `_blob_at(target, ...)` parsed by `_task_lines_text`), where an oracle is not `None` and its `gate` is `None`;
- every task in `placers[path]` is also tagged `none` in the evaluated tree (`_oracles_in_tree`), so a branch that re-tags the task back to a gate keeps the pin;
- no task in `state["tests"]` holds the path.

The path is never released when the target does not resolve, when the change's `tasks.md` is absent on it, or when a placing task is absent from it. The rule reads the target directly and ignores `only`, so `gates tests check --task <N.M>`, the commit hook and `tests check --ref` all reach the same verdict for a path placed by another task. `oracles` is computed once, before condition 1, and reused by condition 3.

### D2. Why no new ledger row

- **Approval.** Release reads the tag from the merge target, which holds only plans that were merged, and therefore approved. An implementer's edit to the branch's `tasks.md` cannot produce it. Release does not depend on the drift check firing elsewhere: that check skips a target that does not resolve or a task it does not hold, and under `--task` it checks only that task.
- **The `--ref` reader** resolves the same target, so it reaches the same verdict.

### D3. The refusal names what is missing

When a path with task `None` differs, the message keeps its current opening. It then appends one clause naming the first unmet release condition, in this order:
- `task <N.M> is not declared NO-TESTS in the latest handoff`;
- `the approved plan on <target> could not be read` (target unresolved or the change absent there);
- `task <N.M> is not tagged [oracle: none] in the approved plan on <target>`;
- `task <N.M> is not tagged [oracle: none] in this tree`;
- `task <N.M>'s handoff holds it`.

Each clause is followed by `— the path is released only when the approved plan moves every task that placed it out of the authored set`. The `--ref` form gets the same clause. The existing `defect` guidance stays.
