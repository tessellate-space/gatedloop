## ADDED Requirements

### Requirement: A sync of the merge target is not implementation

While a merge is in progress whose single incoming commit is reachable from the resolved merge target, `gates tests check` SHALL NOT count a staged path as implementing the current task when its staged state equals the incoming commit's, equals git's automatic merge of `HEAD` and the incoming commit, or, for the change's `tasks.md`, equals the incoming commit's file with the tasks checked at `HEAD` checked. Every other staged path outside the state directory SHALL count as implementing, as before. A merge of more than one commit, of a commit the merge target does not contain, or with no resolvable merge target SHALL get no exemption. The conditions over the tree (placed and held content, red runs, tag drift) SHALL apply to the merge commit unchanged, and `gates tests check --ref` SHALL be unaffected.

#### Scenario: A sync at a task boundary with the next task unplaced

- **WHEN** the current task is started and its tests are not placed, the lane runs `git merge --no-commit` of the merge target, and only the merge's own result is staged
- **THEN** `gates tests check` passes, and the merge commit is allowed once its commit gate is green

#### Scenario: Both sides changed tasks.md

- **WHEN** the branch has ticked a completed task, the target amended a later task's line, and the conflict is resolved as the target's file with the branch's ticks
- **THEN** the change's `tasks.md` does not count as implementing

#### Scenario: Both sides changed a file without conflict

- **WHEN** the branch and the target changed different lines of the same project file, and the staged file is git's automatic merge
- **THEN** that file does not count as implementing

#### Scenario: Implementation staged inside the sync

- **WHEN** the merge is in progress and a project file is staged whose content equals neither side nor their automatic merge
- **THEN** `gates tests check` refuses with "its authored tests are not placed", as before

#### Scenario: A conflict resolved by hand

- **WHEN** a project file conflicted and its staged resolution equals neither side nor the automatic merge
- **THEN** it counts as implementing, and the refusal is unchanged

#### Scenario: The target dropped a task the branch completed

- **WHEN** the branch has ticked two tasks, the target's amended `tasks.md` no longer has one of them, and the conflict is resolved as the target's file with the branch's remaining ticks
- **THEN** the change's `tasks.md` counts as implementing, and the refusal is unchanged

#### Scenario: A merge of a ref the target does not contain

- **WHEN** the in-progress merge's incoming commit is not reachable from the merge target
- **THEN** every staged path outside the state directory counts as implementing, as before

#### Scenario: An octopus merge

- **WHEN** the in-progress merge has more than one incoming commit, even when each is reachable from the merge target
- **THEN** every staged path outside the state directory counts as implementing, as before

#### Scenario: No resolvable merge target

- **WHEN** a merge is in progress and the merge target cannot be resolved
- **THEN** every staged path outside the state directory counts as implementing, as before

### Requirement: Placement holds a task's held tests to its current tag

`gates tests place <task>` SHALL refuse, before moving or deleting any file and before writing any ledger row, when the task's tag in the working tree's `tasks.md` contradicts the latest handoff for that task: tests held for a `none` task, a `NO-TESTS` reason for a task tagged with a gate, a missing or unwanted `CHARACTERIZATION` declaration, or a declared `rewrites:` path with no full file held for the task. The refusal SHALL name each problem and the route: re-dispatch the author for the task, then `gates tests handoff <change> --task <N.M>`. An untagged task SHALL NOT be refused by this check, and a consistent handoff SHALL place as before.

#### Scenario: A sync brought a new rewrites clause

- **WHEN** a task was handed off, a sync then brought its tag with a `rewrites:` path the handoff holds no full file for, and the task is placed
- **THEN** placement refuses, names the path and the `--task` re-handoff, and moves nothing

#### Scenario: A sync moved a task to none

- **WHEN** a task was handed off with tests, and a sync brought its tag as `[oracle: none]`
- **THEN** placement refuses, naming the contradiction and the re-handoff

#### Scenario: A sync moved a NO-TESTS task to a gate

- **WHEN** a task was handed off with a `NO-TESTS` reason, and a sync brought its tag as `[oracle: unit]`
- **THEN** placement refuses, the `NO-TESTS` file stays in the holding area, and no `tests-placed` row is written

#### Scenario: A sync moved a task to characterization

- **WHEN** a task was handed off with tests and no `CHARACTERIZATION` declaration, and a sync brought its tag as a `characterization` tag
- **THEN** placement refuses, naming the contradiction and the re-handoff

#### Scenario: A sync moved a task away from characterization

- **WHEN** a task was handed off with tests and a `CHARACTERIZATION` declaration, and a sync brought its tag as a plain gate tag
- **THEN** placement refuses, naming the contradiction and the re-handoff

#### Scenario: The handoff matches the tag

- **WHEN** a task's held tests agree with its tag
- **THEN** placement succeeds as before

#### Scenario: An untagged task

- **WHEN** a task's line carries no oracle tag, under any `loop.task-oracle` mode
- **THEN** this check does not refuse it, and placement proceeds as before

### Requirement: The loop sends a task a sync amended back to its author

The tdd-apply skill and the implementer SHALL say, for the sync route, that a `tasks.md` conflict resolves to the target's file with `HEAD`'s ticks and a ledger conflict to the branch's rows followed by the target's new rows. They SHALL say that each unplaced task whose line the sync changed goes back to the author before it is placed: the top-level loop re-dispatches the author, and a lane halts `weak-spec` with a detail beginning `re-author`. A placement refused on the task's tag SHALL take the same route, the lane's detail naming the refusal's first problem. A sync whose incoming `tasks.md` no longer has a task ticked at `HEAD` SHALL be aborted before any resolution with `git merge --abort` and halt `weak-spec` with detail `sync dropped completed task <N.M>[, <N.M>]`, which goes to a human. The orchestrator SHALL route a halt whose detail begins `re-author` to the test author for the named tasks, then resume the lane.

#### Scenario: A lane syncs an amended plan

- **WHEN** a lane's sync commit changes the line of task 2.2, which is not placed
- **THEN** the lane halts `weak-spec` with detail `re-author 2.2: the sync amended them`, and the orchestrator, in the lane's worktree, dispatches the test author for 2.2, runs the authored-set review over it and commits the re-handoff before resuming the lane

#### Scenario: Placement refuses on a synced tag

- **WHEN** a lane's `gates tests place 2.2` refuses because the synced tag contradicts the handoff
- **THEN** the lane halts `weak-spec` with a detail beginning `re-author 2.2:` and naming the problem, and the orchestrator routes it to the test author

#### Scenario: A sync drops a completed task

- **WHEN** a lane runs `git merge --no-commit` of the target, and `MERGE_HEAD`'s `tasks.md` no longer has task 1.1, which `HEAD` has ticked
- **THEN** before resolving anything, the lane runs `git merge --abort` and halts `weak-spec` with detail `sync dropped completed task 1.1`, and the orchestrator reports it to a human rather than resuming the lane
