"""`gates tests check --ref <commit>`: the authored-test lock at a commit
(change `test-lock-remote-check`, task 1.2, design D1 and D2).

The commit hooks check the lock against the staged index, so a locked test
edited through any path they did not see -- `--no-verify`, a host with no
hook, a human edit -- reached the merge with the lock silently broken. The
regressions here: a check at a commit that misses an edited placed test,
reads the working tree or the index instead of the commit, keeps a voided
placement's content locked (or forgets the base it must return to), locks
an earlier task's content after a later task replaced it, accepts a
placement with no red run, or refuses a change that has no authored tests
when it should pass and say so.

Real git in temporary repositories: what is under test is which tree and
which ledger a commit carries, which only a real repository can show.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _lock_fixture import TEST_BASE, TEST_EDITED, TEST_REL, TEST_V1, LockRepo
from _merge_fixture import CHANGE, combined, git


class CheckAtRefTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = LockRepo(Path(self._tmp.name))
        self.repo.start_change(lane=False)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_placed_test_edited_past_the_hooks_fails_naming_path_task_and_commit(self):
        self.repo.author()
        self.repo.do_task("1.1")
        bad = self.repo.edit_past_the_hooks(TEST_REL, TEST_EDITED)

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn(TEST_REL, r.stderr)
        self.assertIn("1.1", r.stderr)
        self.assertIn(bad[:12], r.stderr)

    def test_a_clean_head_passes_and_lists_the_tasks_it_verified(self):
        self.repo.author()
        self.repo.do_task("1.1")
        self.repo.do_task("1.2")

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIn("1.1", r.stdout)
        self.assertIn("1.2", r.stdout)

    def test_no_handoff_passes_and_says_there_are_no_authored_tests(self):
        self.repo.write("src/thing.txt", "the thing\n")
        self.repo.gated_commit("add the thing", "1.1")

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIn("no authored tests", r.stdout)

    def test_a_voided_placement_passes_holding_its_base_content(self):
        self.repo.author()
        self.repo.void("1.1")
        self.assertEqual((self.repo.lane / TEST_REL).read_text(), TEST_BASE)

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 0, combined(r))

    def test_a_voided_placement_still_holding_the_placed_content_fails(self):
        self.repo.author()
        self.repo.void("1.1")
        self.repo.edit_past_the_hooks(TEST_REL, TEST_V1, "keep the voided test")

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn(TEST_REL, r.stderr)

    def test_a_later_task_replacing_an_earlier_placement_moves_the_lock(self):
        self.repo.author()
        first = self.repo.do_task("1.1")
        self.repo.do_task("1.2")

        at_head = self.repo.check_ref("HEAD")
        at_first = self.repo.check_ref(first, "--change", CHANGE)

        self.assertEqual(at_head.returncode, 0, combined(at_head))
        # The ledger as of the earlier commit: 1.1's content was the lock then.
        self.assertEqual(at_first.returncode, 0, combined(at_first))

    def test_a_placement_with_no_red_run_fails(self):
        self.repo.author()
        self.repo.do_task("1.1", red=False)

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("1.1", r.stderr)
        self.assertIn("red", r.stderr)

    def test_an_edited_held_test_at_the_commit_fails(self):
        self.repo.author()
        held = f".gatedloop/authored/{CHANGE}/1.2/{TEST_REL}.authored"
        self.repo.edit_past_the_hooks(held, TEST_V1 + "# edited\n", "edit a held test")

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("1.2", r.stderr)

    def test_the_working_tree_and_index_are_not_read(self):
        self.repo.author()
        self.repo.do_task("1.1")
        self.repo.write(TEST_REL, TEST_EDITED)
        git(self.repo.lane, "add", "-A")

        r = self.repo.check_ref("HEAD")

        self.assertEqual(r.returncode, 0, combined(r))

    def test_the_change_resolves_from_a_branch_named_from_elsewhere(self):
        self.repo.author()
        self.repo.do_task("1.1")
        self.repo.edit_past_the_hooks(TEST_REL, TEST_EDITED)
        git(self.repo.lane, "checkout", "-q", "main")

        r = self.repo.check_ref(CHANGE)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn(TEST_REL, r.stderr)

    def test_a_commit_naming_no_change_is_refused_unless_change_is_given(self):
        self.repo.author()
        sha = self.repo.do_task("1.1")
        git(self.repo.lane, "checkout", "-q", "main")

        refused = self.repo.check_ref(sha)
        given = self.repo.check_ref(sha, "--change", CHANGE)

        self.assertEqual(refused.returncode, 1, combined(refused))
        self.assertIn("--change", refused.stderr)
        self.assertEqual(given.returncode, 0, combined(given))

    def test_a_ref_that_is_not_a_commit_is_refused(self):
        r = self.repo.check_ref("no-such-ref", "--change", CHANGE)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("no-such-ref", r.stderr)


if __name__ == "__main__":
    unittest.main()
