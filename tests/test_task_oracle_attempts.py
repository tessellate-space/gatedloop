"""Failed attempts are counted from the first red run on the task's oracle
gate (openspec change `task-oracle`, design D4; the retry-budget delta's
"Failed attempts are counted from the ledger" requirement and its "An e2e
task's red run" scenario).

The count is a pure function of ledger rows and the task's oracle gate,
`_attempt_state(rows, task, gate)` (`gate` defaults to `unit`), tested
directly; the budget refusal is tested black-box: `gates run ci --task`
reads the tag from the change's `tasks.md`.

Stdlib only, per `zero-dep-shim`.

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

_loader = importlib.machinery.SourceFileLoader("gates_shim_task_oracle_attempts", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "oracle-budget"
GATE_CMD = "sh -c 'touch ran; exit $(cat rc)'"


def placed(task):
    return {"gate": "tests-placed", "task": task, "tests": {task: {"t.py": "b" * 40}}}


def run(name, task, rc):
    return {"gate": name, "task": task, "exit": rc}


class TestAnIntegrationTaggedTasksWindow(unittest.TestCase):
    """Regressions guarded: an e2e task's budget never starting, because its
    window waited for a red `unit` run that `unit` cannot produce for it; and
    its red runs on its own gate not counting as attempts."""

    def test_the_first_red_on_its_gate_is_the_red_run(self):
        rows = [placed("5.1"), run("integration", "5.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration"), (True, 0))

    def test_later_reds_on_its_gate_and_on_ci_count(self):
        rows = [placed("5.1"), run("integration", "5.1", 1), run("integration", "5.1", 1),
                run("ci", "5.1", 2)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration"), (True, 2))

    def test_red_unit_runs_neither_open_the_window_nor_count(self):
        rows = [placed("5.1"), run("unit", "5.1", 1), run("integration", "5.1", 1),
                run("unit", "5.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration"), (True, 0))

    def test_a_red_ci_before_the_red_run_does_not_count(self):
        rows = [placed("5.1"), run("ci", "5.1", 1), run("integration", "5.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration"), (True, 0))

    def test_exit_75_on_its_gate_is_neither_the_red_run_nor_an_attempt(self):
        rows = [placed("5.1"), run("integration", "5.1", 75), run("integration", "5.1", 1),
                run("integration", "5.1", 75)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration"), (True, 0))


class TestAnUntaggedTasksWindowIsUnchanged(unittest.TestCase):
    """Regression guarded: the change altering the count for untagged tasks."""

    def test_the_default_gate_is_unit(self):
        rows = [placed("1.1"), run("unit", "1.1", 1), run("ci", "1.1", 1),
                run("unit", "1.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "1.1"), (True, 2))
        self.assertEqual(gates._attempt_state(rows, "1.1", "unit"), (True, 2))

    def test_an_integration_red_is_no_red_run_for_it(self):
        rows = [placed("1.1"), run("integration", "1.1", 1), run("ci", "1.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "1.1"), (False, 0))


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                   env=_env())


def _repo(tmp, tag):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(
        f'gatesVersion: 1\ngates:\n  ci: "{GATE_CMD}"\n  unit: "{GATE_CMD}"\n'
        f'  integration: "{GATE_CMD}"\n')
    (root / ".gitignore").write_text("rc\nran\n")
    change = root / "openspec" / "changes" / CHANGE
    change.mkdir(parents=True)
    (change / "tasks.md").write_text(f"## 5. E2e\n\n- [ ] 5.1 Wire the e2e step{tag}\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    (root / "rc").write_text("1")
    ledger = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        for r in [{"gate": "task-start", "task": "5.1", "tree": "t" * 40},
                  run("integration", "5.1", 1), run("ci", "5.1", 1), run("ci", "5.1", 1)]:
            f.write(json.dumps({"change": CHANGE, "ts": "2026-10-01T00:00:00+00:00", **r}) + "\n")
    return root


def _ci(root):
    return subprocess.run([sys.executable, str(GATES_SHIM), "run", "ci", "--task", "5.1"],
                          cwd=root, capture_output=True, text=True, env=_env(), timeout=120)


class TestTheRefusalReadsTheTag(unittest.TestCase):
    """Regression guarded: the budget refusal counting an e2e task's window
    from `unit`, so a task that has spent its attempts runs on unbounded."""

    def test_an_integration_tagged_task_with_its_budget_spent_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, " [oracle: integration]")
            result = _ci(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("attempt budget", result.stderr)
            self.assertFalse((root / "ran").exists(), "the refused gate must not run")

    def test_the_same_rows_untagged_are_not_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "")
            _ci(root)
            self.assertTrue((root / "ran").exists(),
                            "no red `unit` run: an untagged task's budget has not started")


if __name__ == "__main__":
    unittest.main()
