# Design

## Context

See proposal.md for motivation. What exists today:

- `templates/git-hooks/pre-commit` exits 0 unless `CLAUDECODE` is set, resolves the shim through `CLAUDE_PLUGIN_ROOT` or PATH, then runs `discipline check-worktree`, `discipline check-commit <tree>` and `tests check`. `gates hook install` (`_hook_install`) installs that one template, detecting the owner (none, husky, lefthook, the pre-commit framework, a `core.hooksPath` redirect, a foreign bare hook, a stale copy of our own) and composing or refusing. `gates doctor` reports `git-commit-hook`.
- `hooks/hooks.json` wires ten tool-level hooks; the merge gate (`gate-merge.sh`) and the Stop audit have no git-layer equivalent. `gates merge` repeats the merge gate's checks in code (`_merge_prove_head`) and pushes once at the end, after writing the `merge` row.
- The merge target is resolved by the shim already (main/master detection used by the discipline checks).
- The adoption catalogue has a recurring `git-hook-refresh` item keyed on a stale commit-hook copy.

## Goals / Non-Goals

**Goals:**
- Every guarantee that can hold at the git layer holds there, on any host, inside a declared agent session.
- One install path, one doctor vocabulary, one refresh item for both hooks.
- Documentation that stops saying "Claude Code only" and starts saying what holds where.

**Non-Goals:**
- Tool-hook equivalents for other hosts (each host's hook API is its own change, if ever).
- Gating raw `git merge` at the git layer. Git's `pre-merge-commit` hook does not fire on fast-forwards; the push is the choke point that matters, because it is where history is shared.
- Any gate run inside a hook.

## Decisions

### D1. `discipline.agent-env` and `gates discipline agent-session`

The manifest key is a list of variable names, default `[CLAUDECODE]`, validated as non-empty identifiers. Both hook templates call `gates discipline agent-session`, which exits 0 when any listed variable is set and 1 otherwise; the hook exits 0 on 1. The templates no longer test `CLAUDECODE` directly, so the no-op decision lives in one place and follows the manifest.

Alternative considered: baking the list into the hook at install time. Rejected: the manifest is tracked and shared; the hook is a per-clone copy that goes stale.

### D2. Resolving the shim outside a plugin environment

The templates resolve the shim as: `CLAUDE_PLUGIN_ROOT/bin/gates`, then `gates` on PATH, then an absolute path `gates hook install` writes into the hook at install time (the path of the shim that ran the install). `gates doctor` marks a hook `stale-copy` when the written path no longer exists and nothing else resolves. The existing stale-copy refresh flow then reinstalls with the current path. The written path is the only install-time substitution in the template; everything else stays byte-comparable for the stale check, which compares the template with that line normalized.

### D3. `pre-push` and `gates discipline check-push`

The hook reads git's stdin lines (`<local ref> <local sha> <remote ref> <remote sha>`). For each line whose remote ref is `refs/heads/<merge target>` and whose local sha is not the zero sha, it runs `gates discipline check-push <local sha>`. The check passes when the change ledgers (any `.gatedloop/runs/*.jsonl` at that sha) hold a `merge` row whose `sha` is the pushed commit, or when the incoming-tree checks pass for the sha's tree: a `live-check` marker and a full `ci` marker in any marker store, `verify` where declared, no unresolved taint for the change the commit's branch names if any, the authored-test lock at the ref (when `test-lock-remote-check` has landed; otherwise omitted), and acceptance where a policy is declared. Denials name the unmet check and `gates merge <change>` as the remedy. Other lines pass silently.

`gates merge`'s final push is unaffected: it wrote the merge row for the squash commit before pushing. In pull-request mode the target is pushed by the forge, so the hook never sees it; branch protection covers that path as the existing requirement states.

Alternative considered: denying any push of the target inside an agent session, period. Rejected: `gates merge` must push.

### D4. Install, doctor, adoption

`_hook_install` loops over the two templates with the same owner logic; a husky append or a refuse-and-instruct message covers both hooks in one run. `gates doctor` adds `git-push-hook` with the states `wired`, `stale-copy`, `manager-uncomposed`, `unmanaged-hook`, `absent`. The recurring `git-hook-refresh` item's detector reads both rows. A new item `git-push-hook` (since the next minor, recommended "Yes: install the push hook") applies when the commit hook is wired and the push hook is absent, so existing adopters are asked once. `commands/gates-init.md`'s default-yes offer names both hooks.

### D5. The coverage table

AUTOMATION.md gets one table: rows are the guarantees (commit on green ci, locked tests, merge on proven head, push of proven target, implement after approval, scaffold on allowed branch, no plan writes during implementation, Stop audit and taint, forge merge), columns are tool hook, git layer, forge. README's requirements section replaces the implicit "Claude Code" with: the tool-hook layer needs Claude Code; the shim, the git layer and the forge layer run anywhere, with `discipline.agent-env` as the one binding another host needs.

## Risks / Trade-offs

- [A host that does not inherit environment variables into git subprocesses] → the hooks fall back to no-op, which is the documented failure direction (toward a human, never toward blocking one); the coverage table says so.
- [The written shim path leaks a per-machine path into `.git/hooks`] → hooks are not tracked; the path is a fallback only.
- [`check-push` on a large repo reads several ledgers at a sha] → it reads only `.gatedloop/runs/` blobs at the sha, bounded by the number of changes; no gate runs.
- [Order against `test-lock-remote-check`] → the lock condition in `check-push` is included only if that change has landed; the tasks say so.
- [The pending rename changes the hook file names' comments and the prefix] → nothing here names the plugin; the templates' comments are prose.
