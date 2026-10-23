"""The `CHARACTERIZATION` declaration in the authored-tests holding area
(authored-test-kinds design D1): recorded in the handoff row, refused beside
`NO-TESTS`, placed like any authored test, and locked.

Stdlib only, per `zero-dep-shim`. Builds throwaway git repos under a temp
directory and drives the shim as a subprocess, then reads the ledger back.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_char_handoff", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "demo-change"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
REASON = "pins the report's current output before the refactor"
TEST_V1 = "def test_add():\n    assert add(2, 3) == 5\n"


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


def _rows(root):
    p = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _handoffs(root):
    return [r for r in _rows(root) if r["gate"] == "tests-handoff"]


def _repo(tmp):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    (root / "src").mkdir()
    (root / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    change_dir = root / "openspec" / "changes" / CHANGE
    change_dir.mkdir(parents=True)
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    return root


def _holding(root, task):
    return root / ".gatedloop" / "authored" / CHANGE / task


def _hold(root, task, path, content):
    p = _holding(root, task) / f"{path}.authored"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _marker(root, task, name, text):
    p = _holding(root, task) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text + "\n")


def _characterize(root, task, reason=REASON):
    _marker(root, task, "CHARACTERIZATION", reason)


class TestHandoffRecordsTheDeclaration(unittest.TestCase):
    """Regressions guarded: a declaration the handoff drops (the commit check
    then demands a red run the task can never produce), or one recorded as a
    behaviour-free reason instead of beside the task's tests."""

    def test_reason_recorded_beside_the_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _hold(root, "1.1", "tests/test_calc.py", TEST_V1)
            _characterize(root, "1.1")
            _marker(root, "1.2", "NO-TESTS", "docs only")

            result = _run_gates(root, "tests", "handoff", CHANGE)

            self.assertEqual(result.returncode, 0, result.stderr)
            (row,) = _handoffs(root)
            self.assertEqual(row["characterization"], {"1.1": REASON})
            self.assertIn("tests/test_calc.py", row["tests"]["1.1"])
            self.assertEqual(row["no_behaviour"], {"1.2": "docs only"})

    def test_task_rehandoff_replaces_the_declaration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _hold(root, "1.1", "tests/test_calc.py", TEST_V1)
            _characterize(root, "1.1")
            self.assertEqual(_run_gates(root, "tests", "handoff", CHANGE).returncode, 0)
            (_holding(root, "1.1") / "CHARACTERIZATION").unlink()

            result = _run_gates(root, "tests", "handoff", CHANGE, "--task", "1.1")

            self.assertEqual(result.returncode, 0, result.stderr)
            state = gates._authoring_state(_rows(root))
            self.assertEqual(state["characterization"], {})
            self.assertIn("1.1", state["tests"])


class TestHandoffRefusesWhatTheLockCannotHold(unittest.TestCase):
    """Regressions guarded: a task declared both ways, a characterization
    claim with nothing to pin, and a claim with no reason for review to
    judge, each reaching the ledger."""

    def test_refusals_name_the_task_and_write_nothing(self):
        cases = {
            "CHARACTERIZATION and NO-TESTS": lambda root: (
                _hold(root, "1.1", "tests/test_calc.py", TEST_V1),
                _characterize(root, "1.1"),
                _marker(root, "1.1", "NO-TESTS", "docs only")),
            "CHARACTERIZATION with no tests": lambda root: (
                _hold(root, "1.2", "tests/test_other.py", TEST_V1),
                _characterize(root, "1.1")),
            "an empty reason": lambda root: (
                _hold(root, "1.1", "tests/test_calc.py", TEST_V1),
                _characterize(root, "1.1", reason="   ")),
        }
        for name, arrange in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp)
                arrange(root)
                result = _run_gates(root, "tests", "handoff", CHANGE)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("1.1", result.stderr)
                self.assertIn("CHARACTERIZATION", result.stderr)
                self.assertEqual(_handoffs(root), [])


def _authored(root):
    _hold(root, "1.1", "tests/test_calc.py", TEST_V1)
    _characterize(root, "1.1")
    _hold(root, "1.2", "tests/test_more.py", TEST_V1)
    result = _run_gates(root, "tests", "handoff", CHANGE)
    assert result.returncode == 0, result.stderr
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author tests")


class TestPlacement(unittest.TestCase):
    """Regression guarded: a characterization task placed differently from
    any other (its tests left held, or its declaration left behind in the
    holding area), and a placement message that sends the implementer
    looking for a red run it can never get."""

    def test_places_the_tests_removes_the_declaration_and_asks_for_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _authored(root)

            result = _run_gates(root, "tests", "place", "1.1")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "tests" / "test_calc.py").read_text(), TEST_V1)
            self.assertFalse(_holding(root, "1.1").exists())
            self.assertIn("characterization", result.stdout)
            self.assertIn("pass", result.stdout)
            self.assertNotIn("must fail", result.stdout)


class TestTheDeclarationIsLocked(unittest.TestCase):
    """Design D1: only the authoring phase writes the declaration. Regression
    guarded: an implementer adding one to a held task, or rewording one,
    and the commit check letting it through."""

    def test_adding_a_declaration_after_handoff_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _authored(root)
            _characterize(root, "1.2")
            _git(root, "add", "-A")

            result = _run_gates(root, "tests", "check")

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("1.2/CHARACTERIZATION", result.stderr)

    def test_rewording_a_held_declaration_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _authored(root)
            _characterize(root, "1.1", reason="something else entirely")
            _git(root, "add", "-A")

            result = _run_gates(root, "tests", "check")

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("1.1/CHARACTERIZATION", result.stderr)

    def test_the_untouched_authoring_commit_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _authored(root)
            result = _run_gates(root, "tests", "check")
            self.assertEqual(result.returncode, 0, result.stderr)


class TestLedgerRowCarriesTheDeclaration(unittest.TestCase):
    """Regression guarded: the fixed-shape row writer dropping the new
    field, so the declaration never survives the holding file's removal."""

    def test_written_row_keeps_characterization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gates._append_ledger_row(root, {
                "gate": "tests-handoff", "change": CHANGE, "author": "separate",
                "tests": {"1.1": {"tests/test_calc.py": "abc"}},
                "characterization": {"1.1": REASON},
            })
            (row,) = _rows(root)
        self.assertEqual(row["characterization"], {"1.1": REASON})


if __name__ == "__main__":
    unittest.main()
