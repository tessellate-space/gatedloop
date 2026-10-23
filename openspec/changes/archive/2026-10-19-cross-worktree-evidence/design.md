# Design

## Context

The four defects were reproduced in scratch repositories: a primary checkout on
`main`, a linked worktree `lane` on change branch `add-thing`, `ci: "true"`, and one
surface with `live-check: "true"`. Each hook was fed the PreToolUse JSON the harness
sends.

| Case | main | v0.4.0 |
|---|---|---|
| `git -C <lane> commit` / `cd <lane> && git commit`, fresh marker in the lane | allowed | allowed |
| same, stale marker | denied in `<lane>` | denied in `<lane>` |
| `cd <primary> && openspec new change` from a detached worktree | allowed | allowed |
| `git -C <primary> merge --squash add-thing`, green `live-check` in the lane | **denied: no marker** | **denied: no marker** |
| `gates doctor` from the lane, hook installed in the primary | **WARN: not installed** | — |
| `gates hook install` from the lane | **writes `.git/worktrees/lane/hooks/pre-commit`** | — |
| `git --git-dir=<x>/.git --work-tree=<x> commit` | **resolves the session dir** | — |

## Decisions

### D1. One helper names the stores that may vouch for an incoming ref

`_marker_stores(root, ref) -> list[Path]` returns `[root]`, followed by the worktree
returned by `_worktree_holding(root, branch)`, but only when:
- `ref` is a local branch, given as `<branch>` or `refs/heads/<branch>`;
- that worktree is not `root` itself.

A ref that names a remote branch, a tag or a sha, or a branch no worktree holds,
yields `[root]` alone. That is today's behaviour.

Why the holder's store is trustworthy: a marker is keyed on the normalized tree. The
holder's marker therefore vouches for exactly the tree the incoming ref points at,
which the hook already resolves as `source_tree`. Reading a second store widens where
evidence is found, not what counts as evidence.

`gates merge` step 1 replaces its inline `stores = [root] + [lane]` with this helper.

### D2. `gate-marker check --ref`

`gates gate-marker check <gate> <tree> [--require-scope S] [--ref R]` tries each store
from `_marker_stores(root, R)` in order and exits 0 on the first match. On failure it
prints one line per store it read, so a denial says where it looked, for example:

```
no 'live-check' marker found (primary: <path>; worktree of 'add-thing': <path>)
```

`gate-merge.sh` passes `--ref "${ref}"` on both the `live-check` and the unscoped-`ci`
check whenever it parsed a ref. When it parsed none, the call is unchanged.

The hook keeps its order: it tries the source tree first, then HEAD's tree, and the
`ci` check uses the tree the `live-check` matched. Only the store set grows.

### D3. Git's effective hooks directory

`_hooks_dir(root)` runs `git rev-parse --git-path hooks` and resolves the result
against `root` when it is relative. Git computes that path itself, using
`core.hooksPath` when set and the common directory otherwise, so it is the directory
git will actually run hooks from, in every worktree.

Every place that today joins `_git_dir(root) / "hooks"` uses it instead:
- `_detect_hook_owner`, for the bare-hook and none paths;
- `_hook_install`;
- the adoption `facts["hook"]`, through `_hook_state`.

The `core.hooksPath` classification (`hooksPath` kind) stays: a redirect to an
unrecognised path still refuses and instructs. Its path now comes from the same
helper, so the primary and a lane name the same file.

### D4. Flag forms of the directory signals

The resolver treats `--git-dir=<p>`, `--git-dir <p>`, `--work-tree=<p>` and
`--work-tree <p>` like the `GIT_DIR` / `GIT_WORK_TREE` assignments it already handles:
- the work tree wins;
- a `--git-dir` ending in `.git` resolves to its parent;
- a later `-C` composes with them as git does, with `-C` applied first, then the
  paths resolved against it.

A `--git-dir` that does not end in `.git` and has no `--work-tree` falls through to
the next signal, exactly as the env form does today.

### D5. Publish after push

In the repo's `record` job and in the docs example, the follow-up branch is pushed
first. Then `gates marker publish ci --sha "$(git rev-parse HEAD)"` runs, then the PR
is opened. The `ci` run stays before the push, so a red tree is never pushed.

### D6. What this does not change

- **Per-worktree markers stay per worktree.** A commit in the primary is still never
  vouched for by a lane's marker, and vice versa, because the commit gate is not given
  `--ref`. Only the merge, which by definition brings another branch's tree in, reads
  the holder's store.
- **Bare-line rule and scaffold hook.** The report's requests 2 and 3 already hold,
  and the scaffold hook needs no change. OpenSpec's `new change` takes no `--cwd`.
- **The reporter's own merge recipe** (dev stack reuse, the `eval` gate under worktree
  isolation) stays theirs. With D1 in place, a merge run from the primary, by
  `gates merge` or by hand, sees the lane's evidence.

## Risks

- **A lane's marker could be stale relative to the branch.** That's not possible
  undetected: the marker is keyed on the tree, and the hook compares it with the
  incoming ref's tree. A lane with uncommitted work proves a tree the ref does not
  point at, and the merge is still refused.
- **`--git-path hooks` on very old git.** It has been available since git 2.5 (2015).
  Specloop already requires `git worktree`, which is the same era, so there is no
  fallback.
