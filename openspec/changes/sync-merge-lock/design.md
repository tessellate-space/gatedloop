# Design: sync-merge-lock

## Context

See proposal.md for why. This section covers what the code does today.

`_lock_problems` in `bin/gates` evaluates the authored-test lock. `gates tests check` runs it, and so do both commit hooks (`hooks/gate-commit.sh` and the git-layer `pre-commit`). The evaluator has two halves:

- **Conditions over the tree.** Placed paths, held files, red runs and tag drift. They read content, not intent. A sync of the target leaves them unaffected, because the target carries no held file and no placement of this change.
- **The in-flight half** (the end of `_lock_problems`). This half takes the current task, which is the latest `task-start` after the latest full handoff, and the staged diff against `HEAD` (`_staged_diff_paths`). It sets `implementing` when any staged path falls outside `STATE_PREFIXES` (`.gatedloop/`). When the current task is not placed, it then refuses with "its authored tests are not placed". It runs only for the staged index, never with `at` (a commit).

`git merge --no-commit <target>` stages the target's changes. At a task boundary after `task start`, or after a halt has voided the task's placement, the current task is unplaced. So every sync is read as implementation (#221).

A sync after a plan amendment usually conflicts on two files. Both sides change them, and the lines are adjacent:

- the change's `tasks.md`. The branch ticked earlier tasks, and the target amended a later task's line.
- the change's ledger, `.gatedloop/runs/<change>.jsonl`. The branch appended task rows, and the target appended plan and approval rows.

Ticking 2.1 on the branch and amending 2.2 on the target change adjacent lines, which is a git conflict. The fix therefore can't rely only on "equals the target's blob".

Placement (`_tests_place`) checks each held file's blob and each real path's current content. It doesn't check the task's tag. The tag checks (`_oracle_handoff_problems`) run only at `gates tests handoff`. A tag amended after the handoff, for example a new `rewrites:` clause, therefore reaches placement unchecked.

## Goals / Non-Goals

**Goals**

- The documented sync commits at a task boundary when its commit gate is green, with no placement first.
- The lock's guarantee is unchanged: nothing that implements an unplaced task is committed. Only content the shim can prove came from the target passes as a sync.
- A task whose tag a sync amended can't be placed from a handoff that contradicts the new tag.

**Non-Goals**

- Hand-resolved conflicts in project files. They still count as implementing (D2).
- Detecting a text-only amendment of a pending task in code. That case goes through the prompts (D5).
- #213 (D6).
- Any new subcommand, flag, manifest key or ledger field.

## Decisions

### D1. The exemption lives in the in-flight half only

The change is limited to how `implementing` is computed. A staged path counts as implementing only when it is outside `STATE_PREFIXES` **and** is not one of the sync's own paths (D2, D3). Nothing else in the evaluator changes:

- Every condition over the tree applies to a merge commit exactly as to any other commit.
- `--ref` evaluation (`at`) has no in-flight half and is untouched.
- `gates merge` step 1 and `gatedloop/tests` see the same verdicts as before.

The helper is pure apart from its git reads and lives beside `_staged_diff_paths`. It returns the set of staged paths that are the sync's own, or an empty set when no qualifying merge is in progress.

*Alternative considered:* a ledger-only "sync" commit grade (the issue's other suggestion). Rejected: a merge commit must carry the merged tree, so it can never be ledger-only. A grade that skipped the lock for merge commits would also let implementation ride inside one.

*Alternative considered:* skip the in-flight half entirely while `MERGE_HEAD` exists. Rejected: an implementer could then stage a task's code during any merge and commit it unplaced.

### D2. A sync's own path: one of three proven results

When a qualifying merge is in progress (D3), a path in the staged diff is the sync's own when its staged state (a blob, or absent for a deletion) equals one of:

1. **The target's**: the path's state at `MERGE_HEAD`.
2. **Git's automatic merge**: the path's state in the tree that `git merge-tree --write-tree HEAD MERGE_HEAD` prints. This is the same ort merge `git merge` runs. It covers a file both sides changed without conflict, such as a README the branch and another change both edited. For a conflicted path, that tree holds the conflict-marked file, so a hand resolution never equals it.
3. **The change's `tasks.md`** (`openspec/changes/<change>/tasks.md`): the content at `MERGE_HEAD`, with every task line whose id is checked at `HEAD` set to checked (D4).

Any other staged path counts as implementing, as today. That includes a conflict resolved by hand in a project file, and a file edited after the merge was started.

`git merge-tree --write-tree` needs git 2.38 or later. When it exits with neither 0 (clean) nor 1 (conflicts), or prints no tree, the second candidate is dropped and the other two still apply. That fails closed: a sync whose paths need it is refused as today. The call writes the merge's tree and blobs to the object database as loose objects. It changes no ref and no index.

*Alternative considered:* the issue's suggestion, which equals `MERGE_HEAD`'s blob only. Rejected as the whole rule: in the motivating case it still refuses, because `tasks.md` differs from both sides after any tick. Kept as the first candidate.

*Alternative considered:* per-path `git merge-file` against the merge base. Rejected: it can disagree with ort on renames, and `merge-tree` gives the exact tree `git merge` produced, in one call.

### D3. Which merges qualify

The exemption applies only when both of these hold:

- `git rev-parse --git-path MERGE_HEAD` names a file holding exactly one commit. An octopus merge doesn't qualify.
- That commit is an ancestor of, or equal to, the merge target that `_resolve_merge_target` returns, checked with `git merge-base --is-ancestor`.

No resolvable target means no exemption. A merge of any other ref (a side branch, a local `main` ahead of `origin/main`) counts exactly as today. The incoming content is then only the target's, which already passed its own gates on the way in. That is why passing it through keeps the lock's guarantee: the lane's own authorship is still checked.

### D4. The `tasks.md` candidate

Done ⟺ committed, so `HEAD`'s ticks are the branch's truth. The target's file is the approved plan, so its task lines are the plan's truth. The expected file is the target's text with `HEAD`'s ticks applied. It is computed only when the file exists at both `HEAD` and `MERGE_HEAD`. A task id checked at `HEAD` but absent from `MERGE_HEAD` makes the candidate unavailable, and the path falls back to the other two. An amendment that removes a completed task is a plan problem, not a sync. The loop checks for it right after `git merge --no-commit`, before resolving anything: when a task id checked at `HEAD` is absent from `MERGE_HEAD`'s `openspec/changes/<change>/tasks.md`, it runs `git merge --abort` and halts `weak-spec` with detail `sync dropped completed task <N.M>[, <N.M>]`, with `--task` the current started task, or the first dropped task when none is started. The top-level loop records that halt and stops for the user, and a lane's halt goes to a human like any other `weak-spec` halt that does not begin `re-author`.

Tick lines are matched with the shim's existing task-line pattern. Only the checkbox is rewritten, and the rest of each line keeps its bytes. The tag-drift condition already compares the tree's tags with the target's, so a hand-edited tag fails there whatever this candidate says.

### D5. Placement holds the held tests to the task's current tag

`gates tests place <task>` runs `_oracle_handoff_problems` for that task only, right after it reads the handoff state and before its `NO-TESTS` branch (which deletes the reason file and writes a row), over the latest handoff state:

- the held tests,
- the `NO-TESTS` reasons,
- the `CHARACTERIZATION` declarations,

with `drift=False`, because the lock already checks drift. Its tag is read from the working tree's `tasks.md`, as the handoff reads it. On a problem, placement refuses before moving or deleting any file and before writing any row. The refusal names each problem and the route: re-dispatch the author for the task, then `gates tests handoff <change> --task <N.M>`.

The `loop.task-oracle: required` untagged-task message is change-wide and has no place in a per-task refusal. The call passes `only=<task>` and drops that message. An untagged task is never refused here.

This catches the amendments that make a handoff wrong in a way the shim can see:

- a new `rewrites:` path with no full file held,
- a move to or from `none`,
- a move to or from `characterization`.

A change of gate alone (`unit` to `integration`) doesn't contradict the held tests. The red run on the new gate, which the lock already reads from the tree, is where that shows.

A text-only amendment of a pending task can't be seen without recording each task's line at handoff, which is a new ledger field. It is left to the prompts. After a sync commit, the loop compares the task lines of `HEAD^1` and `HEAD`, ignoring ticks. Each unplaced task whose line changed goes back to the author:

- At the top level, `/gatedloop:tdd-apply` re-dispatches the author, then runs the authored-set review over that task and commits the re-handoff.
- A lane can't dispatch, so it halts `weak-spec` with detail `re-author <N.M>[, <N.M>]: the sync amended them`.
- In either halt, `gates halt record`'s `--task` is the current started task, or the first amended task when none is started; the detail names every task.
- A placement refusal on the tag takes the same route: at the top level, re-dispatch, review and `--task` re-handoff; in a lane, a `weak-spec` halt with detail `re-author <N.M>: <the refusal's first problem>`. `commands/orchestrator.md` step 4 routes a `re-author` detail to the test author, as it routes a `test-defect` detail, then resumes the lane.

*Alternative considered:* record each task's line in the handoff row and refuse placement when it moved. Rejected for this change. It adds a field to the handoff row, which two in-flight changes (`approved-tests`, `checkable-disputes`) are also extending. The case it adds over D5 is one the dispatcher already handles: an amendment follows a halt, and the halt's resolution is a re-author. It is recorded as a candidate if text-only amendments turn out to slip through.

### D6. #213 is out of scope

#213 asks for two things:

- `gates attempt grant`, a human-only attempt for a budget spent on environment failures. This is a new guarantee about the attempt budget, with its own refusal rules (refused inside an agent session). It has nothing to do with the lock.
- A restart inside an open sync merge. It arises when a plan does a task *inside* the sync merge, so that one commit carries the merge and the task. With this change the routine sync commits on its own at a task boundary, which leaves a clean tree before the next task's attempts. `gates attempt restart`'s clean-tree precondition then holds. A plan that still needs merge and task in one commit (the merged tree is red without the task) is a narrower case. It needs a decision about what a restart discards in an open merge, and that decision belongs with the attempt-grant design.

So the PR refers to #221 only, and #213 stays open.

### D7. Docs follow the behaviour

The following say a sync's own paths don't count as implementing, and say when placement refuses:

- SETUP.md: the lock paragraph and its enforcement table row.
- AUTOMATION.md: the lock row.
- README.md's "How tests flow" step 3.

No diagram node changes.

## Risks / Trade-offs

- [A hand-resolved conflict in a project file still deadlocks a lane at an unplaced task] → Such conflicts need the branch and target to have edited the same lines, which is rare at a task boundary. The refusal is unchanged, and the remedy is today's: retire the lane and cut it fresh from the target. Widening the rule to hand resolutions would let authored code through, which is the one thing the lock exists to stop.
- [git older than 2.38] → D2 fails closed to candidates 1 and 3, which still cover a sync where the two sides changed different files plus the `tasks.md` case.
- [Merge options that change the result (`-X ours`, `merge.renames=false`)] → The staged result may then differ from `merge-tree`'s, and the path counts as implementing. That fails closed.
- [Overlap with `approved-tests` on `skills/tdd-apply/SKILL.md`] → Different sections (§4b there, the sync paragraph after 5h here). Neither changes the other's text.

## Migration Plan

None. The change only stops refusing a commit the loop documents, and adds one placement refusal that a consistent handoff never meets. Rollback is a revert.
