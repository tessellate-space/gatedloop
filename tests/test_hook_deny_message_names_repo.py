"""Every gate hook's deny message names the repository it evaluated (design
D1, task 1.3 of `worktree-native-loop`). A mis-resolution used to be
undiagnosable from the message alone -- this proves the resolved path always
appears, from both a primary checkout's own denial and a secondary
worktree's.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / "hooks"
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: Path, branch: str = "main") -> None:
    _git(root, "init", "-b", branch)
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _change_dir(root: Path, change: str) -> Path:
    change_dir = root / "openspec" / "changes" / change
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("plan\n")
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    return change_dir


def _run_hook(hook_name: str, session_cwd: Path, stdin: dict):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run(
        ["bash", str(HOOKS / hook_name)], input=json.dumps(stdin), cwd=str(session_cwd),
        env=env, capture_output=True, text=True,
    )


class TestDenyMessagesNameTheRepo(unittest.TestCase):
    def test_gate_commit_names_the_evaluated_worktree(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)  # no ci marker -> denied
            _init_repo(session)

            result = _run_hook(
                "gate-commit.sh", session,
                {"tool_input": {"command": f"cd {worktree} && git commit -m x"}, "cwd": str(session)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(worktree), result.stderr)

    def test_gate_commit_names_the_primary_when_denied_there(self):
        with tempfile.TemporaryDirectory() as primary:
            primary = Path(primary)
            _init_repo(primary)

            result = _run_hook(
                "gate-commit.sh", primary,
                {"tool_input": {"command": "git commit -m x"}, "cwd": str(primary)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(primary), result.stderr)

    def test_gate_merge_names_the_evaluated_worktree(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)  # no live-check marker -> denied
            _init_repo(session)

            result = _run_hook(
                "gate-merge.sh", session,
                {"tool_input": {"command": f"cd {worktree} && git merge feature"}, "cwd": str(session)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(worktree), result.stderr)

    def test_gate_scaffold_names_the_evaluated_worktree(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)
            _git(worktree, "checkout", "-b", "unrelated-feature")  # refused here
            _init_repo(session)

            result = _run_hook(
                "gate-scaffold.sh", session,
                {"tool_input": {"command": f"cd {worktree} && openspec new change"}, "cwd": str(session)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(worktree), result.stderr)

    def test_gate_archive_names_the_evaluated_worktree(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)  # change not merged here -> denied
            _init_repo(session)

            result = _run_hook(
                "gate-archive.sh", session,
                {"tool_input": {"command": f"cd {worktree} && openspec archive my-change"}, "cwd": str(session)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(worktree), result.stderr)

    def test_gate_implement_names_the_evaluated_worktree(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)
            _change_dir(worktree, "my-change")
            _git(worktree, "add", "-A")
            _git(worktree, "commit", "-m", "author plan, never attested")
            _init_repo(session)

            result = _run_hook(
                "gate-implement.sh", session,
                {"tool_input": {"command": f"cd {worktree} && git checkout -b my-change"}, "cwd": str(session)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(worktree), result.stderr)


if __name__ == "__main__":
    unittest.main()
