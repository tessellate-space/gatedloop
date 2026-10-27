"""Both commit hooks skip the authored-test lock on a ledger-grade commit
(change `unblock-authored-lock`, design D1; issue #56).

A ledger row cannot change a test, yet both hooks ran `gates tests check`
after `discipline check-commit` had allowed a ledger-only diff, so a lock
that failed for any reason refused every bookkeeping commit on the branch,
the two `gates merge` makes for itself included. The regressions: either
hook still running the lock on a ledger-only commit, and either hook
skipping it when a test edit rides along with a ledger row.

Real hooks driven against real repositories: the tool-level hook reads its
command from stdin and the git-layer hook is the shipped template, and what
is under test is which checks each runs on the staged index.

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
GATES_SHIM = REPO / "bin" / "gates"
TOOL_HOOK = REPO / "hooks" / "gate-commit.sh"
GIT_HOOK = REPO / "templates" / "git-hooks" / "pre-commit"

CHANGE = "demo-change"
LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "false"\n'
TEST_REL = "tests/test_calc.py"
TEST_V1 = "def test_add():\n    assert add(2, 3) == 5\n"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env())


def _tool_hook(root):
    return subprocess.run(
        ["bash", str(TOOL_HOOK)], cwd=root, env=_env(), capture_output=True, text=True,
        input=json.dumps({"tool_input": {"command": "git commit -m x"}, "cwd": str(root)}),
    )


def _git_hook(root):
    return subprocess.run(["bash", str(GIT_HOOK)], cwd=root, env=_env(),
                          capture_output=True, text=True)


HOOKS = (("tool", _tool_hook), ("git", _git_hook))


def _locked_repo(tmp) -> Path:
    """A change branch whose lock fails at the index: task 1.1's tests are
    placed and committed with no red `unit` run after the placement (the
    shape of #56's tasks 3.1 and 5.1)."""
    root = Path(tmp)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    change_dir = root / "openspec" / "changes" / CHANGE
    change_dir.mkdir(parents=True)
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "checkout", "-q", "-b", CHANGE)
    held = root / ".gatedloop" / "authored" / CHANGE / "1.1" / f"{TEST_REL}.authored"
    held.parent.mkdir(parents=True)
    held.write_text(TEST_V1)
    for args in (("tests", "handoff", CHANGE), ("task", "start", "1.1"),
                 ("tests", "place", "1.1")):
        r = _gates(root, *args)
        assert r.returncode == 0, r.stdout + r.stderr
    (root / "src.py").write_text("def add(a, b):\n    return a + b\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "--no-verify", "-m", "task 1.1, committed past the hooks")
    return root


def _append_row(root, row):
    with (root / LEDGER).open("a") as f:
        f.write(json.dumps({"change": CHANGE, "ts": "2026-10-27T00:00:00+00:00", **row}) + "\n")


class LedgerGradeSkipsTheLockTest(unittest.TestCase):
    def test_the_lock_fails_at_the_index_in_the_arranged_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _locked_repo(tmp)
            _append_row(root, {"gate": "halt", "task": "1.1", "cause": "other",
                               "detail": "waiting on a source"})
            _git(root, "add", LEDGER)

            r = _gates(root, "tests", "check")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_a_ledger_only_commit_is_allowed_by_both_hooks(self):
        for name, hook in HOOKS:
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = _locked_repo(tmp)
                _append_row(root, {"gate": "halt", "task": "1.1", "cause": "other",
                                   "detail": "waiting on a source"})
                _git(root, "add", LEDGER)

                r = hook(root)

                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertNotIn("authored tests check failed", r.stdout + r.stderr)

    def test_a_ledger_row_staged_with_an_edited_placed_test_is_refused_by_both(self):
        for name, hook in HOOKS:
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = _locked_repo(tmp)
                (root / TEST_REL).write_text(TEST_V1.replace("5", "6"))
                _git(root, "add", TEST_REL)
                ci = _gates(root, "run", "ci")
                self.assertEqual(ci.returncode, 0, ci.stdout + ci.stderr)
                _git(root, "add", LEDGER)

                r = hook(root)

                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn(TEST_REL, r.stderr)


if __name__ == "__main__":
    unittest.main()
