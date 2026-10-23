# Design

## Context

See proposal.md for motivation. What exists today (`bin/gates`):

- `gates tests check` (`cmd_tests`, conditions in the `_tests_check_*` helpers) reads the staged index with `git ls-files -s` and the working-tree ledger. It accepts `--task` and `--change` only. The placed and handoff blobs live in `tests-handoff` and `tests-placed` ledger rows as git blob ids; a defect or halt voids a placement back to its `base` blob.
- `_change_ledger_rows(root, change, ref)` already reads `<ref>:.gatedloop/runs/<change>.jsonl`, which is how `_merge_prove_head` sees the lane's committed rows.
- `_merge_prove_head` checks the live-check and full `ci` markers, `verify`, taint and acceptance, collecting `problems` and refusing on any. It does not check the lock.
- `gates marker publish <gate>` requires a green local marker for the sha's normalized tree and posts `<prefix>/<gate>` with `tree <normalized>` as the description. `check-remote` reads it back. The prefix is a constant (`STATUS_CONTEXT_PREFIX`) that the pending rename changes in one place.
- This repository's workflow publishes `ci` on every pull request; branch protection requires it.

## Goals / Non-Goals

**Goals:**
- One lock evaluator with two inputs: the staged index (today) or a commit (new). Same conditions, same messages.
- The merge and the forge see a broken lock, not only the laptop.

**Non-Goals:**
- Re-running any test in CI. The lock is a content comparison plus a ledger read.
- A forge-side merge gate. Branch protection remains the forge's job, as the existing requirement says; this adds the status it can require.
- Verifying the lock for archived changes.

## Decisions

### D1. The evaluator takes a tree and a row set

Refactor the check so its inputs are (a) a map of path to blob for the paths under consideration and (b) the change's ledger rows. The staged mode builds (a) from the index as now; `--ref` builds it from `git ls-tree -r <commit>` and (b) from `_change_ledger_rows(root, change, ref)`. The red-run condition reads the same rows. With `--ref`, every placed task is checked, not only the one in flight, and the "task in flight is placed before any staged change" condition does not apply (there is no staging).

The change is resolved from `--change`, else from the ref's branch name when it names an active change, else refused with a message.

### D2. "No authored tests" passes

A change with no `tests-handoff` row at the ref passes and prints that there is nothing to verify. This keeps `marker publish tests` uniform across pull requests so branch protection can require the status everywhere, including planning PRs and docs PRs that carry no change.

### D3. The merge proves the lock

`_merge_prove_head` adds the `--ref refs/heads/<change>` evaluation to its `problems` list, after the taint check, in both modes. The refusal reuses the check's own lines (path, task, commit) with the merge step's prefix.

### D4. `tests` is a computed status, not a marker

`gates marker publish tests [--sha]` runs the evaluator against the sha's tree and posts `<prefix>/tests` with state `success` and `tree <normalized>` on a pass, `failure` with the first offending path on a fail (and exits non-zero). `check-remote tests <sha>` is unchanged in logic: the status must exist, be success, and name the sha's tree. No marker file is written, because the evidence is the tree itself.

Alternative considered: writing a `tests` marker so `publish` stays uniform. Rejected: a marker says "a command passed on this tree"; here the tree is the evidence and a marker would be a copy of it.

### D5. CI and the example

`.github/workflows/gatedloop.yml` adds `./bin/gates marker publish tests` after `publish ci`. `docs/running-at-scale.md` shows the same step in its workflow example. AUTOMATION.md's branch-protection list names `<prefix>/tests` beside `<prefix>/ci`, and the "what is covered where" prose says the lock now holds at the merge and the forge.

## Risks / Trade-offs

- [Ledger rows for a lane are committed only at `gates merge` step 1, so a `--ref` run on a lane head may miss uncommitted placement rows] → the check reads the ref's committed rows plus, as `_change_ledger_rows` already does, the uncommitted rows of the worktree holding the branch; in CI there is no worktree and the merge step committed them first.
- [A voided placement whose path was then legitimately edited by a later task] → the later task's placement row wins, as it does in the staged check.
- [`tests` status required by protection before adopters update their workflows] → documented as a two-step adoption: add the publish step, then require the status.
