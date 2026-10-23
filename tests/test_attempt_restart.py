"""`gates attempt restart` and the `stalled` halt's `restart_available`
(openspec change `retry-budget`, design D4; the retry-budget delta's "A fresh
restart resets the count once, from a clean tree" requirement and the
escalation-record delta's "A stalled halt says whether a fresh restart
remains").

Stdlib only, per `zero-dep-shim`. Drives the shim as a subprocess in a
throwaway git repo; the ledger is seeded with the rows a loop would have
written and committed, so the tree is clean at the task boundary the way the
halt discipline leaves it.

Run with:  python3 -m unittest discover -s tests
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
CHANGE = "my-change"
GATE_CMD = "sh -c 'touch ran; exit $(cat rc)'"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _repo(tmp, loop_block=""):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(
        f'gatesVersion: 1\ngates:\n  ci: "{GATE_CMD}"\n  unit: "{GATE_CMD}"\n' + loop_block)
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


def _seed_and_commit(root, rows):
    p = _ledger(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        for r in rows:
            full = {"change": CHANGE, "ts": "2026-10-01T00:00:00+00:00"}
            full.update(r)
            f.write(json.dumps(full) + "\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "ledger")


def _run(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


USED = [
    {"gate": "task-start", "task": "1.2", "tree": "t" * 40},
    {"gate": "unit", "task": "1.2", "exit": 1},
    {"gate": "unit", "task": "1.2", "exit": 1},
    {"gate": "unit", "task": "1.2", "exit": 1},
]


def _restarts(root, task="1.2"):
    return [r for r in _rows(root) if r.get("gate") == "restart" and r.get("task") == task]


class TestAttemptRestart(unittest.TestCase):
    def test_a_restart_with_one_remaining_records_a_row_and_the_gate_runs_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed_and_commit(root, USED)
            r = _run(root, "run", "unit", "--task", "1.2")
            self.assertFalse((root / "ran").exists(), "precondition: the budget is used")

            r = _run(root, "attempt", "restart", "1.2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(_restarts(root)), 1)

            r = _run(root, "run", "unit", "--task", "1.2")
            self.assertTrue((root / "ran").exists(), "a restart resets the count")

    def test_no_restart_remains_refuses_naming_the_halt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed_and_commit(root, USED + [{"gate": "restart", "task": "1.2"}])
            r = _run(root, "attempt", "restart", "1.2")
            self.assertEqual(r.returncode, 1)
            self.assertIn("stalled", r.stdout + r.stderr)
            self.assertEqual(len(_restarts(root)), 1, "a refusal records nothing")

    def test_fresh_restarts_zero_disables_restarts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "loop:\n  fresh-restarts: 0\n")
            _seed_and_commit(root, USED)
            r = _run(root, "attempt", "restart", "1.2")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(_restarts(root), [])

    def test_restarts_are_counted_per_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed_and_commit(root, [{"gate": "restart", "task": "1.1"}] + USED)
            r = _run(root, "attempt", "restart", "1.2")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_dirty_tree_refuses_and_records_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed_and_commit(root, USED)
            (root / "half-done.py").write_text("x = 1\n")
            r = _run(root, "attempt", "restart", "1.2")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(_restarts(root), [])

    def test_a_staged_change_is_dirty_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed_and_commit(root, USED)
            (root / "staged.py").write_text("x = 1\n")
            _git(root, "add", "staged.py")
            r = _run(root, "attempt", "restart", "1.2")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(_restarts(root), [])


class TestStalledHaltRestartAvailable(unittest.TestCase):
    def _halt(self, root, cause="stalled"):
        r = _run(root, "halt", "record", cause, "--task", "1.2", "--detail", "budget used")
        self.assertEqual(r.returncode, 0, r.stderr)
        return [x for x in _rows(root) if x.get("gate") == "halt"][-1]

    def test_halting_with_a_restart_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed_and_commit(root, USED)
            self.assertIs(self._halt(root)["restart_available"], True)

    def test_halting_after_the_restart_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed_and_commit(root, USED + [{"gate": "restart", "task": "1.2"}])
            self.assertIs(self._halt(root)["restart_available"], False)

    def test_halting_with_restarts_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, "loop:\n  fresh-restarts: 0\n")
            _seed_and_commit(root, USED)
            self.assertIs(self._halt(root)["restart_available"], False)

    def test_other_causes_carry_no_restart_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _seed_and_commit(root, USED)
            self.assertIsNone(self._halt(root, cause="weak-spec").get("restart_available"))


if __name__ == "__main__":
    unittest.main()
