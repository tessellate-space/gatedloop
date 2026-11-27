"""A run with no `--task` after the latest started task is ticked at HEAD
belongs to no task (openspec change `budget-ticked-task`, design D1 and D3;
issue #147).

Stdlib only, per `zero-dep-shim`. Each test drives `gates run` as a subprocess
in a throwaway git repo on a change branch, with a real ledger seeded through
the issue's sequence: a full handoff, task-start rows, the last task's RED
run, red `ci` rows, its restart used. The gate command touches a `ran` file,
so "refused without running the gate" is observable.

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

CHANGE = "room-occupants"
GATE_CMD = "sh -c 'touch ran; exit $(cat rc)'"
TASKS = f"openspec/changes/{CHANGE}/tasks.md"

UNTICKED = "## 1. Work\n\n- [x] 2.1 First thing\n- [ ] 2.2 Second thing\n"
TICKED = "## 1. Work\n\n- [x] 2.1 First thing\n- [x] 2.2 Second thing\n"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    env.pop("GATEDLOOP_CHANGE", None)
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _repo(tmp, tasks_at_head=TICKED):
    """A change branch whose HEAD holds `tasks_at_head` (or no tasks.md when
    `None`); the ledger is left untracked, as the tests seed it directly."""
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(
        f'gatesVersion: 1\ngates:\n  ci: "{GATE_CMD}"\n  unit: "{GATE_CMD}"\n')
    (root / ".gitignore").write_text("rc\nran\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    (root / "openspec" / "changes" / CHANGE).mkdir(parents=True)
    (root / "openspec" / "changes" / CHANGE / "proposal.md").write_text("why\n")
    if tasks_at_head is not None:
        (root / TASKS).write_text(tasks_at_head)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "tasks")
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


def _row(gate, task, rc=None):
    r = {"gate": gate, "task": task}
    if rc is not None:
        r["exit"] = rc
    if gate == "task-start":
        r["tree"] = "t" * 40
    return r


# The issue's sequence: the handoff, task 2.1 and 2.2 started, 2.2's RED run,
# two red ci runs charged to 2.2, its restart, two more reds -- the budget
# (loop.attempts 2, one fresh restart) is exhausted, restart included.
EXHAUSTED = [
    _row("tests-handoff", None),
    _row("task-start", "2.1"), _row("unit", "2.1", 1), _row("unit", "2.1", 0),
    _row("task-start", "2.2"), _row("unit", "2.2", 1),
    _row("ci", "2.2", 1), _row("ci", "2.2", 1),
    _row("restart", "2.2"),
    _row("ci", "2.2", 1), _row("ci", "2.2", 1),
]


class TestTickedAtHead(unittest.TestCase):
    def test_a_plain_ci_on_a_fully_ticked_change_runs_and_records_no_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, TICKED)
            _seed(root, EXHAUSTED)
            r = _run(root, "run", "ci")
            self.assertTrue((root / "ran").exists(),
                            "2.2 is ticked at HEAD: the run is no task's attempt\n"
                            + r.stdout + r.stderr)
            self.assertEqual(r.returncode, 1)
            last = _rows(root)[-1]
            self.assertEqual(last["gate"], "ci")
            self.assertIsNone(last["task"])

    def test_a_plain_unit_on_a_fully_ticked_change_runs_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, TICKED)
            _seed(root, EXHAUSTED)
            r = _run(root, "run", "unit")
            self.assertTrue((root / "ran").exists(), r.stdout + r.stderr)
            self.assertIsNone(_rows(root)[-1]["task"])

    def test_an_explicit_task_stays_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, TICKED)
            _seed(root, EXHAUSTED)
            before = len(_rows(root))
            r = _run(root, "run", "ci", "--task", "2.2")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse((root / "ran").exists(), "an explicit --task is budgeted")
            self.assertEqual(len(_rows(root)), before)
            self.assertIn("stalled", r.stdout + r.stderr)

    def test_an_unticked_task_in_flight_is_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, UNTICKED)
            _seed(root, EXHAUSTED)
            r = _run(root, "run", "ci")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse((root / "ran").exists(),
                             "2.2 is unchecked at HEAD: its budget applies")


class TestNotTickedAtHead(unittest.TestCase):
    """Design D3: the gaming route and the fail-closed paths."""

    def _assert_refused(self, root):
        before = len(_rows(root))
        r = _run(root, "run", "ci")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertFalse((root / "ran").exists(), "the gate ran despite the budget")
        self.assertEqual(len(_rows(root)), before, "a refusal writes no ledger row")
        self.assertIn("2.2", r.stdout + r.stderr)

    def test_a_tick_only_in_the_working_tree_stays_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, UNTICKED)
            (root / TASKS).write_text(TICKED)
            _seed(root, EXHAUSTED)
            self._assert_refused(root)

    def test_a_staged_tick_not_committed_stays_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, UNTICKED)
            (root / TASKS).write_text(TICKED)
            _git(root, "add", TASKS)
            _seed(root, EXHAUSTED)
            self._assert_refused(root)

    def test_no_tasks_md_at_head_stays_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, None)
            _seed(root, EXHAUSTED)
            self._assert_refused(root)

    def test_no_tasks_md_at_head_but_a_ticked_one_in_the_tree_stays_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, None)
            (root / TASKS).write_text(TICKED)
            _seed(root, EXHAUSTED)
            self._assert_refused(root)


if __name__ == "__main__":
    unittest.main()
