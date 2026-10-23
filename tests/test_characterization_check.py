"""`gates tests check` for a characterization task (authored-test-kinds
design D2): the run after placement must be green, a red one there is a
defect, and the missing-run message says which run the task needs.

Stdlib only, per `zero-dep-shim`. Builds throwaway git repos under a temp
directory and drives the shim as a subprocess, as the loop and the commit
hooks do.

Run with:  python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

CHANGE = "demo-change"
GREEN = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
RED = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "false"\n'
PRECONDITION = (
    'gatesVersion: 1\ngates:\n  ci: "true"\n'
    '  unit:\n    run: "true"\n    requires: "false"\n'
)
GUARD = "def test_report_unchanged():\n    assert report() == 'ok'\n"
NEW = "def test_add():\n    assert add(2, 3) == 5\n"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=_env(),
    )


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True, env=_env(),
    )


def _hold(root, task, path, content):
    p = root / ".gatedloop" / "authored" / CHANGE / task / f"{path}.authored"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _characterize(root, task):
    p = root / ".gatedloop" / "authored" / CHANGE / task / "CHARACTERIZATION"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("pins current output before the refactor\n")


def _manifest(root, text):
    (root / ".gates.yaml").write_text(text)


def _repo(tmp):
    """A change branch whose author declared 1.1 characterization and wrote
    ordinary red-first tests for 1.2; handed off and committed."""
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _manifest(root, GREEN)
    (root / "src").mkdir()
    (root / "src" / "calc.py").write_text("def report():\n    return 'ok'\n")
    change_dir = root / "openspec" / "changes" / CHANGE
    change_dir.mkdir(parents=True)
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    _hold(root, "1.1", "tests/test_report.py", GUARD)
    _characterize(root, "1.1")
    _hold(root, "1.2", "tests/test_calc.py", NEW)
    handoff = _run_gates(root, "tests", "handoff", CHANGE)
    assert handoff.returncode == 0, handoff.stderr
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author tests")
    return root


def _start_and_place(root, task):
    assert _run_gates(root, "task", "start", task).returncode == 0
    placed = _run_gates(root, "tests", "place", task)
    assert placed.returncode == 0, placed.stderr


def _unit(root, task, manifest):
    """One `unit` run for the task under `manifest`, which is then restored
    to the committed one so the staged tree carries no manifest edit."""
    _manifest(root, manifest)
    result = _run_gates(root, "run", "unit", "--task", task)
    _manifest(root, GREEN)
    return result


def _implement_and_stage(root, body="def report():\n    return 'ok'  # refactored\n"):
    (root / "src" / "calc.py").write_text(body)
    _git(root, "add", "-A")


def _check(root):
    return _run_gates(root, "tests", "check")


class TestCharacterizationNeedsAGreenRun(unittest.TestCase):
    """Regressions guarded: a characterization task refused for lacking the
    red run it can never produce (the friction of issue #42), and one that
    commits on tests never seen to pass on the tree as it was."""

    def test_a_green_run_after_placement_satisfies_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "1.1")
            self.assertEqual(_unit(root, "1.1", GREEN).returncode, 0)
            _implement_and_stage(root)

            result = _check(root)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_red_run_after_placement_is_refused_as_a_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "1.1")
            self.assertNotIn(_unit(root, "1.1", RED).returncode, (0, 75))
            _implement_and_stage(root)

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("task 1.1", result.stderr)
            self.assertIn("characterization", result.stderr)
            self.assertIn("gates tests defect 1.1", result.stderr)

    def test_red_then_green_is_still_refused(self):
        """The pass must be on the tree as it was, not one the implementation
        produced after a red run."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "1.1")
            self.assertNotIn(_unit(root, "1.1", RED).returncode, (0, 75))
            self.assertEqual(_unit(root, "1.1", GREEN).returncode, 0)
            _implement_and_stage(root)

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("gates tests defect 1.1", result.stderr)

    def test_a_precondition_failure_is_not_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "1.1")
            self.assertEqual(_unit(root, "1.1", PRECONDITION).returncode, 75)
            _implement_and_stage(root)
            self.assertNotEqual(_check(root).returncode, 0)

            self.assertEqual(_unit(root, "1.1", GREEN).returncode, 0)
            _git(root, "add", "-A")
            result = _check(root)

            self.assertEqual(result.returncode, 0, result.stderr)


class TestTheMissingRunMessageNamesTheRunNeeded(unittest.TestCase):
    """Regression guarded: one message for both kinds of task, so an
    implementer told 'red before green' on a characterization task goes
    looking for a failure it must never produce, or the reverse."""

    def test_characterization_task_asks_for_a_passing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "1.1")
            _git(root, "add", "-A")

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("characterization", result.stderr)
            self.assertIn("passing", result.stderr)
            self.assertNotIn("red before green", result.stderr)

    def test_ordinary_task_still_asks_for_a_failing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "1.2")
            _git(root, "add", "-A")

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("failing", result.stderr)
            self.assertNotIn("characterization", result.stderr)


class TestAMixedChange(unittest.TestCase):
    """A change with one characterization task and one ordinary task, across
    real commits. Regressions guarded: the characterization rule leaking onto
    the ordinary task (a green-only run accepted for new behaviour), or the
    ordinary rule still applied to the characterization task."""

    def _commit_1_1(self, root):
        _start_and_place(root, "1.1")
        self.assertEqual(_unit(root, "1.1", GREEN).returncode, 0)
        _implement_and_stage(root)
        result = _check(root)
        self.assertEqual(result.returncode, 0, result.stderr)
        _git(root, "commit", "-m", "task 1.1")

    def test_each_task_is_held_to_its_own_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            self._commit_1_1(root)
            _start_and_place(root, "1.2")
            self.assertNotIn(_unit(root, "1.2", RED).returncode, (0, 75))
            _implement_and_stage(root, "def report():\n    return 'ok'\n\n"
                                       "def add(a, b):\n    return a + b\n")

            result = _check(root)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_ordinary_task_is_not_excused_from_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            self._commit_1_1(root)
            _start_and_place(root, "1.2")
            self.assertEqual(_unit(root, "1.2", GREEN).returncode, 0)
            _implement_and_stage(root, "def report():\n    return 'ok'\n\n"
                                       "def add(a, b):\n    return a + b\n")

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("task 1.2", result.stderr)
            self.assertIn("failing", result.stderr)


if __name__ == "__main__":
    unittest.main()
