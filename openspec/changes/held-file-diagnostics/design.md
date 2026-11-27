# Design: held-file-diagnostics

## Context

See proposal.md for why. The lock's evaluator is `_lock_problems` in `bin/gates`. It takes a `{path: blob}` map, which is the staged index for `gates tests check` and the commit hooks (`hooks/gate-commit.sh` runs `gates tests check`), and a commit's tree for `gates tests check --ref` (`at` set). Its condition 2 builds three expectation maps for every task with no placement in force: `wanted_held` (held test → blob), `reasons_held` (`NO-TESTS` → reason) and `declared_held` (`CHARACTERIZATION` → reason). It reports any entry whose index content differs, with one wording per map, all saying "differs from the handoff". The index is the only thing it looks at. A held file that exists only on disk, untracked or modified since it was staged, therefore looks exactly like an edited one.

`gates tests place` deletes a behaviour-free task's `NO-TESTS` file and records the placement. The reason lives on in the handoff row (`state["no_behaviour"]`). When the placement is voided by a `test-defect` row, or by a `halt` at a task not yet completed, `_active_placements` drops the task, and condition 2 expects the file back. A discarded task restores it only when `HEAD` holds it, through `git checkout -- .` after the authoring commit. When the holding area was never committed, which is the first problem's root, nothing restores it. `_tests_handoff --task N.M` reads the holding area from disk and refuses an empty directory with "holds nothing".

## Goals / Non-Goals

**Goals:**

- Every condition-2 refusal in the staged check names the actual cause (not staged, missing, or differing content) and a remedy that works.
- A voided behaviour-free task can be returned to the state the lock expects with one shim command, with no fresh worktree and no re-dispatch of the author.

**Non-Goals:**

- `gates tests check --ref`'s wording. A commit's tree has no working tree beside it, so "not staged" has no meaning there.
- Restoring held **test** files or `CHARACTERIZATION` declarations from the ledger. Their blobs are in the local object store only where the handoff ran, so a restore would work on one machine and fail on another. A missing one is pointed at `HEAD` or at its author instead (D3).
- Condition 1 (placed paths). It already says "is not staged — `git add <path>`" for a placed test left unstaged.
- Changing what the lock accepts. Every verdict stays as it is today; only the wording of a refusal and the handoff's empty-directory case change.

## Decisions

### D1. Classify a condition-2 mismatch against the working tree, in staged mode only

When `at` is `None` and a condition-2 entry's index content does not match, the lock reads the same path from the working tree:

| On disk | Classification | Line |
|---|---|---|
| present, and it matches the handoff | not staged | `<rel>: not staged — the file on disk matches the handoff, but the index does not hold it. Run `git add <state>` and re-check` |
| absent, and absent from the index | missing | see D3 |
| anything else | differs | today's wording, byte for byte |

"Matches" uses the comparison condition 2 already uses for that kind of file. For a held test, the working copy's blob id must equal the handed-off blob. For `NO-TESTS` and `CHARACTERIZATION`, the stripped text must equal the recorded reason. `<state>` is the state directory's name as `_state_rel` resolves it (`.gatedloop` by default), so a project with a renamed state directory is told the right path. One wording covers both untracked and modified-since-staging: the remedy is the same, and the shim needn't ask git which one it is.

The blob id comes from `git hash-object --stdin` **without** `-w`. A check should write nothing, and `_file_blob` (which goes through `_hash_blob` and writes the object) is the wrong helper here. The new non-writing helper sits next to `_hash_blob`. Condition 1 keeps its existing `_file_blob` call, which can write an object when a placed path mismatches. Changing it is out of scope here, so "writes nothing" is a property of condition 2's classification, not of the whole check.

An absent file with an index entry is "differs": the index holds the wrong content, and the file is gone from disk. That is not a staging slip, so it keeps today's wording.

*Alternative considered:* report "not staged" whenever `git ls-files` lacks the path. Rejected because it would tell someone to stage a file that does **not** match the handoff, and the re-check would then fail with "differs" after the remedy was followed. Classifying on content gives a remedy that works.

### D2. A per-task re-handoff restores a recorded `NO-TESTS` reason (chosen over a check-only fix)

The issue gave two options: make the per-task re-handoff restore the file, or have check report "missing" and name a restoring command. We take the first, and check names it (D3).

`gates tests handoff <change> --task N.M` (real, not `--dry-run`) gains one step, run **first**, before the holding area is read. Today an empty N.M is refused in three places, and the restore takes precedence over all three:

- the whole holding area holds nothing ("the holding area … is empty"). This is the common case: placement deletes held files, so it is what an all-`NO-TESTS` change, or a voided task that is the last one held, looks like;
- N.M's directory is left on disk with no file in it, which `_read_holding_area` reports as "task N.M: holds nothing" and the handoff refuses as a holding-area problem;
- N.M's directory is absent while other tasks hold files (the `--task` branch's "holds nothing").

So the first step checks whether N.M's directory is absent or holds no file, at any depth. If it is, the handoff **restores** when all three of these hold:

1. the current authoring state (`_authoring_state`) declares N.M behaviour-free;
2. N.M has no placement in force (`_active_placements` with `_lock_completion` at `HEAD`, falling back to `_active_placements(rows)` on `_LedgerRewritten`, exactly as the full handoff's D10 guard reads it), so the lock expects the file;
3. the oracle-tag checks the handoff runs for N.M pass (`_oracle_handoff_problems` with N.M as a `NO-TESTS` task), so a restore never brings back a declaration the approved plan has since contradicted.

It writes `<state>/authored/<change>/N.M/NO-TESTS` with the recorded reason and a trailing newline, appends **no** ledger row, prints `gatedloop: restored <rel> from the handoff recorded for task N.M ("<reason>") — nothing was re-authored, so no row was recorded. Stage it: `git add <state>``, and exits 0. When conditions 1 and 2 hold and condition 3 fails, the step itself refuses with the handoff's existing oracle-tag contradiction message ("refusing the handoff for '<change>' — it contradicts the plan's oracle tags …") and writes nothing, because that is the real reason the task can't be restored. When N.M's directory holds any file, or condition 1 or 2 fails, the step does nothing and the handoff continues exactly as today, refusals and wording included: a task with tests, a task placed and in force, or a task not in the handoff. The restore writes only under N.M, so it never hides another task's holding-area problem. The next handoff or check still reports that problem.

Why this option:

- **No new surface.** A check-only fix needs a command to name. None restores a held file today, so it would need a new subcommand (contract, SETUP, README, release-docs inventory), or it would tell an agent to write the reason into a held file by hand. Writing a held file by hand is exactly what the lock exists to stop an implementer doing.
- **It's the command people already reach for.** The lock's own line for this file says the reason "changes only through `gates tests handoff <change> --task N.M`", and the reporter ran exactly that. Making it work removes the trap, where a new command would only document it.
- **It can't change a reason.** The content written is the ledger's recorded reason, so the restore can only put back what the lock already expects. The author's authority over the declaration is untouched.
- **No row, because nothing was authored.** A handoff row records an author's act (`author: separate|inline`). Recording one for a restore would attribute authorship to whoever ran the command, and stats that count handoffs would see a re-authoring that never happened. The ledger stays truthful, and the lock's expectation is unchanged by construction.

*Alternative considered:* also restore when the directory is non-empty but lacks `NO-TESTS`. Rejected because a non-empty directory is an author re-declaring the task, which is the existing handoff's job.

### D3. What "missing" names

| Missing file | Remedy in the line |
|---|---|
| `NO-TESTS` | `<rel>: missing from the holding area — task N.M is declared behaviour-free in the handoff, and `gates tests handoff <change> --task N.M` writes its recorded reason back; then `git add <state>` and re-check` |
| held test or `CHARACTERIZATION`, and `HEAD` has the path | `<rel>: missing from the holding area — `git checkout HEAD -- <rel>` restores it; then re-check` |
| held test or `CHARACTERIZATION`, and `HEAD` lacks it | `<rel>: missing from the holding area, and HEAD has no copy — it returns only through its author: re-dispatch the author for task N.M, then `gates tests handoff <change> --task N.M`` |

`git checkout HEAD -- <rel>` writes both the index and the working tree, so no `git add` follows it. When `HEAD` holds the file, its content is the committed handoff's content. A later re-handoff of the task would have committed the new content with the ledger row (tdd-apply §5-defects step 3).

## Risks / Trade-offs

- [An implementer may hesitate to run `gates tests handoff --task`, reading it as the author's command] → The line names the command and says it writes the *recorded* reason back, and the handoff prints that nothing was re-authored. The restore cannot change what the author declared, so the role boundary holds. If agents still balk in practice, a one-line prompt note in tdd-apply's discard step is a follow-up, not part of this change.
- [Hashing a working-tree file on every condition-2 mismatch] → It runs only on a mismatch, which is already a refusal, and only for holding-area files.
- [An existing test that depends on the "differs" wording for an unstaged file] → Only `tests/test_tests_check_staged_output.py` pins condition-2 text, and its held-file case stages the edit with `git add -A`, so it still reads "differs". The task keeps that module's output byte-identical.

- [An existing test that pins a per-task handoff's refusal of an empty task] → None meets all three restore conditions. `tests/test_authored_tests.py` (`test_refusals_write_nothing`) and `tests/test_plan_preflight_dry_run.py` (`test_an_empty_area_is_refused_alike`) refuse an empty area in a full handoff, which the restore never touches. `test_a_task_holding_nothing_is_refused_alike_under_task` hands off `--task 3.9`, which no handoff declares behaviour-free, so it still refuses. No test is rewritten.

## Migration Plan

Nothing to migrate: no manifest key, ledger field or flag changes. An older shim reading a ledger after a restore sees exactly the rows it would have seen, because the restore writes none.
