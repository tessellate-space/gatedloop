"""Fresh-worktree setup hint (design D7 of `worktree-native-loop`, task
7.1). A gate failing in a worktree with no prior recorded gate history
earns one stack-agnostic line pointing at the adopter's own manifest --
printed at most once per worktree, never touching the gate's own exit code.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

FAILING_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "false"\n'
PASSING_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: Path, manifest: str) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


HINT_TEXT = "this worktree looks fresh"


class TestFirstFailureHints(unittest.TestCase):
    def test_first_failing_gate_in_a_fresh_worktree_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, FAILING_MANIFEST)
            r = _run_gates(root, "run", "ci")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(HINT_TEXT, r.stderr)

    def test_exit_code_is_unchanged_by_the_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, FAILING_MANIFEST)
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 1)


class TestSecondFailureDoesNotHint(unittest.TestCase):
    def test_second_failure_in_the_same_worktree_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, FAILING_MANIFEST)
            first = _run_gates(root, "run", "ci")
            self.assertIn(HINT_TEXT, first.stderr)

            second = _run_gates(root, "run", "ci")
            self.assertNotEqual(second.returncode, 0)
            self.assertNotIn(HINT_TEXT, second.stderr)


class TestEstablishedWorktreeNeverHints(unittest.TestCase):
    def test_a_worktree_with_a_prior_green_gate_never_hints_on_a_later_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, PASSING_MANIFEST)
            green = _run_gates(root, "run", "ci")
            self.assertEqual(green.returncode, 0)

            # Now the gate command itself starts failing (e.g. a real test
            # regression) -- this worktree has history, so no hint.
            (root / ".gates.yaml").write_text(FAILING_MANIFEST)
            failing = _run_gates(root, "run", "ci")
            self.assertNotEqual(failing.returncode, 0)
            self.assertNotIn(HINT_TEXT, failing.stderr)


class TestHintNamesNoStack(unittest.TestCase):
    def test_hint_names_only_the_manifest_never_a_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, FAILING_MANIFEST)
            r = _run_gates(root, "run", "ci")
            self.assertIn(".gates.yaml", r.stderr)
            for banned in ("npm", "pytest", "pip", "cargo", "make", "yarn", "poetry"):
                self.assertNotIn(banned, r.stderr.lower())


if __name__ == "__main__":
    unittest.main()
