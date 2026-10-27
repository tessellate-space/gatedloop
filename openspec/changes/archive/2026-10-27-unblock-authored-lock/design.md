# Design

## Context

See proposal.md, Why. The lock is one evaluator, `_lock_problems`, with two callers. One is `gates tests check`, which reads the staged index and is called by both commit hooks after `discipline check-commit` passes. The other is `gates tests check --ref`, which reads a commit's tree and is called by `gates merge` step 1 and the forge status (`test-lock-remote-check` D1). Both read the change's ledger. `_active_placements` decides which placements are in force, and today any later `test-defect` or `halt` row for a task voids its placement, whatever state the task is in.

The adopter's stuck changes show three failure shapes, each matched by a decision below:

| Shape | Example in #56 | Decision |
|---|---|---|
| The lock runs on a ledger-only commit | merge steps 1 and 5 | D1 |
| A halt at a finished task voids its placement | 0.3 `NO-TESTS` "reason differs" | D2, D3 |
| Tests that are right but green on first run have no truthful record, and a finished task cannot be reopened | 3.1, 5.1; #49 case 1 | D4, D5 |

## Goals / Non-Goals

**Goals:** every stuck shape has a route through that passes the gate, with no `--no-verify`. The commit hooks and `--ref` give the same verdict on the same facts.

**Non-Goals:** the plan declaring each task's oracle (`task-oracle`, the follow-up). Any weakening of the lock for the task in flight. Any new manifest key.

## Decisions

### D1. The hooks skip the lock on a ledger-grade verdict

`hooks/gate-commit.sh` and `templates/git-hooks/pre-commit` run `gates tests check` only when `check-commit`'s verdict is not ledger-grade. `discipline check-commit` gains `--verdict-file <path>`: on success it writes exactly one token, `ledger`, `planning` or `marker`, to that path. Its exit status and printed text are unchanged, so other callers are unaffected. The hooks branch on the token, never by matching the human-readable line, which is free to change.

Alternative considered: make `tests check` itself pass on a ledger-only index. Rejected, because `tests check` is also run by hand and by `--ref`, where "the diff" has no meaning. The exemption belongs where the diff is classified.

`--ref` gains nothing from D1. A ledger commit never changes a test, so the head's tree is checked as it is. What fixes the merge's head proof is D2 to D5.

### D2. Completion is ordered by commits, not read from a single tree

A task is completed at row *i* when the first commit that checks the task in `openspec/changes/<change>/tasks.md` comes strictly before the first commit whose ledger carries row *i*. The evaluator computes both positions once per evaluation by walking the change branch's first-parent commits from its merge-base with the merge target up to the evaluated commit (`HEAD` for the index check, the ref for `--ref`). For each commit it reads two blobs: the ledger's row count and the set of checked task ids. Rows that are not yet committed, or that are present only in a lane's working tree (`_change_ledger_rows`), are placed after the last commit.

Alternative considered: the `[x]` in the evaluated tree alone. Rejected, because a halt row and the task's tick staged together would then read as a completed task, so a halt in flight could be carried past its void by ticking the task in the same commit. Alternative considered: a later task's `task-start` row as the completion marker. Rejected, because the last task of a change has none, and #49 case 2 is exactly a halt at the last task after `ready`.

Rows are append-only, so a row's index is stable across commits. A commit where the ledger shrinks is treated as a rewrite: the evaluator refuses, naming the commit, and never guesses an order.

### D3. A halt voids only an uncompleted task's placement

`_active_placements` takes the completion positions from D2. A `halt` row at a completed task is skipped, so the placement stays in force, together with its holding-file removal and its `NO-TESTS` or `CHARACTERIZATION` reason. A halt at the task in flight voids its placement as today, because the restart that follows begins at a clean boundary and places again.

### D4. A defect at a completed task reopens it

A `test-defect` row voids the placement whether or not the task is completed. The new tests have to go back through the author, so the placement must go. What changes is condition 3 for the next placement of a task that was completed before that defect. The red run it accepts is one recorded after the task's *first* placement, not after the latest one. Condition 1 checks the latest placement's content, so the lock still applies to the new tests in full.

For a reopened task declared `CHARACTERIZATION` at re-handoff, the characterization rule (green first verdict after placement) applies to the latest placement. A green run against code that is already committed carries less evidence than one against the base tree. The authored-set review judges the reason, and the risk is recorded below.

`gates tests place` already accepts a real path that holds an earlier placement's content, so it needs no change to place a reopened task.

### D5. A `green` defect kind

`TEST_DEFECT_KINDS` gains `green` with a cap of 1, and its halt cause past the cap is `oracle-conflict`. It records an observation (the placed tests passed before any implementation) rather than a claim that the tests are wrong. The author answers it in one of three ways: re-declare the task `CHARACTERIZATION` with a reason, re-declare it `NO-TESTS` with no tests, or rewrite the tests so they fail against the tree. If the re-placed tests are green again with no declaration, the second `green` is refused, and a human decides.

Alternative considered: a `gates tests redeclare` that the implementer runs. Rejected, because it breaks "only the author may declare a task free of behaviour" (test-discipline). The implementer would choose its own oracle, which is the thing the lock exists to prevent.

`gates stats` counts defects by kind from `TEST_DEFECT_KINDS`, so `green` appears in its counts without a separate change. Rows from before this change never carry `green`, and `test_defect_kind`'s fallback (unknown → `assertion`) is unchanged.

### D6. Attempts count from the latest placement

`_attempt_state` starts its window at the later of the task's latest `task-start` and its latest `tests-placed` row. `red_seen` resets at that point, so the first red run against the re-handed-off tests is the task's red run, and the runs from the defect cycle before it are not attempts.

### D7. A restart accepts the task's placed tests

`_attempt_restart` filters the porcelain status before judging it dirty. It drops each path that is one of the task's active placements, staged or in the worktree with exactly its placed blob, and each removal of that task's holding files. Anything else is still dirty. A placed path with any other content is named in the refusal.

## Risks / Trade-offs

- [D2 reads the branch's history on every lock evaluation] → it costs two blob reads per first-parent commit, once per evaluation, and branches run to tens of commits. A test pins the read count so that a later edit cannot make it quadratic.
- [A reopened `CHARACTERIZATION` task is green trivially against its own committed code] → the reason is recorded in the handoff, and the authored-set review judges it under `gatedloop.test-quality`, as any characterization claim is judged. `task-oracle` removes most of these cases by letting the plan declare the kind before any code exists.
- [Files the `unit` gate never runs, such as e2e step files, can only be declared `CHARACTERIZATION` for now] → stated in the test-author prompt as an interim rule, with `task-oracle` as the fix. It is not hidden behind a new kind.
- [Adopters who installed the git-layer hook keep the old copy] → the release notes say to re-run its install, and `gates doctor` already reports an installed hook that differs from the shipped template as `stale-copy`.

## Migration Plan

This ships as a patch. For an adopter's stuck change, after upgrading:

1. A halt at a completed task (0.3 in #56) clears with no action (D3).
2. A completed task committed without its red run (3.1, 5.1) gets `gates tests defect <task> --kind green --detail ...`, committed as a ledger-grade commit (D1). The author re-hands it off as `CHARACTERIZATION`, the implementer places it and runs `unit` green, and the task commits. `gates merge` then proves the head.

Rollback: revert the patch. No ledger row changes shape. A `green` defect row written under this version reads as `assertion` under an older shim, which is the existing fallback.

