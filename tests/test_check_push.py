"""`gates discipline check-push <sha> --remote-ref <ref>` (change
`git-layer-enforcement`, design D3).

A push that updates the merge target is allowed only when the pushed commit
is proven: a `merge` ledger row records it (what `gates merge` writes — the
row names the squash commit, and the archive commit pushed on top of it
carries only ledger and planning paths), or the merge gate's incoming-tree
checks hold for the pushed commit's tree. Any other branch, and a deletion,
pass untouched.

The regressions caught here: `gates merge`'s own push refused (the merge
row not found for the commit actually pushed, which is the archive commit,
not the squash); a raw merge pushed with no proof allowed; a code commit
landed after an earlier merge riding on that merge's row; a proven
incoming tree refused; a denial that does not name the unmet check or
`gates merge` as the remedy; and a feature-branch push or a deletion gated.

Real git with a bare remote (`_merge_fixture.MergeRepo`): which commit a
merge row vouches for, and what a raw merge's tree is, are git's answers,
and nothing below a real repository can produce them.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, MergeRepo, combined, git

ZERO = "0" * 40
TARGET_REF = "refs/heads/main"


class CheckPushTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = MergeRepo(Path(self._tmp.name))

    def check(self, sha, ref=TARGET_REF):
        return self.repo.gates("discipline", "check-push", sha, "--remote-ref", ref)

    def raw_merge(self) -> str:
        """The change merged into `main` by hand, no gate run on the result."""
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        git(self.repo.primary, "checkout", "-q", "main")
        git(self.repo.primary, "merge", "-q", "--no-ff", "-m", "raw merge", CHANGE)
        return git(self.repo.primary, "rev-parse", "HEAD")

    def test_the_push_gates_merge_made_is_proven_by_its_merge_row(self):
        # Scenario "The shim's own merge push".
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        self.repo.prove_head()
        merged = self.repo.merge()
        self.assertEqual(merged.returncode, 0, combined(merged))

        r = self.check(self.repo.origin_main())

        self.assertEqual(r.returncode, 0, combined(r))

    def test_a_code_commit_after_a_merge_is_not_proven_by_that_merge(self):
        # Fails if any merge row in the ledger vouched for every later
        # commit: code landed on top of a proven merge would ride on it.
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        self.repo.prove_head()
        self.assertEqual(self.repo.merge().returncode, 0)
        git(self.repo.primary, "checkout", "-q", "-B", "main", "origin/main")
        (self.repo.primary / "later.txt").write_text("unproven\n")
        git(self.repo.primary, "add", "later.txt")
        git(self.repo.primary, "commit", "-q", "-m", "a later code commit")

        r = self.check(git(self.repo.primary, "rev-parse", "HEAD"))

        self.assertEqual(r.returncode, 1, combined(r))

    def test_a_raw_merge_with_no_proof_is_denied_naming_the_check_and_the_remedy(self):
        # Scenario "A raw merge pushed without proof".
        sha = self.raw_merge()

        r = self.check(sha)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("live-check", combined(r))
        self.assertIn("gates merge", combined(r))

    def test_a_raw_merge_whose_tree_is_proven_passes(self):
        # Fails if only a merge row could ever pass: D3's second way is the
        # merge gate's own incoming-tree checks, here a full `ci` and a
        # `live-check` run on the merged tree itself.
        sha = self.raw_merge()
        for gate in ("ci", "live-check"):
            ran = self.repo.gates("run", gate)
            self.assertEqual(ran.returncode, 0, combined(ran))

        r = self.check(sha)

        self.assertEqual(r.returncode, 0, combined(r))

    def test_a_feature_branch_push_is_ignored(self):
        # Scenario "A feature branch push": nothing about the branch is
        # proven, and nothing is required of it.
        self.repo.start_change(lane=False)
        sha = self.repo.task_commit("feature.txt", "the thing\n", "add the thing")

        r = self.check(sha, ref=f"refs/heads/{CHANGE}")

        self.assertEqual(r.returncode, 0, combined(r))

    def test_a_deletion_is_ignored(self):
        r = self.check(ZERO)

        self.assertEqual(r.returncode, 0, combined(r))


if __name__ == "__main__":
    unittest.main()
