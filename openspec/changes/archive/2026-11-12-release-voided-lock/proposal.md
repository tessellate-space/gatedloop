# Proposal: release-voided-lock

## Why

The authored-test lock pins every path that any placement in a change ever held. When all of a path's placements are voided by a defect or a halt, the path is pinned to its content before the change, with no task attached. The pin exists so that a voided placement cannot carry an implementer's edit to a test past the lock.

That leaves no way out when the plan itself moves on. An adopter's task was tagged with a test oracle and `rewrites: <script>`. Its placement drew a `green` defect, because no oracle gate runs that script. The plan was then amended and re-approved:
- the task became `[oracle: none]`;
- its text has the implementer edit the script;
- the author re-handed off with `NO-TESTS` for the task.

The commit hook still refuses the edit: "no placement of it is in force — the implementer never edits an authored test". A `none` task can never place anything, and no record releases the path. The lane is held until a release carries a fix (#195).

Rejection test: this keeps a stated guarantee, that an authored test changes only through its author, while not blocking work that a human-approved plan has moved out of the authored set. It authors no artifact and names no stack command.

## What Changes

- **The release condition.** A path that is pinned only because all its placements are void is released when **every** task whose placement held it meets both of these:
  - (a) the latest accepted handoff declares it `NO-TESTS`;
  - (b) it is tagged `[oracle: none]` in the approved plan on the merge target, and in the evaluated tree.

  No current handoff may hold the path for any task.
- **What release means.** A released path is not checked by condition 1, so it may differ from its content before the change.
- **Same evaluator for every reader.** The rule lives in `_lock_problems`, so the commit hook, `gates tests check` and the merge's `tests check --ref` all apply it.
- **The human gate.** The tag is read from the merge target, which holds only approved plans. So release follows only from a re-approved plan, never from an edit the implementer makes, and nothing is released when that plan cannot be read.
- **The refusal message.** When a path is still pinned, the message says which condition is missing, so an operator can see the route.

## Capabilities

### Modified Capabilities

- `test-discipline`: the lock releases a voided path that the approved plan moved out of the authored set.

## Impact

- `bin/gates`: `_lock_problems` condition 1, and its refusal wording.
- `tests/test_tests_check_staged_output.py`: the pinned refusal text gains the missing-condition clause.
- A patch release (0.12.2).
