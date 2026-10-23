"""A stale `ci` denial names what changed (design D4 of `hook-correctness`,
#33 item 8).

The usual cause of a "marker is stale" commit denial is a file staged after
`gates run ci` ran -- but the denial only said "no recorded tree matches",
leaving the operator to guess. `gates gate-marker check ci` now diffs the
most recently recorded tree against the staged one and says which paths
differ; both commit hooks (the `PreToolUse` one and the git-layer
`pre-commit`) print it as their denial.

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
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _env(root: Path) -> dict:
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env["CLAUDECODE"] = "1"
    return env


def _green_then_staged(root: Path) -> None:
    """A repo where `gates run ci` passed on a staged `work.txt`."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    (root / "work.txt").write_text("v1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    (root / "work.txt").write_text("v2\n")
    _git(root, "add", "work.txt")
    ci = subprocess.run(
        [sys.executable, str(GATES_SHIM), "run", "ci"], cwd=root, capture_output=True, text=True,
    )
    assert ci.returncode == 0, ci.stderr


def _denials(root: Path) -> dict:
    """Both commit hooks' stderr, each asserted to deny."""
    tool = subprocess.run(
        ["bash", str(COMMIT_HOOK)],
        input=json.dumps({"tool_input": {"command": "git commit -m x"}, "cwd": str(root)}),
        cwd=str(root), env=_env(root), capture_output=True, text=True,
    )
    git_layer = subprocess.run(
        ["bash", str(GIT_PRE_COMMIT)], cwd=str(root), env=_env(root),
        capture_output=True, text=True,
    )
    assert tool.returncode != 0, tool.stderr
    assert git_layer.returncode != 0, git_layer.stderr
    return {"PreToolUse": tool.stderr, "pre-commit": git_layer.stderr}


class TestFilesStagedAfterTheGate(unittest.TestCase):
    def test_denial_names_the_files_staged_after_the_gate_ran(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _green_then_staged(root)
            (root / "late.txt").write_text("forgot this\n")
            _git(root, "add", "late.txt")
            for hook, stderr in _denials(root).items():
                with self.subTest(hook=hook):
                    self.assertIn(
                        "1 file(s) were staged after `gates run ci` ran: late.txt", stderr,
                    )
                    self.assertIn("re-run the gate", stderr)


class TestOtherwiseDifferingPaths(unittest.TestCase):
    def test_denial_lists_status_and_path_capped_at_ten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _green_then_staged(root)
            (root / "work.txt").write_text("v3\n")
            for i in range(11):
                (root / f"new{i:02d}.txt").write_text(f"{i}\n")
            _git(root, "add", "-A")
            for hook, stderr in _denials(root).items():
                with self.subTest(hook=hook):
                    self.assertIn("the staged tree differs from the one `ci` passed on:", stderr)
                    self.assertIn("A new00.txt", stderr)
                    self.assertNotIn("new10.txt", stderr)
                    self.assertIn("and 2 more", stderr)
                    self.assertNotIn("A work.txt", stderr)


if __name__ == "__main__":
    unittest.main()
