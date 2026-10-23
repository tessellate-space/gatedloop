"""A branch checked out in more than one worktree cannot be committed to
(design D7 of `hook-correctness`, #33 item 10).

A lane forced a checkout of a branch the primary worktree held; its commit
then moved the ref under the primary checkout, whose index and working tree
silently went stale. `gates discipline check-worktree` reads
`git worktree list --porcelain` and refuses when the current branch appears
in more than one worktree, naming each; both commit hooks call it before the
marker check -- so even a green `ci` does not let the commit through.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
COMMIT_HOOK = REPO / "hooks" / "gate-commit.sh"
GIT_PRE_COMMIT = REPO / "templates" / "git-hooks" / "pre-commit"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _gates(root: Path, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _env(root: Path) -> dict:
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env["CLAUDECODE"] = "1"
    return env


def _shared_branch(primary: Path, lane: Path) -> None:
    """`primary` and `lane` both have `my-change` checked out -- the lane got
    there by forcing past git's own refusal. A green `ci` marker covers the
    primary's staged tree, so only the sharing can deny."""
    _git(primary, "init", "-b", "main")
    _git(primary, "config", "user.email", "t@example.com")
    _git(primary, "config", "user.name", "T")
    (primary / ".gates.yaml").write_text(MANIFEST)
    _git(primary, "add", "-A")
    _git(primary, "commit", "-m", "init")
    _git(primary, "branch", "my-change")
    _git(primary, "worktree", "add", str(lane), "my-change")
    _git(primary, "checkout", "--ignore-other-worktrees", "my-change")
    (primary / "work.txt").write_text("task\n")
    _git(primary, "add", "work.txt")
    ci = _gates(primary, "run", "ci", "--change", "my-change")
    assert ci.returncode == 0, ci.stderr


class TestCheckWorktree(unittest.TestCase):
    def test_a_branch_in_two_worktrees_is_refused_naming_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary, lane = Path(tmp) / "primary", Path(tmp) / "lane"
            primary.mkdir()
            _shared_branch(primary, lane)
            r = _gates(primary, "discipline", "check-worktree")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("my-change", r.stderr)
            self.assertIn(str(primary.resolve()), r.stderr)
            self.assertIn(str(lane.resolve()), r.stderr)

    def test_a_branch_of_its_own_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary, lane = Path(tmp) / "primary", Path(tmp) / "lane"
            primary.mkdir()
            _shared_branch(primary, lane)
            _git(primary, "checkout", "main")
            r = _gates(primary, "discipline", "check-worktree")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestBothCommitHooksRefuseASharedBranch(unittest.TestCase):
    def test_commit_denied_despite_a_green_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary, lane = Path(tmp) / "primary", Path(tmp) / "lane"
            primary.mkdir()
            _shared_branch(primary, lane)
            tool = subprocess.run(
                ["bash", str(COMMIT_HOOK)],
                input=json.dumps({"tool_input": {"command": "git commit -m x"}, "cwd": str(primary)}),
                cwd=str(primary), env=_env(primary), capture_output=True, text=True,
            )
            git_layer = subprocess.run(
                ["bash", str(GIT_PRE_COMMIT)], cwd=str(primary), env=_env(primary),
                capture_output=True, text=True,
            )
            for name, r in (("PreToolUse", tool), ("pre-commit", git_layer)):
                with self.subTest(hook=name):
                    self.assertNotEqual(r.returncode, 0, r.stderr)
                    self.assertIn(str(lane.resolve()), r.stderr)


if __name__ == "__main__":
    unittest.main()
