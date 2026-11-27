# Proposal: held-file-diagnostics

## Why

`gates tests check` and the commit lock compare the holding area in the **index** with the latest handoff. When a held file under `.gatedloop/authored/<change>/` is untracked or unstaged, the index lacks it, and the lock reports "the held test … differs from the handoff" or "task N.M's behaviour-free reason differs from the handoff". The content is identical; it just isn't staged. An adopter spent a debugging session on that wording, read it as a byte mismatch in the reasons, and reported a defect that didn't exist (issue #216). The message named the wrong cause and the wrong remedy, which breaks `fail-loud-gates`: a refusal must say what is wrong and how to fix it.

The same report found a real gap. Placement deletes a behaviour-free task's `NO-TESTS` file, because the reason is recorded in the handoff. When that placement is later voided (a discarded task, a halt in flight), the lock expects the file back in the holding area. If the holding area was never committed, nothing restores it: `git checkout` has no copy, and `gates tests handoff <change> --task N.M` refuses because the task's directory "holds nothing". The only way out the adopter found was a fresh worktree and a fresh handoff.

Rejection test: this makes a stated guarantee enforceable. The lock's refusal names its real cause and remedy, and a voided behaviour-free task can be put back the way the lock expects it. It authors no artifact and names no stack command.

## What Changes

- **The lock says "not staged" when that is the cause.** In the staged-index check (`gates tests check`, and the commit hooks that run it), a held file whose index entry is missing or wrong is classified against the working tree:
  - the file on disk matches the handoff: it is **not staged**, and the line says so and names `git add <state dir>` (`.gatedloop` by default) and a re-check;
  - the file is absent on disk and from the index: it is **missing from the holding area**, and the line names the command that restores it;
  - otherwise it **differs from the handoff**, worded exactly as today.

  This applies to held tests, `NO-TESTS` reasons and `CHARACTERIZATION` declarations alike. `gates tests check --ref` reads a commit's tree, so it has no working tree to compare with and keeps its wording.
- **A per-task re-handoff restores a lost `NO-TESTS` file.** `gates tests handoff <change> --task N.M`, when N.M's holding directory is empty, N.M is declared behaviour-free in the current handoff, and N.M has no placement in force, writes `NO-TESTS` back with the recorded reason. It records no ledger row, because nothing was re-authored, and prints the path and the `git add` to run. Every other empty-directory case refuses as today.
- The check's "missing" line for a `NO-TESTS` file names that command. For a missing held test or `CHARACTERIZATION` file, it names `git checkout HEAD -- <path>` when `HEAD` has the file. Otherwise it names the author's re-handoff.

## Capabilities

### Modified Capabilities

- `test-discipline`: the lock's refusal for an unstaged or missing held file, and the per-task handoff's restoration of a recorded `NO-TESTS` reason.

## Impact

- `bin/gates`: `_lock_problems` (condition 2, staged mode only) and `_tests_handoff` (the `--task` empty-directory branch); a non-writing blob hash for the working-tree comparison.
- `tests/`: new cases for each classification and for the restore; `tests/test_tests_check_staged_output.py`'s existing cases stay byte-identical. No new subcommand or flag, so `tests/contract.json` is unchanged.
- `SETUP.md` (the handoff and lock paragraphs) and `README.md` ("How tests flow"): what the lock reports for an unstaged held file, and that a per-task re-handoff restores a behaviour-free reason.
