"""Which change a push refusal names (change `release-push`, design D2, D3).

`gates discipline check-push` refuses an unproven commit pushed to the merge
target and tells the agent how to integrate it. In 0.10.0 it named
`gates merge loop-hardening` for a release commit that change had nothing to
do with: a change branch freshly cut from `main`, with no commits of its own,
is "merged into" anything later, so it was counted as carried in (#125).

The regressions caught here: a fresh change branch blamed for an unrelated
commit; a commit that carries no change refused with a `gates merge`
remedy that cannot apply; and the fix going too far, no longer naming a
change whose own commits the push really carries.

Real git with a bare remote (`_merge_fixture.MergeRepo`): which branches a
commit contains, and what the target's remote-tracking ref holds, are git's
answers.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, MergeRepo, combined, git

TARGET_REF = "refs/heads/main"
NO_CHANGE = "belongs to no change in flight"


class PushAttributionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = MergeRepo(Path(self._tmp.name))

    def check(self, sha):
        return self.repo.gates("discipline", "check-push", sha, "--remote-ref", TARGET_REF)

    def unrelated_commit_on_main(self) -> str:
        """A commit on `main` that no change owns, as a release commit is."""
        git(self.repo.primary, "checkout", "-q", "main")
        (self.repo.primary / "CHANGELOG.md").write_text("## 1.0.0\n\n- notes\n")
        git(self.repo.primary, "add", "CHANGELOG.md")
        git(self.repo.primary, "commit", "-q", "-m", "Release 1.0.0")
        return git(self.repo.primary, "rev-parse", "HEAD")

    def test_a_fresh_change_branch_is_not_blamed(self):
        # Scenario "A fresh change branch is not blamed": the branch exists
        # locally, cut from main, with no commits of its own.
        self.repo.start_change(lane=False)
        sha = self.unrelated_commit_on_main()

        r = self.check(sha)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertNotIn(f"gates merge {CHANGE}", combined(r))

    def test_a_commit_that_carries_no_change_says_so_and_lists_the_checks(self):
        # Scenario "A commit that belongs to no change".
        self.repo.start_change(lane=False)
        sha = self.unrelated_commit_on_main()

        r = self.check(sha)

        out = combined(r)
        self.assertEqual(r.returncode, 1, out)
        self.assertIn(NO_CHANGE, out)
        self.assertNotIn("integrate through", out)
        self.assertNotIn("gates merge <change>", out)
        self.assertIn("live-check", out)  # the unmet checks are still listed

    def test_a_change_branch_with_its_own_commits_is_still_named(self):
        # Scenario "A change branch with its own commits is still named".
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        git(self.repo.primary, "checkout", "-q", "main")
        git(self.repo.primary, "merge", "-q", "--no-ff", "-m", "raw merge", CHANGE)
        sha = git(self.repo.primary, "rev-parse", "HEAD")

        r = self.check(sha)

        out = combined(r)
        self.assertEqual(r.returncode, 1, out)
        self.assertIn(f"gates merge {CHANGE}", out)
        self.assertNotIn(NO_CHANGE, out)


if __name__ == "__main__":
    unittest.main()
