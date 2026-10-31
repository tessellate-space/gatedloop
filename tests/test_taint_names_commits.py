"""The taint refusal names its commits (loop-hardening D5, #108).

The regression: `gates merge` step 1 refused a tainted change with "the
reflog audit found a commit with no green-ci record", and nothing else. The
lane had to work out which commit that was -- usually a merge commit from a
plain `git merge origin/main`, which git commits without running any
pre-commit hook. The refusal now lists each tainted commit's short sha and
subject, and marks a merge commit with the sync route. The remedy is
unchanged: one green `gates run ci` on the head clears it.

Real git with a bare remote and `_merge_fixture`'s repository: the merge
commit is made with plain git, outside every hook, as a lane's was.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import MergeRepo, combined, git


class TaintRefusalNamesItsCommits(unittest.TestCase):
    def test_a_merge_commit_made_outside_the_hooks_is_named_and_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = MergeRepo(Path(tmp))
            repo.start_change(lane=True)
            repo.task_commit("feature.txt", "the thing\n", "add the thing")
            repo.advance_origin("other.txt", "another change\n", "another change lands")
            git(repo.lane, "fetch", "-q", "origin")
            git(repo.lane, "merge", "-q", "--no-edit", "-m", "sync main into the lane", "origin/main")
            merge_sha = git(repo.lane, "rev-parse", "HEAD")
            repo.task_commit("feature.txt", "the thing, finished\n", "finish the thing")
            repo.prove_head()

            r = repo.merge()

            self.assertEqual(r.returncode, 1, combined(r))
            out = combined(r)
            self.assertIn("unresolved taint", out)
            self.assertIn(merge_sha[:12], out)
            self.assertIn("sync main into the lane", out)
            self.assertIn("merge commit", out)
            self.assertIn("git merge --no-commit", out)


if __name__ == "__main__":
    unittest.main()
