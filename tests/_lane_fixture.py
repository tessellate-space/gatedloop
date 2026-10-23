"""Shared fixtures for `cross-worktree-evidence`: a primary checkout and a
REAL linked lane worktree, and the two ways a session reaches the shim --
the PreToolUse hook scripts fed the JSON the harness sends, and
`gates hook git-cwd`.

What these tests observe is which repository, which marker store and which
hooks directory git and the shim agree on across worktrees. Only a real
`git worktree add` can show that (a linked worktree's private git dir under
`.git/worktrees/<lane>` is the whole defect), so the fixtures sit on the git
layer boundary on purpose.

Every child process gets `clean_env` from `_merge_fixture`: no `GIT_*`
variable, `CLAUDECODE=1` pinned rather than inherited from the host (CI has
it unset), and `CLAUDE_PLUGIN_ROOT` pointed at this repository so the hook
scripts find this shim. Nothing here touches this repository's own `.git`.

Stdlib only, per `zero-dep-shim`. Not a test module (no `test` prefix).
"""

import json
import subprocess
import sys
from pathlib import Path

from _merge_fixture import BASE_MANIFEST, REPO, MergeRepo, clean_env

GATES_SHIM = REPO / "bin" / "gates"
HOOKS = REPO / "hooks"

# `ci` and one surface with a `live-check`, both always green: the design's
# reproduction manifest.
LIVE_CHECK_MANIFEST = BASE_MANIFEST + (
    "surfaces:\n"
    "  - name: all\n"
    '    match: "**"\n'
    '    live-check: "true"\n'
)


def lane_repo(tmp) -> MergeRepo:
    """A primary checkout on `main` and a linked worktree `lane` holding the
    change branch `add-thing`, with one gated task commit on it."""
    repo = MergeRepo(Path(tmp), manifest=LIVE_CHECK_MANIFEST)
    repo.start_change(lane=True)
    repo.task_commit("thing.txt", "thing\n", "add the thing")
    return repo


def run_hook(hook: str, command: str, cwd, **env) -> subprocess.CompletedProcess:
    """Fire `hooks/<hook>` exactly as the harness does: the PreToolUse JSON
    on stdin, the hook input's `cwd` set to `cwd`, and the hook process
    itself started there."""
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(cwd)})
    extra = {"CLAUDE_PLUGIN_ROOT": str(REPO), "CLAUDE_PROJECT_DIR": None}
    extra.update(env)
    return subprocess.run(
        ["bash", str(HOOKS / hook)], input=payload, cwd=str(cwd),
        env=clean_env(extra), capture_output=True, text=True,
    )


def resolve_git_cwd(kind: str, command: str, hook_cwd) -> Path:
    """The directory `gates hook git-cwd <kind>` resolves for `command`,
    given the hook input's `cwd`."""
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(hook_cwd)})
    r = subprocess.run(
        [sys.executable, str(GATES_SHIM), "hook", "git-cwd", kind],
        input=payload, cwd=str(hook_cwd), env=clean_env({"CLAUDE_PROJECT_DIR": None}),
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise AssertionError(f"gates hook git-cwd failed: {r.stderr}")
    return Path(r.stdout.strip())


def markers_dir(git_dir) -> str:
    """The marker store under a worktree's git dir, as the shim names it."""
    return str(Path(git_dir).resolve() / "gatedloop" / "markers")
