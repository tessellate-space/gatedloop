"""The attempt budget follows the commit gate (openspec change `ci-at`, design
D5; the retry-budget delta's "Failed attempts are counted from the ledger"
requirement).

Under `loop.ci-at: ready` the commit gate is `unit`, so a red `unit` after a
task's RED run is a failed attempt even when the task's oracle is another
gate. The regressions: that red not counting under `ready`, counting under
`task`, an untagged task's red `unit` counting twice, and the READY `ci`
(with every task checked in HEAD) refused by a task's spent budget.

The count is the pure `_attempt_state(rows, task, gate, commit_gate)`; the
READY `ci` is driven black-box through `gates run ci` on a real repository.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
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

_loader = importlib.machinery.SourceFileLoader("gates_shim_ci_at_budget", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "ready-budget"
LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"


def placed(task):
    return {"gate": "tests-placed", "task": task, "tests": {task: {"t.py": "b" * 40}}}


def run(name, task, rc):
    return {"gate": name, "task": task, "exit": rc}


class TestTheCommitGateCounts(unittest.TestCase):
    def test_a_red_unit_after_an_integration_tasks_red_run_counts_under_ready(self):
        rows = [placed("5.1"), run("integration", "5.1", 1), run("unit", "5.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration", "unit"), (True, 1))

    def test_it_does_not_count_under_task(self):
        rows = [placed("5.1"), run("integration", "5.1", 1), run("unit", "5.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration", "ci"), (True, 0))
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration"), (True, 0))

    def test_a_red_ci_still_counts_under_ready(self):
        rows = [placed("5.1"), run("integration", "5.1", 1), run("ci", "5.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration", "unit"), (True, 1))

    def test_an_untagged_tasks_red_unit_counts_once(self):
        rows = [placed("1.1"), run("unit", "1.1", 1), run("unit", "1.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "1.1", "unit", "unit"), (True, 1))

    def test_a_red_unit_before_the_red_run_does_not_count(self):
        rows = [placed("5.1"), run("unit", "5.1", 1), run("integration", "5.1", 1)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration", "unit"), (True, 0))

    def test_exit_75_on_the_commit_gate_never_counts(self):
        rows = [placed("5.1"), run("integration", "5.1", 1), run("unit", "5.1", 75)]
        self.assertEqual(gates._attempt_state(rows, "5.1", "integration", "unit"), (True, 0))

    def test_the_refusal_reads_the_mode_from_the_manifest(self):
        rows = [placed("5.1"), run("integration", "5.1", 1),
                run("unit", "5.1", 1), run("unit", "5.1", 1)]
        ready = {"loop": {"ci-at": "ready"}}
        self.assertIsNotNone(gates._budget_refusal(ready, rows, "5.1", "integration"))
        self.assertIsNone(gates._budget_refusal({}, rows, "5.1", "integration"))


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env()).stdout.strip()


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


class TestTheReadyCiIsNoTasksAttempt(unittest.TestCase):
    def test_a_red_ready_ci_is_run_and_records_no_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-q", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(
                'gatesVersion: 1\ngates:\n  ci: "false"\n  unit: "false"\n'
                "loop:\n  ci-at: ready\n")
            d = root / "openspec" / "changes" / CHANGE
            d.mkdir(parents=True)
            (d / "tasks.md").write_text("## 1. Work\n\n- [ ] 1.1 a\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "init")
            _git(root, "checkout", "-q", "-b", CHANGE)
            # Task 1.1: its RED run and two failed attempts on `unit` -- the
            # budget (default 2) is spent for it.
            ledger = root / LEDGER
            ledger.parent.mkdir(parents=True)
            with ledger.open("a") as f:
                for r in ({"gate": "tests-handoff", "task": None},
                          {"gate": "task-start", "task": "1.1", "tree": "a" * 40},
                          run("unit", "1.1", 1), run("unit", "1.1", 1),
                          run("unit", "1.1", 1)):
                    f.write(json.dumps({"change": CHANGE, **r}) + "\n")
            self.assertIsNotNone(gates._budget_refusal(
                {"loop": {"ci-at": "ready"}}, gates._read_ledger_rows(root, CHANGE), "1.1"))
            # Every task is checked and committed in HEAD.
            (d / "tasks.md").write_text("## 1. Work\n\n- [x] 1.1 a\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "--no-verify", "-m", "1.1")

            r = _gates(root, "run", "ci")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertNotIn("attempt budget", r.stderr)
            last = json.loads(ledger.read_text().splitlines()[-1])
            self.assertEqual(last["gate"], "ci")
            self.assertIsNone(last["task"])


if __name__ == "__main__":
    unittest.main()
