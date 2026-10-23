"""End-to-end check for the commit gate across two REAL git worktrees (task
1.4 of `unblock-parallel-planning`, design D1/D5). Where
`test_worktree_resolution.py` proves cwd-based resolution generically with
two independent repos, this file reproduces the actual production
configuration -- one `git worktree add` off a single repo -- and matches the
two `parallel-planning` spec scenarios exactly:

- A commit in a secondary worktree with a green marker there is allowed.
- The primary checkout's own commit is still denied without its own marker,
  regardless of what the worktree's marker store holds (design D5: marker
  stores are per-worktree, never shared or promoted).

Stdlib only, per `zero-dep-shim`.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
HOOK = REPO / "hooks" / "gate-commit.sh"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _run_hook(process_cwd: Path, stdin: dict, env_overrides: dict | None = None):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(stdin),
        cwd=str(process_cwd),
        env=env,
        capture_output=True,
        text=True,
    )


class TestCommitGateAcrossRealWorktrees(unittest.TestCase):
    def test_both_spec_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            primary = tmp / "primary"
            primary.mkdir()
            _git(primary, "init", "-b", "main")
            _git(primary, "config", "user.email", "t@example.com")
            _git(primary, "config", "user.name", "T")
            (primary / ".gates.yaml").write_text(MANIFEST)
            _git(primary, "add", "-A")
            _git(primary, "commit", "-m", "init")

            _git(primary, "branch", "feature")
            worktree = tmp / "wt"
            _git(primary, "worktree", "add", str(worktree), "feature")

            # --- Scenario: a commit in a secondary worktree with a green
            # marker there is allowed, even though the primary checkout has
            # no such marker at all.
            (worktree / "new.txt").write_text("x\n")
            _git(worktree, "add", "new.txt")
            r = _run_gates(worktree, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)

            allowed = _run_hook(
                tmp,
                {"tool_input": {"command": "git commit -m x"}, "cwd": str(worktree)},
                env_overrides={"CLAUDE_PROJECT_DIR": str(primary)},
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

            # --- Scenario: the primary checkout's own commit is still
            # denied without its own marker -- the worktree's green marker
            # (just used above) does not leak across (design D5).
            (primary / "other.txt").write_text("y\n")
            _git(primary, "add", "other.txt")

            denied = _run_hook(
                tmp,
                {"tool_input": {"command": "git commit -m y"}, "cwd": str(primary)},
                env_overrides={"CLAUDE_PROJECT_DIR": str(primary)},
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("marker", denied.stderr)


if __name__ == "__main__":
    unittest.main()
