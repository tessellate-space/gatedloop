"""`gates merge` step 2: integrate (design D2 of `merge-step`).

Fetch, detach onto the target's tip, `git merge --squash`. A conflict must
abort the squash, restore the primary checkout to exactly where it was, and
exit 2 naming the conflicting paths -- with the target untouched. The
regressions: a half-applied squash left staged in the primary, the primary
left detached, a conflict reported without the paths an orchestrator needs,
and #36's "local changes would be overwritten" refusal on the detach.

Real git with a bare remote, because a squash conflict and a detach refusal
are git's behaviour and nothing below it can produce them.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import MergeRepo, combined, git


class IntegrateTest(unittest.TestCase):
    def test_a_conflict_halts_naming_the_paths_and_leaves_everything_as_it_was(self):
        for lane in (False, True):
            with self.subTest(primary_on_the_branch=not lane), tempfile.TemporaryDirectory() as tmp:
                repo = MergeRepo(Path(tmp))
                repo.start_change(lane=lane)
                repo.task_commit("shared.txt", "one\nbranch side\nthree\n", "change line two")
                repo.prove_head()
                repo.advance_origin("shared.txt", "one\ntarget side\nthree\n", "target changes line two")
                # Step 1 commits the trailing rows; snapshot after that is
                # what "as before" means for the branch, so commit them here.
                git(repo.lane, "add", "-A")
                git(repo.lane, "commit", "-q", "-m", "trailing rows")
                origin_before = repo.origin_main()
                local_main_before = git(repo.primary, "rev-parse", "refs/heads/main")
                head_before = repo.head_state()

                r = repo.merge()

                self.assertEqual(r.returncode, 2, combined(r))
                self.assertIn("shared.txt", combined(r))
                self.assertEqual(repo.origin_main(), origin_before)
                self.assertEqual(git(repo.primary, "rev-parse", "refs/heads/main"), local_main_before)
                self.assertEqual(repo.head_state(), head_before,
                                 "the primary checkout is not exactly as before")

    def test_an_uncommitted_ledger_row_does_not_block_the_detach(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = MergeRepo(Path(tmp))
            repo.start_change(lane=False)
            repo.task_commit("feature.txt", "the thing\n", "add the thing")
            repo.prove_head()

            r = repo.merge()

            self.assertNotIn(r.returncode, (1, 2), combined(r))
            self.assertNotIn("would be overwritten", combined(r))


if __name__ == "__main__":
    unittest.main()
