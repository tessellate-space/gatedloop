"""A halt at a completed task leaves its placement in force (change
`unblock-authored-lock`, design D3; issue #56 task 0.3, #49 case 2).

A halt means "wait" and says nothing about the tests, yet any halt row
voided the task's placement: a completed `NO-TESTS` task's committed
holding-file removal then read as its reason differing from the handoff,
on every commit of the branch and at the merge's head proof. The
regressions: a halt at a completed task that still voids its placement
(at the index or at a commit), and a halt at the task in flight that no
longer does.

Real git through the loop's own steps (`_lock_fixture.LockRepo`): what is
under test is which commit carried a task's tick and which carried the
halt, which only a real history shows.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _lock_fixture import TEST_REL, LockRepo
from _merge_fixture import CHANGE, LEDGER_REL, combined, git

TASKS_REL = f"openspec/changes/{CHANGE}/tasks.md"


def tick(repo: LockRepo, *done: str) -> None:
    """Rewrite the change's tasks.md with `done` checked."""
    lines = [f"- [{'x' if t in done else ' '}] {t} task {t}" for t in ("1.1", "1.2", "1.3")]
    repo.write(TASKS_REL, "## 1. Do it\n\n" + "\n".join(lines) + "\n")


class HaltAtACompletedTaskTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = LockRepo(Path(self._tmp.name))
        self.repo.start_change(lane=False)
        self.repo.author()

    def tearDown(self):
        self._tmp.cleanup()

    def _completed_no_tests_task_then_a_committed_halt(self) -> None:
        self.repo.do_task("1.1")
        self.repo.do_task("1.2")
        self.repo.place("1.3")
        self.repo.write("README.md", "docs\n")
        tick(self.repo, "1.1", "1.2", "1.3")
        self.repo.gated_commit("task 1.3", "1.3")
        self.repo.must("halt", "record", "oracle-conflict", "--task", "1.3",
                       "--detail", "waiting on a sourced value")
        git(self.repo.lane, "add", LEDGER_REL)
        git(self.repo.lane, "commit", "-q", "-m", "halt at 1.3")

    def test_at_a_commit_the_completed_no_tests_task_still_passes(self):
        self._completed_no_tests_task_then_a_committed_halt()

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertNotIn("NO-TESTS", combined(r))

    def test_at_the_index_a_later_commit_is_not_refused_for_the_halted_task(self):
        self._completed_no_tests_task_then_a_committed_halt()
        self.repo.write("data/catalog.txt", "a sourced value\n")
        git(self.repo.lane, "add", "-A")

        r = self.repo.gates("tests", "check", cwd=self.repo.lane)

        self.assertEqual(r.returncode, 0, combined(r))

    def test_a_halt_at_the_task_in_flight_still_voids_its_placement(self):
        self.repo.do_task("1.1")
        tick(self.repo, "1.1")
        self.repo.gated_commit("tick 1.1")
        self.repo.place("1.2")
        self.repo.red("1.2")
        self.repo.must("halt", "record", "stalled", "--task", "1.2", "--detail", "budget used")
        git(self.repo.lane, "add", "-A")  # the placed test kept, not discarded

        at_index = self.repo.gates("tests", "check", cwd=self.repo.lane)
        git(self.repo.lane, "commit", "-q", "-m", "halt at 1.2, keeping its placed test")
        at_commit = self.repo.check_ref("HEAD")

        self.assertEqual(at_index.returncode, 1, combined(at_index))
        self.assertIn(TEST_REL, at_index.stderr)
        self.assertEqual(at_commit.returncode, 1, combined(at_commit))
        self.assertIn(TEST_REL, at_commit.stderr)


if __name__ == "__main__":
    unittest.main()
