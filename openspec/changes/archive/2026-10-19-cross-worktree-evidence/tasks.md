## 1. Merge evidence across worktrees

- [x] 1.1 Add `_marker_stores(root, ref)` per design D1, and make `gates merge` step 1 use it. Tests:
  - a local branch held by another worktree;
  - a local branch nobody holds;
  - a remote ref and a sha;
  - the holder being `root`;
  - the existing merge-step tests still pass.
- [x] 1.2 `gate-marker check --ref` per design D2, which names every store read on failure; `hooks/gate-merge.sh` passes the incoming ref on both checks. Tests run the real hook script against a primary and a linked lane:
  - the lane-proven merge is allowed from the primary, via `-C` and via `cd &&`;
  - lane markers on a different tree deny, naming both stores;
  - the commit gate in the primary ignores the lane's marker.

## 2. The effective hooks directory

- [x] 2.1 Add `_hooks_dir(root)` per design D3, used by `_detect_hook_owner`, `_hook_install`, `_hook_state` and the adoption hook fact. Tests in a real linked worktree:
  - doctor reports a hook installed in the primary;
  - install writes to the shared directory, and the hook fires for a commit in the primary;
  - `git-hook-copy` and `git-hook-current` agree from both checkouts;
  - a `core.hooksPath` redirect is still classified and refused as today.

## 3. Directory signals

- [x] 3.1 Resolve `--git-dir` and `--work-tree`, in both spellings, per design D4. Tests cover:
  - each spelling;
  - work tree over git dir;
  - a `.git`-suffixed git dir;
  - a bare `--git-dir` falling through;
  - composition with `-C`.

## 4. Publish after push

- [x] 4.1 `.github/workflows/specloop.yml` and `docs/running-at-scale.md`: the follow-up branch is pushed before `gates marker publish ci --sha`, then the PR is opened (design D5).

## 5. Docs

- [x] 5.1 Update the docs:
  - SETUP's worktree-lanes and merge sections: a merge from the primary sees the lane's evidence;
  - the hook section: install and doctor work from any worktree;
  - AUTOMATION's merge-gate row names the stores read.

  `python3 scripts/release docs` exits 0.

## 6. Close

- [x] 6.1 `gates run ci` green on the final tree; `openspec validate cross-worktree-evidence --strict` passes
