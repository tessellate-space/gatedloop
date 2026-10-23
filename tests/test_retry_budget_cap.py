"""The attempt cap, enforced from the ledger (openspec change `retry-budget`,
design D1 and D2; the retry-budget delta's "The attempt cap is enforced from
the ledger" requirement).

Stdlib only, per `zero-dep-shim`. The count is a pure function of ledger rows
(`failed_attempt_count(rows, task)`), tested directly; the refusal is tested
black-box by driving `gates run` as a subprocess in a throwaway git repo whose
ledger is seeded with the rows a loop would have written. The gate command
touches a `ran` file, so "refused without running the gate" is observable.

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

_loader = importlib.machinery.SourceFileLoader("gates_shim_retry_budget_cap", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "my-change"
GATE_CMD = "sh -c 'touch ran; exit $(cat rc)'"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _manifest(loop_block=""):
    return (f'gatesVersion: 1\ngates:\n  ci: "{GATE_CMD}"\n  unit: "{GATE_CMD}"\n'
            + loop_block)


def _repo(tmp, loop_block=""):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(_manifest(loop_block))
    (root / ".gitignore").write_text("rc\nran\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    (root / "openspec" / "changes" / CHANGE).mkdir(parents=True)
    (root / "rc").write_text("1")
    return root


def _ledger(root):
    return root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"


def _rows(root):
    p = _ledger(root)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _seed(root, rows):
    p = _ledger(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        for r in rows:
            full = {"change": CHANGE, "ts": "2026-10-01T00:00:00+00:00"}
            full.update(r)
            f.write(json.dumps(full) + "\n")


def _run(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def start(task):
    return {"gate": "task-start", "task": task, "tree": "t" * 40}


def gate(name, task, rc):
    return {"gate": name, "task": task, "exit": rc}


def restart(task):
    return {"gate": "restart", "task": task}


class TestFailedAttemptCount(unittest.TestCase):
    def test_the_red_run_is_not_an_attempt(self):
        rows = [start("1.2"), gate("unit", "1.2", 1)]
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 0)

    def test_reds_after_the_red_run_count(self):
        rows = [start("1.2"), gate("unit", "1.2", 1), gate("unit", "1.2", 1),
                gate("ci", "1.2", 2)]
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 2)

    def test_exit_75_is_never_an_attempt(self):
        rows = [start("1.2"), gate("unit", "1.2", 1), gate("unit", "1.2", 75),
                gate("ci", "1.2", 75)]
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 0)

    def test_exit_75_is_not_the_red_run_either(self):
        rows = [start("1.2"), gate("unit", "1.2", 75), gate("unit", "1.2", 1),
                gate("unit", "1.2", 1)]
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 1)

    def test_a_green_run_does_not_reset_the_count(self):
        rows = [start("1.2"), gate("unit", "1.2", 1), gate("unit", "1.2", 1),
                gate("unit", "1.2", 0), gate("ci", "1.2", 1)]
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 2)

    def test_other_tasks_and_other_gates_do_not_count(self):
        rows = [start("1.2"), gate("unit", "1.2", 1), gate("unit", "1.1", 1),
                gate("live-check", "1.2", 1), gate("verify", "1.2", 1)]
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 0)

    def test_counted_from_the_latest_task_start(self):
        rows = [start("1.2"), gate("unit", "1.2", 1), gate("unit", "1.2", 1),
                gate("unit", "1.2", 1), start("1.2"), gate("unit", "1.2", 1),
                gate("unit", "1.2", 1)]
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 1)

    def test_a_restart_resets_the_count(self):
        rows = [start("1.2"), gate("unit", "1.2", 1), gate("unit", "1.2", 1),
                gate("unit", "1.2", 1), restart("1.2")]
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 0)
        rows.append(gate("unit", "1.2", 1))
        self.assertEqual(gates.failed_attempt_count(rows, "1.2"), 1)


class TestRefusal(unittest.TestCase):
    USED = [start("1.2"), gate("unit", "1.2", 1), gate("unit", "1.2", 1),
            gate("unit", "1.2", 1)]

    def test_budget_used_refuses_without_running_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, self.USED)
            before = len(_rows(root))
            r = _run(root, "run", "unit", "--task", "1.2", "--attempt", "4")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse((root / "ran").exists(), "the gate ran despite the budget")
            self.assertEqual(len(_rows(root)), before, "a refusal writes no ledger row")
            out = r.stdout + r.stderr
            self.assertIn("1.2", out)
            self.assertIn("2", out)
            self.assertIn("gates attempt restart 1.2", out)
            self.assertIn("stalled", out)

    def test_ci_is_refused_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, self.USED)
            r = _run(root, "run", "ci", "--task", "1.2")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse((root / "ran").exists())

    def test_the_callers_attempt_number_buys_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, self.USED)
            r = _run(root, "run", "unit", "--task", "1.2", "--attempt", "1")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse((root / "ran").exists())

    def test_under_budget_the_gate_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, [start("1.2"), gate("unit", "1.2", 1), gate("unit", "1.2", 1)])
            r = _run(root, "run", "unit", "--task", "1.2", "--attempt", "3")
            self.assertEqual(r.returncode, 1)
            self.assertTrue((root / "ran").exists(), "one attempt remained; the gate must run")
            self.assertEqual(_rows(root)[-1]["gate"], "unit")

    def test_the_red_run_itself_is_never_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "loop:\n  attempts: 0\n")
            _seed(root, [start("1.2")])
            r = _run(root, "run", "unit", "--task", "1.2", "--attempt", "1")
            self.assertEqual(r.returncode, 1)
            self.assertTrue((root / "ran").exists())

    def test_declared_budget_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "loop:\n  attempts: 3\n")
            _seed(root, self.USED)
            r = _run(root, "run", "unit", "--task", "1.2")
            self.assertTrue((root / "ran").exists(), "3 attempts declared, 2 used")
            r = _run(root, "run", "unit", "--task", "1.2")
            self.assertEqual(r.returncode, 1)
            (root / "ran").unlink()
            r = _run(root, "run", "unit", "--task", "1.2")
            self.assertEqual(r.returncode, 1)
            self.assertFalse((root / "ran").exists())

    def test_message_without_a_restart_remaining_names_only_the_halt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "loop:\n  fresh-restarts: 0\n")
            _seed(root, self.USED)
            r = _run(root, "run", "unit", "--task", "1.2")
            self.assertEqual(r.returncode, 1)
            out = r.stdout + r.stderr
            self.assertNotIn("gates attempt restart", out)
            self.assertIn("stalled", out)

    def test_message_after_the_restart_is_used_names_only_the_halt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, self.USED + [restart("1.2"), gate("unit", "1.2", 1),
                                     gate("unit", "1.2", 1)])
            r = _run(root, "run", "unit", "--task", "1.2")
            self.assertEqual(r.returncode, 1)
            self.assertFalse((root / "ran").exists())
            out = r.stdout + r.stderr
            self.assertNotIn("gates attempt restart", out)
            self.assertIn("stalled", out)

    def test_a_run_with_no_task_and_no_task_started_is_never_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, [gate("ci", None, 1)] * 5)
            r = _run(root, "run", "ci")
            self.assertTrue((root / "ran").exists(), "no task: no budget applies")
            self.assertEqual(r.returncode, 1)

    def test_a_run_without_task_is_budgeted_against_the_started_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed(root, self.USED)
            r = _run(root, "run", "ci")
            self.assertEqual(r.returncode, 1)
            self.assertFalse((root / "ran").exists(),
                             "the started task's budget applies when --task is omitted")


if __name__ == "__main__":
    unittest.main()
