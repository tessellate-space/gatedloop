"""A recorded halt stops the loop (escalation-outcomes design D3).

`gates discipline check-continue` is what the Stop hook reads to decide
whether to re-enter the loop. Before this change it continued on (change
branch AND unchecked task AND clean tree) — exactly the state a clean halt
leaves behind. These tests pin the one new case in which it stops
continuing: the change's latest `halt` row is newer (by file order) than its
latest `task-start` row.

Stdlib only, per `zero-dep-shim`. Throwaway git repos, shim driven as a
subprocess.

Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
CHANGE = "my-change"
TASKS = "# Tasks\n\n- [x] 1.1 first\n- [ ] 1.2 second\n- [ ] 1.3 third\n"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    )


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _repo(tmp):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    tasks = root / "openspec" / "changes" / CHANGE / "tasks.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text(TASKS)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "tasks")
    return root


def _commit_ledger(root, msg):
    _git(root, "add", ".gatedloop/runs")
    _git(root, "commit", "-m", msg)


def _check(root):
    return _run_gates(root, "discipline", "check-continue")


class TestCheckContinueHonoursARecordedHalt(unittest.TestCase):
    def test_clean_boundary_with_no_halt_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _check(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("1.2", r.stdout)

    def test_committed_halt_stops_and_names_cause_and_remedy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _run_gates(root, "halt", "record", "weak-spec", "--task", "1.2")
            self.assertEqual(r.returncode, 0, r.stderr)
            _commit_ledger(root, "record halt")
            r = _check(root)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("weak-spec", r.stderr)
            self.assertIn("gates task start", r.stderr)
            self.assertEqual(r.stdout.strip(), "", "no continuation line on a halt")

    def test_uncommitted_halt_row_still_names_the_cause(self):
        """The halt row dirties the ledger; the continue check must still say
        why it stops, not only that the tree is dirty."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "halt", "record", "weak-spec", "--task", "1.2")
            r = _check(root)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("weak-spec", r.stderr)

    def test_task_start_after_halt_lifts_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "halt", "record", "weak-spec", "--task", "1.2")
            _commit_ledger(root, "record halt")
            self.assertNotEqual(_check(root).returncode, 0)
            r = _run_gates(root, "task", "start", "1.2")
            self.assertEqual(r.returncode, 0, r.stderr)
            _commit_ledger(root, "resume")
            r = _check(root)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_halt_older_than_latest_task_start_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "1.1")
            _run_gates(root, "halt", "record", "stalled", "--task", "1.1")
            _run_gates(root, "task", "start", "1.2")
            _commit_ledger(root, "history")
            r = _check(root)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_unrecorded_halt_is_re_entered(self):
        """A halt that was only narrated (no row) does not take: the check
        continues exactly as at a task boundary."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "1.2")
            _commit_ledger(root, "task start")
            r = _check(root)
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
