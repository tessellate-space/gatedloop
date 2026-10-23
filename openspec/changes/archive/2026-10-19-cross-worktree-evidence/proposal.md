# Proposal

## Why

Issue #38 reports that one session can only work safely in one checkout at a time.
Reproducing it on main and on v0.4.0 showed that its stated cause is not the real one.
The hooks already resolve the repository a command targets: `git -C`, a leading
`cd <dir> &&`, and `GIT_DIR=` / `GIT_WORK_TREE=` have worked since 0.4.0
(`parallel-planning`). Two other defects produced the symptoms, and a third came to
light while checking the doctor output in the report.

1. **The merge hook ignores evidence recorded in the lane.** Markers are kept per
   worktree, so a lane's green `live-check` and `ci` live in
   `.git/worktrees/<lane>/specloop/markers`. A squash onto `main`, run from the primary
   checkout however it is targeted, makes the hook read only the primary's store, and
   it is always refused with "no 'live-check' marker found". The only merge that
   passes is one run from inside the lane. That is why the reporter's orchestrator has
   to stay `cd`-ed in the lane for the whole merge, why planning on the primary queues
   behind it, and why a stray `cd` is dangerous. `gates merge` (0.5.0) already reads
   both stores; the hook was never given the same lookup.
2. **The hook installer and doctor look in a linked worktree's private git dir.** They
   find the hook path through `git rev-parse --git-dir`, which in a linked worktree is
   `.git/worktrees/<lane>`. Git runs hooks only from the common directory, or from
   `core.hooksPath`. So from a lane:
   - `gates doctor` warns that the hook is not installed when it is (the report's
     doctor output shows this);
   - `gates hook install` writes `.git/worktrees/<lane>/hooks/pre-commit`, a file git
     never runs, and reports success, which breaks `fail-loud-gates`;
   - the `git-hook-refresh` adoption item (`adoption-followups`, unreleased) inherits
     both errors.
3. **`git --git-dir=… --work-tree=…` falls back to the session directory.** The
   resolver handles the environment-variable forms but not the equivalent flags.

The reporter's fourth item, a heredoc that quotes `git merge --squash` being gated,
is already fixed on main by `hook-correctness` and ships in 0.5.0.

One more defect surfaced in this repo's own CI after `merge-pull-request` landed:

4. **The `record` job publishes a status for a commit GitHub doesn't have yet.** The
   workflow, and the example in `docs/running-at-scale.md` it was adapted from, run
   `gates marker publish ci` before `git push`, so the status call fails with HTTP 422
   and the follow-up PR is never opened.

## What Changes

- **Merge evidence from the incoming branch's worktree.** `gates gate-marker check`
  gains `--ref <ref>`. When the ref names a local branch checked out in another
  worktree, that worktree's marker store is consulted after the current one's. The
  merge hook passes the incoming ref for both its `live-check` and its unscoped-`ci`
  checks. `gates merge` step 1 uses the same helper instead of its own loop. The
  denial still names the trees it compared, and now names every store it read.
- **The shared hooks directory.** The hook path is resolved with
  `git rev-parse --git-path hooks`, which honours both the common directory and
  `core.hooksPath`. That one helper is used by:
  - hook-owner detection;
  - `gates hook install`;
  - `_hook_state` and so `gates doctor`;
  - the adoption hook fact.
  From a linked worktree, all four now see the same hook the primary sees.
- **`--git-dir` / `--work-tree` flags** are resolved like their environment-variable
  forms, in both the `--opt=value` and `--opt value` spellings.
- **Publish after push.** The repo workflow and the docs example push the follow-up
  branch first, then publish `specloop/ci` on it, then open the PR.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `parallel-planning`: the resolver's directory signals include the `--git-dir` and
  `--work-tree` flags.
- `loop-enforcement`:
  - a merge counts markers recorded in the worktree holding the incoming branch;
  - the hook installer resolves git's effective hooks directory.

## Impact

- `bin/gates`:
  - the marker check and its `--ref` option;
  - `gates merge` step 1;
  - a new `_hooks_dir` helper used by `_detect_hook_owner`, `_hook_install`,
    `_hook_state` and the adoption facts;
  - the git-cwd resolver.
- `hooks/gate-merge.sh`: passes `--ref` to both marker checks.
- `.github/workflows/specloop.yml` and `docs/running-at-scale.md`: step order.
- `SETUP.md`, `AUTOMATION.md`: merging from the primary when the lane holds the
  evidence; hooks from a linked worktree.
- Tests: `tests/` for each case, using real linked worktrees.
