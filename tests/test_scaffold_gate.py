"""Scaffold gating and debris naming (design D4 of `unblock-parallel-
planning`, tasks 4.1/4.4). `gates discipline check-propose --scaffold` runs
the same D3 branch discipline `check-propose` applies to an artifact write,
one step earlier -- before `openspec new change` creates any directory --
so a refusal never leaves a stranded scaffold (issue #7). Both the
scaffold and authoring refusal paths name any untracked, unproposed change
directory already on the working tree, with its cleanup command.

`hooks/gate-scaffold.sh` is exercised directly (stdin JSON, no `git worktree`
needed here -- the two-repo cwd-resolution technique already proven out in
`tests/test_worktree_resolution.py` is not this file's concern; this file
is about the branch-discipline judgement `check-propose --scaffold` makes).

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
HOOK = REPO / "hooks" / "gate-scaffold.sh"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _git_ok(cwd, *args):
    r = _git(cwd, *args)
    assert r.returncode == 0, r.stderr
    return r


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _run_hook(root: Path, cmd: str):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    return subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps({"tool_input": {"command": cmd}, "cwd": str(root)}),
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )


def _init_repo(root: Path) -> None:
    _git_ok(root, "init", "-b", "main")
    _git_ok(root, "config", "user.email", "t@example.com")
    _git_ok(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git_ok(root, "add", "-A")
    _git_ok(root, "commit", "-m", "init")


SCAFFOLD_CMD = "openspec new change my-change"


class TestCheckProposeScaffold(unittest.TestCase):
    """Task 4.1: `discipline check-propose --scaffold` reuses the exact D3
    judgement, with no file argument."""

    def test_refuses_on_a_feature_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "feature-x")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("design D9", r.stderr)

    def test_allows_on_the_merge_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)  # stays on main
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_allows_on_a_based_plan_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "plan/my-change")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestDebrisNaming(unittest.TestCase):
    """Task 4.3: both refusal paths (scaffold and authoring) name an
    untracked, unproposed change directory with its cleanup command."""

    def test_scaffold_refusal_names_existing_debris(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "feature-x")
            debris = root / "openspec" / "changes" / "stranded-change"
            debris.mkdir(parents=True)
            (debris / "proposal.md").write_text("half-written\n")

            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("stranded-change", r.stderr)
            self.assertIn("rm -r", r.stderr)

    def test_authoring_refusal_names_existing_debris(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "feature-x")
            debris = root / "openspec" / "changes" / "stranded-change"
            debris.mkdir(parents=True)
            (debris / "proposal.md").write_text("half-written\n")
            # An authoring write is refused only for a change in
            # implementation (hook-correctness D5).
            started = _run_gates(root, "task", "start", "1.1", "--change", "other")
            self.assertEqual(started.returncode, 0, started.stderr)

            r = _run_gates(root, "discipline", "check-propose", "openspec/changes/other/proposal.md")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("stranded-change", r.stderr)

    def test_no_debris_message_when_tree_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "feature-x")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn("rm -r", r.stderr)


class TestGateScaffoldHookEndToEnd(unittest.TestCase):
    """Task 4.4: the actual `openspec new change` command, matched by the
    hook, refused on a feature branch with the tree left unchanged; a
    pre-existing stranded directory is named in the refusal."""

    def test_scaffold_command_refused_on_feature_branch_tree_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "feature-x")
            before = sorted(p.name for p in (root / "openspec" / "changes").glob("*")) \
                if (root / "openspec" / "changes").exists() else []

            r = _run_hook(root, SCAFFOLD_CMD)
            self.assertNotEqual(r.returncode, 0)

            after_dir = root / "openspec" / "changes"
            after = sorted(p.name for p in after_dir.glob("*")) if after_dir.exists() else []
            self.assertEqual(before, after, "the hook itself must not create anything")

    def test_scaffold_command_allowed_on_merge_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)  # stays on main
            r = _run_hook(root, SCAFFOLD_CMD)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_unrelated_command_passes_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "feature-x")
            r = _run_hook(root, "ls -la")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_scaffold_refused_with_preexisting_debris_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "feature-x")
            debris = root / "openspec" / "changes" / "stranded-change"
            debris.mkdir(parents=True)
            (debris / "proposal.md").write_text("half-written\n")

            r = _run_hook(root, SCAFFOLD_CMD)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("stranded-change", r.stderr)


if __name__ == "__main__":
    unittest.main()
