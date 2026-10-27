"""`gates tests check` against the staged index keeps its exact output
(change `test-lock-remote-check`, task 1.1, design D1).

Design D1 refactors the lock check into one evaluator with two inputs, the
staged index or a commit, and requires the staged mode to stay
byte-identical. The commit hooks print this text as their denial, and an
implementer acts on its remedies, so the regression is a refactor that
rewords, reorders or drops a line of it while every pass/fail verdict stays
right. These are characterization tests: they pin the output the tree has
today, and pass before and after the refactor.

Real git in temporary repositories, driven through the shim as the hooks
call it: the check reads git's index, which only a real repository has.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _lock_fixture import TEST_EDITED, TEST_REL, TEST_V2, LockRepo
from _merge_fixture import git

HEADER = "gatedloop: authored tests check failed for 'add-thing':\n  - "
HELD_1_2 = ".gatedloop/authored/add-thing/1.2/tests/test_thing.py.authored"


class StagedCheckOutputTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = LockRepo(Path(self._tmp.name))
        self.repo.start_change(lane=False)
        self.repo.author()

    def tearDown(self):
        self._tmp.cleanup()

    def _check(self):
        git(self.repo.lane, "add", "-A")
        return self.repo.gates("tests", "check")

    def assert_refused_with(self, problems: list[str]):
        r = self._check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stdout, "")
        self.assertEqual(r.stderr, HEADER + "\n  - ".join(problems) + "\n")

    def test_a_pass(self):
        self.repo.place("1.1")
        self.repo.red("1.1")

        r = self._check()

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "gatedloop: authored tests check passed for 'add-thing'\n")

    def test_an_edited_placed_test(self):
        self.repo.place("1.1")
        self.repo.red("1.1")
        self.repo.write(TEST_REL, TEST_EDITED)

        self.assert_refused_with([
            f"{TEST_REL}: staged content differs from the test placed for task 1.1 — the "
            "implementer never edits an authored test. Restore it and record `gates tests "
            "defect 1.1 --kind setup|assertion --detail \"<why it is wrong>\"` for the "
            "author instead",
        ])

    def test_a_placed_test_left_unstaged(self):
        self.repo.place("1.1")
        self.repo.red("1.1")
        git(self.repo.lane, "add", "-A")
        git(self.repo.lane, "restore", "--staged", TEST_REL)

        r = self.repo.gates("tests", "check")

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stderr, HEADER + (
            f"{TEST_REL}: task 1.1's placed test is not staged — `git add {TEST_REL}`\n"
        ))

    def test_an_edited_held_test(self):
        self.repo.place("1.1")
        self.repo.red("1.1")
        self.repo.write(f"{HELD_1_2}", TEST_V2 + "# edited\n")

        self.assert_refused_with([
            f"{HELD_1_2}: the held test for task 1.2 differs from the handoff — a held "
            "test changes only through `gates tests handoff add-thing --task 1.2`",
        ])

    def test_a_placement_with_no_red_run(self):
        self.repo.place("1.1")

        self.assert_refused_with([
            "task 1.1: no failing `unit` run is recorded after its tests were placed — red "
            "before green is required. Run `gates run unit --task 1.1` and read why it "
            "fails before implementing (a precondition failure, exit 75, is not a red run; "
            "placed tests that pass are a defect: `gates tests defect 1.1 --kind "
            "green --detail ...`)",
        ])

    def test_implementing_before_placing(self):
        self.repo.must("task", "start", "1.1")
        self.repo.write("src/thing.txt", "the thing\n")

        self.assert_refused_with([
            "task 1.1: its authored tests are not placed — run `gates tests place 1.1` "
            "and a red `gates run unit --task 1.1` before implementing it",
        ])

    def test_a_voided_placement_carrying_an_edit(self):
        self.repo.place("1.1")
        self.repo.red("1.1")
        self.repo.must("tests", "defect", "1.1", "--kind", "assertion", "--detail", "wrong")
        self.repo.write(TEST_REL, TEST_EDITED)

        r = self._check()

        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(r.stderr.startswith(HEADER + (
            f"{TEST_REL}: staged content differs from its content before this change, "
            "and no placement of it is in force — the implementer never edits an authored "
            "test; record `gates tests defect <N.M> --kind setup|assertion --detail ...` "
            "instead\n"
        )), r.stderr)


if __name__ == "__main__":
    unittest.main()
