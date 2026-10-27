"""A test defect at a completed task reopens it (change
`unblock-authored-lock`, design D4; issue #49 case 1, #56 tasks 3.1/5.1).

After a task went red then green and was committed, a defect sent its
tests back to the author, and the lock then demanded a fresh red `unit`
run after the re-placement: impossible against code that is already
committed, so the branch could never commit again. The regressions: a
reopened task refused for the red run its first placement already
recorded; the re-handoff commit refused because the reopened path still
holds the committed test; a reopened test editable by the implementer
after re-placement; and the merge's head proof stopped by the #56 shape (a
completed `NO-TESTS` task with a later halt, and a completed task reopened
by a `green` defect and re-declared `CHARACTERIZATION`).

Real git through the loop's own steps, and a real `gates merge` for the
head proof: what is under test is the lock against a branch's history and
the merge step that reads it, which only a real repository shows.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _lock_fixture import TEST_EDITED, TEST_REL, TEST_V2, LockRepo
from _merge_fixture import CHANGE, MergeRepo, combined, git

TASKS_REL = f"openspec/changes/{CHANGE}/tasks.md"
HOLDING = f".gatedloop/authored/{CHANGE}"
TEST_V2_REVISED = TEST_V2 + "\ndef test_thing_thrice():\n    assert thing() * 3 == 3\n"

# `unit` reads its exit status from an untracked file, so one repository
# can record both the red run of a first placement and the green run a
# characterization re-placement needs.
UNIT_SWITCH = "  unit: \"sh -c 'exit $(cat .unit-rc)'\"\n"


class SwitchRepo(LockRepo):
    def __init__(self, tmp: Path, manifest_extra: str = ""):
        MergeRepo.__init__(self, tmp, manifest_extra=UNIT_SWITCH + manifest_extra)
        exclude = self.primary / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text(".unit-rc\n")

    def start_change(self, lane: bool) -> Path:
        out = super().start_change(lane=lane)
        self.unit_rc(1)
        return out

    def unit_rc(self, rc: int) -> None:
        (self.lane / ".unit-rc").write_text(f"{rc}\n")

    def green(self, task: str) -> None:
        self.unit_rc(0)
        r = self.gates("run", "unit", "--task", task, "--attempt", "1", cwd=self.lane)
        self.unit_rc(1)
        if r.returncode != 0:
            raise AssertionError(f"fixture green run for {task} was not green: {combined(r)}")

    def tick(self, *done: str) -> None:
        lines = [f"- [{'x' if t in done else ' '}] {t} task {t}" for t in ("1.1", "1.2", "1.3")]
        self.write(TASKS_REL, "## 1. Do it\n\n" + "\n".join(lines) + "\n")

    def hold(self, task: str, rel: str, content: str, characterization: str | None = None) -> None:
        self.write(f"{HOLDING}/{task}/{rel}.authored", content)
        if characterization is not None:
            self.write(f"{HOLDING}/{task}/CHARACTERIZATION", characterization + "\n")

    def complete_1_2(self, red: bool = True) -> None:
        """Tasks 1.1 and 1.2 done, 1.2's tick committed with its code."""
        self.do_task("1.1")
        self.place("1.2")
        if red:
            self.red("1.2")
        else:
            self.green("1.2")
        self.write("src/task_1_2.txt", "task 1.2\n")
        self.tick("1.1", "1.2")
        self.gated_commit("task 1.2", "1.2")

    def defect(self, task: str, kind: str, detail: str) -> None:
        if kind == "green":
            # The row `gates tests defect --kind green` writes; this task's
            # tests exercise the lock, not the defect command.
            self.append_lane_row({
                "ts": "2026-10-27T00:00:00+00:00", "gate": "test-defect", "exit": None,
                "duration_ms": 0, "change": CHANGE, "task": task, "tree": None,
                "attempt": None, "approved_by": None, "sha": None,
                "detail": detail, "kind": kind,
            })
        else:
            self.must("tests", "defect", task, "--kind", kind, "--detail", detail)
        self.gated_commit(f"test defect: {task}")


class ReopenedTaskTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _reopened_and_re_handed_off(self) -> SwitchRepo:
        repo = SwitchRepo(self.tmp)
        repo.start_change(lane=False)
        repo.author()
        repo.complete_1_2()
        repo.defect("1.2", "setup", "a step definition the e2e run cannot find")
        repo.hold("1.2", TEST_REL, TEST_V2_REVISED)
        repo.must("tests", "handoff", CHANGE, "--task", "1.2")
        return repo

    def test_the_re_handoff_commit_passes_the_lock(self):
        repo = self._reopened_and_re_handed_off()
        git(repo.lane, "add", "-A")

        at_index = repo.gates("tests", "check", cwd=repo.lane)
        repo.gated_commit("re-hand off 1.2")
        at_commit = repo.check_ref("HEAD")

        self.assertEqual(at_index.returncode, 0, combined(at_index))
        self.assertEqual(at_commit.returncode, 0, combined(at_commit))

    def test_a_reopened_task_placed_again_needs_no_new_red_run(self):
        repo = self._reopened_and_re_handed_off()
        repo.gated_commit("re-hand off 1.2")
        repo.place("1.2")
        self.assertEqual((repo.lane / TEST_REL).read_text(), TEST_V2_REVISED)
        git(repo.lane, "add", "-A")

        at_index = repo.gates("tests", "check", cwd=repo.lane)
        repo.gated_commit("task 1.2, reopened", "1.2")
        at_commit = repo.check_ref("HEAD")

        self.assertEqual(at_index.returncode, 0, combined(at_index))
        self.assertEqual(at_commit.returncode, 0, combined(at_commit))

    def test_a_reopened_test_edited_after_re_placement_is_refused(self):
        repo = self._reopened_and_re_handed_off()
        repo.gated_commit("re-hand off 1.2")
        repo.place("1.2")
        repo.write(TEST_REL, TEST_EDITED)
        git(repo.lane, "add", "-A")

        r = repo.gates("tests", "check", cwd=repo.lane)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn(TEST_REL, r.stderr)

    def test_the_merge_proves_the_head_of_a_change_shaped_like_issue_56(self):
        repo = SwitchRepo(self.tmp)
        repo.start_change(lane=True)
        repo.author()
        # 1.2: green on its first run and committed without a red run.
        repo.complete_1_2(red=False)
        # 1.3: a completed NO-TESTS task, then a halt at it.
        repo.place("1.3")
        repo.write("README.md", "docs\n")
        repo.tick("1.1", "1.2", "1.3")
        repo.gated_commit("task 1.3", "1.3")
        repo.must("halt", "record", "oracle-conflict", "--task", "1.3",
                  "--detail", "waiting on a sourced value")
        repo.gated_commit("halt at 1.3")
        # 1.2 reopened by a green defect and re-declared characterization.
        repo.defect("1.2", "green", "its tests pass on the tree before any implementation")
        repo.hold("1.2", TEST_REL, TEST_V2,
                  characterization="verifies values an earlier task already wrote")
        repo.must("tests", "handoff", CHANGE, "--task", "1.2")
        repo.gated_commit("re-hand off 1.2 as characterization")
        repo.place("1.2")
        repo.green("1.2")
        repo.gated_commit("task 1.2, re-declared", "1.2")

        at_head = repo.check_ref("HEAD")
        repo.prove_head()
        r = repo.merge()

        self.assertEqual(at_head.returncode, 0, combined(at_head))
        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIn("the head is proven", combined(r))


if __name__ == "__main__":
    unittest.main()
