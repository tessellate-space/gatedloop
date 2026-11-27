# Design: approved-tests

## Context

plan-preflight D7 keeps the loop's held tests in `.gatedloop/out/preflight/<change>/`. `gates plan save` snapshots that store to the branch `gatedloop/preflight/<change>` using plumbing only. The store's layout mirrors the holding area (`authored/<N.M>/<path>.authored`, `NO-TESTS`, `CHARACTERIZATION`), plus `digests.json`, which holds each task's brief digest as of the last clean `--dry-run`.

The approval sha covers `proposal.md`, `design.md`, `specs/**.md` and the oracle tags of `tasks.md`. It does not cover `.openspec.yaml`.

## Decisions

### D0. Sequencing

This change is implemented on a base that already contains `batch-approval-check`. Task 1.1 changes that change's batched reader (its D2, `ls-tree` + `cat-file --batch`), which must stay byte-identical to `_approval_sha_ref`.

### D1. The approval binds the snapshot's tree; the plan loop's digests do not

**Writing the key.**
- After `update-ref` succeeds, `gates plan save` writes `x-gatedloop-preflight-tree: <tree sha>` into `openspec/changes/<change>/.openspec.yaml`.
- An existing line for the key is replaced where it is; otherwise the line is appended. Every other line is kept as written.
- When `.openspec.yaml` is absent, the snapshot is still saved. No key is written, and it prints that the approval will bind no snapshot. That matches today's exit 0.
- This is the one working-tree edit `plan save` makes.
- The bound value is the tree, not the commit, because the tree is content-addressed: a re-save of identical content writes the same value.

**Hashing it for approval.** The approval digest mixes the key in. This applies to:
- `_approval_sha_ref`;
- the batched reader;
- `_approval_sha_worktree` when called for approval (`approval record --local`, `plan status`'s approval line).

When the key is present, after the oracle-tag update and in the style of `_update_with_oracle_tags`, it adds `h.update(b".openspec.yaml#x-gatedloop-preflight-tree\n" + value.encode() + b"\n")`, where `value` is the key's value stripped of whitespace. When the key is absent, nothing is added, so every recorded approval keeps its sha.

**Not hashing it for the plan loop.** `_approval_sha_worktree` gains a keyword `preflight: bool = True`. Two callers pass `preflight=False`:
- `_plan_digests` (the `plan_sha` on `plan-round`/`plan-review` rows, `plan record`'s "the plan changed since round N opened" refusal, and `green_round_moved`);
- `_plan_save`'s snapshot message.

Saving the store therefore never moves a round or marks a green round moved.

**Approving the bound tree.** The tree is the whole store, including `digests.json` and the reports. A re-save after approval writes a new value, and the approval check then reports an edit after approval, as for any plan edit.

### D2. `gates tests adopt <change>`

**Refusals.** It refuses with exit 1 and writes nothing when:
- it is not run on the change's branch;
- `gates approval check <change>` fails;
- a `tests-handoff` row for the change already exists in the ledger. Adopting is a pre-handoff step, and a resumed loop that has already handed off skips it.
- no snapshot with the bound tree is found.

**Finding the snapshot.** It searches the history of `refs/heads/gatedloop/preflight/<change>` and of `refs/remotes/origin/gatedloop/preflight/<change>` for a commit whose tree is the bound one. It fetches `origin gatedloop/preflight/<change>` once, only when neither history carries that tree. The remote is `origin`, as `plan save` and `plan restore` already print it.

**Nothing to adopt.** When the approved `.openspec.yaml` has no key, it prints "nothing to adopt" and exits 0.

**Staleness.** `_preflight_reuse`'s rule moves into a pure function, `_preflight_stale(current, saved, held) -> (stale, kept)`:
- `current` and `saved` map task ids to digests;
- `held` maps task ids to the paths they hold;
- a task is stale when its digest moved or is absent, or when it holds a path a stale task holds.

`gates tests brief --preflight` keeps its output by calling `_preflight_stale` with the store's `digests.json` and paths. `adopt` calls it with:
- `current` from `_preflight_task_digests`;
- `saved` from the snapshot's `digests.json`;
- `held` from the snapshot's `authored/` paths.

**Three categories.** The categories range over every task in `tasks.md`. A task with no saved digest in the snapshot is stale, and so is a kept task whose snapshot has no `authored/<N.M>/` files. For each task:
- **present**: the task's directory already exists in `.gatedloop/authored/<change>/`. It is left untouched, never dispatched and not recorded.
- **adopted**: kept and not present. Every file of the snapshot's `authored/<N.M>/` is written there, including `NO-TESTS` and `CHARACTERIZATION`.
- **stale**: everything else. It goes to the author.

It prints the three lists.

**`ADOPTED.json`.** It writes `.gatedloop/authored/<change>/ADOPTED.json` as `{tree, tasks}`. A re-run before the handoff merges the new adopted tasks into an existing file with the same tree. It refuses when the existing file names another tree. It exits 0 whenever it does not refuse.

### D3. The handoff records the adoption

Only a full (no `--task`), non-dry handoff that succeeds reads `ADOPTED.json`:
- A listed task counts as adopted only when its directory's file set equals the snapshot's `authored/<N.M>/` file set and every blob matches (read with `git cat-file` from the commit that carries the tree). A deleted or added file disqualifies it.
- It records `preflight_tree` and `adopted` on its `tests-handoff` row. `adopted` lists the tasks whose files all still match.
- It deletes `ADOPTED.json` after appending the row.

`--task` and `--dry-run` handoffs neither read nor delete the file. An `--inline` handoff is a full handoff and reads it.

The lock and the red-run rules are unchanged: adopted tests are placed and run red like any others. The two fields are additions, so the row version stays.

### D4. The loop adopts first

In `skills/tdd-apply/SKILL.md` §4b (which runs on the change's branch):
- When `gates tests show <change> --json` reports no handoff, the loop runs `gates tests adopt <change>` before step 1.
- With no stale task, it does not dispatch the author.
- With stale tasks, it dispatches the author naming only those tasks.
- **present** tasks are never dispatched.

- Under `loop.test-author: inline` (§5-inline), the loop adopts the same way and then authors only the stale tasks itself before its `--inline` handoff.

The authored-set review covers the stale tasks just authored plus the **present** tasks (written by an earlier, interrupted run that never handed off, so never reviewed). Adopted tasks were reviewed in the plan loop before approval, and their brief digests show their inputs have not moved since. When both sets are empty, the review is skipped. The handoff and the authoring commit always follow, run by the loop itself as today.

`commands/orchestrator.md` step 3.1 dispatches the test author before the lane exists, so adopt (which runs only on the change's branch) cannot run there. When the approved `.openspec.yaml` carries `x-gatedloop-preflight-tree`, the orchestrator skips its step 3.1 author dispatch and opens the lane. The implementer's §4b then adopts, dispatches the author for stale tasks, hands off and commits. A plan without the key keeps today's step 3.1.

`agents/test-author.md` gains this rule: when the dispatcher names tasks, author only those, and leave every other task's directory as it is.

`commands/propose.md` and `commands/planner.md` gain a step after the plan loop's final `gates plan save`: stage `openspec/changes/<change>/.openspec.yaml` with the plan and commit it, so that the approval binds the tree.

### D5. Deleting the branch after archive

**Direct mode.** After `_merge_publish` succeeds, `gates merge`:
- deletes `refs/heads/gatedloop/preflight/<change>` when it exists;
- when `_split_target` gives a remote, checks `git ls-remote --exit-code <remote> refs/heads/gatedloop/preflight/<change>` and, if the branch is there, runs `git push <remote> --delete gatedloop/preflight/<change>`.

A local target attempts no remote deletion.

**Pull-request mode.** `gates record-merged` does the same with remote `origin`, only after its record commit (`git commit`) succeeds, since staging, `discipline check-commit` or the commit can still discard an archive that succeeded. It never does so for a `plan/` head, nothing-to-record, already archived, an acceptance refusal or an archive failure.

**Failure and output.**
- A failed deletion prints the command to run and leaves the exit status unchanged.
- When there is no branch anywhere, nothing is printed.
- The step does not depend on `loop.plan-preflight`, so a branch left from an earlier run is removed too.

## Risks

- **A remote branch deleted before a second machine adopts.** Deletion happens only after archive, when adoption is long over.
- **Every task stale.** If the base moved a lot after approval, adopt can find every task stale. The loop then behaves as today: the author runs for every task.
