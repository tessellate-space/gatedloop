"""The lock reads the task's declared gate (openspec change `task-oracle`,
design D2 and D4; the test-discipline delta's "The lock reads the task's
declared gate" requirement and its scenarios).

For a task tagged with a gate, the red-run condition is a red run of that gate
for the task after placement; a `characterization` tag needs the first verdict
on that gate to be green. An untagged task keeps the `unit` rule. The staged
check (`gates tests check`) and the commit check (`--ref`) apply the same rule,
reading the tag from the tree they evaluate.

Stdlib only, per `zero-dep-shim`. Throwaway git repositories; the shim is
driven as a subprocess, as the loop and the commit hooks drive it. A gate's
verdict is chosen by swapping the manifest for one run, then restoring it, so
the staged tree never carries a manifest edit.

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
CHANGE = "oracle-lock"


def _manifest(unit="true", integration="true"):
    return (
        'gatesVersion: 1\n'
        'gates:\n'
        '  ci: "true"\n'
        f'  unit: "{unit}"\n'
        f'  integration: "{integration}"\n'
    )


BASE = _manifest()

TASKS = """\
## 1. Work

- [ ] 1.1 Add the parser
- [ ] 3.1 Verify the data an earlier task wrote [oracle: integration characterization]
- [ ] 5.1 Wire the e2e step [oracle: integration]
"""


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=60)


def _repo(tmp):
    """A change branch whose tests are handed off as the tags require, and
    committed."""
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml", BASE)
    _write(root, "src/app.py", "def app():\n    return 1\n")
    change = f"openspec/changes/{CHANGE}"
    _write(root, f"{change}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"{change}/tasks.md", TASKS)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    held = root / ".gatedloop" / "authored" / CHANGE
    _write(held, "1.1/tests/test_parse.py.authored", "def test_parse():\n    assert False\n")
    _write(held, "3.1/tests/test_data.py.authored", "def test_data():\n    assert True\n")
    _write(held, "3.1/CHARACTERIZATION", "pins the data an earlier task wrote\n")
    _write(held, "5.1/tests/test_e2e.py.authored", "def test_e2e():\n    assert False\n")
    handoff = _gates(root, "tests", "handoff", CHANGE)
    assert handoff.returncode == 0, handoff.stderr
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author tests")
    return root


def _start_and_place(root, task):
    assert _gates(root, "task", "start", task).returncode == 0
    placed = _gates(root, "tests", "place", task)
    assert placed.returncode == 0, placed.stderr


def _run(root, gate, task, manifest):
    _write(root, ".gates.yaml", manifest)
    result = _gates(root, "run", gate, "--task", task)
    _write(root, ".gates.yaml", BASE)
    return result


def _implement_and_stage(root, task):
    _write(root, "src/app.py", f"def app():\n    return 2  # {task}\n")
    _git(root, "add", "-A")


def _check(root):
    return _gates(root, "tests", "check")


def _commit_and_check_ref(root, task):
    _implement_and_stage(root, task)
    _git(root, "commit", "-m", f"task {task}")
    return _gates(root, "tests", "check", "--ref", "HEAD", "--change", CHANGE)


class TestAnIntegrationTaggedTask(unittest.TestCase):
    """Regressions guarded: an e2e task's red run on the gate that actually
    runs its tests refused for lacking a `unit` red it can never produce (#56
    5.1), and a red `unit` run accepted for it although `unit` never ran the
    e2e tests."""

    def test_red_on_its_gate_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "5.1")
            self.assertNotIn(_run(root, "integration", "5.1",
                                  _manifest(integration="false")).returncode, (0, 75))
            _implement_and_stage(root, "5.1")
            result = _check(root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_red_only_on_unit_is_refused_naming_the_right_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "5.1")
            self.assertNotIn(_run(root, "unit", "5.1",
                                  _manifest(unit="false")).returncode, (0, 75))
            _implement_and_stage(root, "5.1")
            result = _check(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("gates run integration --task 5.1", result.stderr)

    def test_a_precondition_failure_on_its_gate_is_not_a_red_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "5.1")
            down = BASE.replace('  integration: "true"\n',
                                '  integration:\n    run: "false"\n    requires: "false"\n')
            self.assertEqual(_run(root, "integration", "5.1", down).returncode, 75)
            _implement_and_stage(root, "5.1")
            result = _check(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("gates run integration --task 5.1", result.stderr)

    def test_the_commit_check_applies_the_same_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "5.1")
            _run(root, "integration", "5.1", _manifest(integration="false"))
            result = _commit_and_check_ref(root, "5.1")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_commit_check_refuses_a_unit_only_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "5.1")
            _run(root, "unit", "5.1", _manifest(unit="false"))
            result = _commit_and_check_ref(root, "5.1")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("integration", result.stderr)
            self.assertIn("5.1", result.stderr)


class TestACharacterizationTaskOnAnotherGate(unittest.TestCase):
    """Regression guarded: a characterization task whose tests run under a
    gate other than `unit` refused for lacking a green `unit` run."""

    def test_a_green_first_verdict_on_its_gate_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "3.1")
            self.assertEqual(_run(root, "integration", "3.1", BASE).returncode, 0)
            _implement_and_stage(root, "3.1")
            result = _check(root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_red_first_verdict_on_its_gate_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "3.1")
            _run(root, "integration", "3.1", _manifest(integration="false"))
            _run(root, "integration", "3.1", BASE)
            _implement_and_stage(root, "3.1")
            result = _check(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("3.1", result.stderr)
            self.assertIn("integration", result.stderr)

    def test_a_green_unit_run_alone_does_not_satisfy_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "3.1")
            self.assertEqual(_run(root, "unit", "3.1", BASE).returncode, 0)
            _implement_and_stage(root, "3.1")
            result = _check(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("gates run integration --task 3.1", result.stderr)


class TestAnUntaggedTask(unittest.TestCase):
    """Regression guarded: the change altering the lock for plans that
    declare nothing."""

    def test_a_red_unit_run_still_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "1.1")
            _run(root, "unit", "1.1", _manifest(unit="false"))
            _implement_and_stage(root, "1.1")
            result = _check(root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_red_integration_run_alone_is_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _start_and_place(root, "1.1")
            _run(root, "integration", "1.1", _manifest(integration="false"))
            _implement_and_stage(root, "1.1")
            result = _check(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("gates run unit --task 1.1", result.stderr)


if __name__ == "__main__":
    unittest.main()
