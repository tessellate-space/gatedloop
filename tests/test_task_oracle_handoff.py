"""`gates tests handoff` refuses a holding area that contradicts the plan's
oracle tags, and `loop.task-oracle: required` refuses an untagged task
(openspec change `task-oracle`, design D3 and D6; the test-discipline delta's
"The handoff refuses a declaration that contradicts the plan" and "A project
may require every task to declare its oracle" requirements).

Stdlib only, per `zero-dep-shim`. A throwaway git repository per case; the
shim is driven as a subprocess, as the test author drives it.

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
CHANGE = "tagged-change"

MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n'
    '  ci: "true"\n'
    '  unit: "true"\n'
    '  integration: "true"\n'
)

TASKS = """\
## 1. Work

- [ ] 1.1 Add the parser [oracle: unit]
- [ ] 3.1 Verify the data an earlier task wrote [oracle: unit characterization]
- [ ] 4.2 Edit the prompt [oracle: none]
- [ ] 5.1 Wire the e2e step [oracle: integration]
"""

RED = "def test_x():\n    assert False\n"
GUARD = "def test_x():\n    assert True\n"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                   env=_env())


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=60)


def _project(tmp, tasks=TASKS, manifest=MANIFEST):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml", manifest)
    change = f"openspec/changes/{CHANGE}"
    _write(root, f"{change}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"{change}/tasks.md", tasks)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    return root


def _held(root):
    return root / ".gatedloop" / "authored" / CHANGE


def _consistent(root):
    """A holding area that agrees with every tag in TASKS."""
    held = _held(root)
    _write(held, "1.1/tests/test_parse.py.authored", RED)
    _write(held, "3.1/tests/test_data.py.authored", GUARD)
    _write(held, "3.1/CHARACTERIZATION", "pins the data task 1.1 already wrote\n")
    _write(held, "4.2/NO-TESTS", "a prompt edit; no behaviour a test can see\n")
    _write(held, "5.1/tests/test_e2e.py.authored", RED)


def _handoff(root, *extra):
    return _gates(root, "tests", "handoff", CHANGE, *extra)


def _handoff_recorded(root):
    ledger = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
    return ledger.exists() and '"tests-handoff"' in ledger.read_text()


class TestAConsistentHoldingArea(unittest.TestCase):
    """Regression guarded: a holding area that matches the plan refused."""

    def test_is_handed_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            result = _handoff(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(_handoff_recorded(root))


class TestTheFourContradictions(unittest.TestCase):
    """Regression guarded: the author choosing its own oracle against the one
    the plan declared, which is what the tag exists to prevent."""

    def _refused(self, mutate, task, *needles, extra=()):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            mutate(_held(root))
            result = _handoff(root, *extra)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(task, result.stderr)
            for n in needles:
                self.assertIn(n, result.stderr)
            self.assertFalse(_handoff_recorded(root), "a refused handoff writes nothing")

    def test_tests_for_a_none_task(self):
        def mutate(held):
            (held / "4.2" / "NO-TESTS").unlink()
            _write(held, "4.2/tests/test_prompt.py.authored", RED)
        self._refused(mutate, "4.2", "[oracle: none]")

    def test_no_tests_for_a_gate_tagged_task(self):
        def mutate(held):
            (held / "1.1" / "tests" / "test_parse.py.authored").unlink()
            _write(held, "1.1/NO-TESTS", "nothing to test\n")
        self._refused(mutate, "1.1", "[oracle: unit]", "NO-TESTS")

    def test_a_characterization_task_without_the_marker(self):
        def mutate(held):
            (held / "3.1" / "CHARACTERIZATION").unlink()
        self._refused(mutate, "3.1", "CHARACTERIZATION")

    def test_e2e_tests_declared_characterization(self):
        def mutate(held):
            _write(held, "5.1/CHARACTERIZATION", "an e2e step the unit gate never runs\n")
        self._refused(mutate, "5.1", "red `integration` run first")

    def test_a_single_task_rehandoff_is_held_to_its_tag_too(self):
        def mutate(held):
            (held / "4.2" / "NO-TESTS").unlink()
            _write(held, "4.2/tests/test_prompt.py.authored", RED)
        self._refused(mutate, "4.2", "[oracle: none]", extra=("--task", "4.2"))


UNTAGGED = """\
## 2. Work

- [ ] 2.1 Add the parser [oracle: unit]
- [ ] 2.3 Wire it up
"""


def _untagged_holding(root):
    held = _held(root)
    _write(held, "2.1/tests/test_parse.py.authored", RED)
    _write(held, "2.3/tests/test_wire.py.authored", RED)


class TestRequired(unittest.TestCase):
    """Regression guarded: a project that chose to require tags handing off
    a plan with a task whose oracle nobody declared."""

    def test_an_untagged_task_under_required_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, UNTAGGED,
                            MANIFEST + "loop:\n  task-oracle: required\n")
            _untagged_holding(root)
            result = _handoff(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("2.3", result.stderr)
            self.assertNotIn("2.1:", result.stderr)
            self.assertIn("[oracle: <gate>]", result.stderr)
            self.assertFalse(_handoff_recorded(root))

    def test_the_default_hands_off_untagged_tasks_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, UNTAGGED)
            _untagged_holding(root)
            result = _handoff(root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_optional_declared_hands_off_untagged_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, UNTAGGED,
                            MANIFEST + "loop:\n  task-oracle: optional\n")
            _untagged_holding(root)
            result = _handoff(root)
            self.assertEqual(result.returncode, 0, result.stderr)


class TestTheKey(unittest.TestCase):
    """Regression guarded: a typo in the key's value silently leaving the
    project on the default it meant to change."""

    def _validate(self, value):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, UNTAGGED, MANIFEST + f"loop:\n  task-oracle: {value}\n")
            return _gates(root, "validate")

    def test_an_unknown_value_fails_validation(self):
        result = self._validate("sometimes")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("loop.task-oracle", result.stderr)

    def test_both_known_values_validate(self):
        for value in ("optional", "required"):
            with self.subTest(value=value):
                result = self._validate(value)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
