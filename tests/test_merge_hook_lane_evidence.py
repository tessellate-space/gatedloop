"""The merge hook counts evidence recorded in the incoming branch's worktree
(design D2 of `cross-worktree-evidence`, task 1.2; issue #38).

The design's reproduction, as tests: a primary checkout on `main`, a linked
lane holding change branch `add-thing`, `live-check` and an unscoped `ci`
run green in the lane on the branch head. `git merge --squash add-thing`
issued against the primary -- however it names the primary -- used to be
denied with "no 'live-check' marker found", because the hook read only the
primary's store. The lane's markers vouch for exactly the tree the incoming
ref points at, so the merge is allowed; markers on any other tree still
deny, and the denial names every store it read. The commit gate is not
widened: a lane's marker never vouches for a commit in the primary.

Each case drives the real `hooks/gate-merge.sh` / `hooks/gate-commit.sh`
with the PreToolUse JSON the harness sends, against real worktrees: the
store layout under `.git/worktrees/<lane>` is git's, and no cheaper layer
can show which one the hook reads.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from _lane_fixture import lane_repo, markers_dir, run_hook
from _merge_fixture import CHANGE, git


class TestMergeFromThePrimarySeesTheLane(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = lane_repo(self._tmp.name)
        self.primary = self.repo.primary
        self.lane = self.repo.lane

    def test_a_lane_proven_merge_is_allowed_however_the_primary_is_named(self):
        # Fails if the hook reads only the merging worktree's store: every
        # route below was denied with "no 'live-check' marker found".
        self.repo.prove_head()
        routes = (
            ("bare, from the primary", f"git merge --squash {CHANGE}", self.primary),
            ("git -C, from the lane", f"git -C {self.primary} merge --squash {CHANGE}", self.lane),
            ("cd &&, from the lane", f"cd {self.primary} && git merge --squash {CHANGE}", self.lane),
        )
        for name, command, cwd in routes:
            with self.subTest(route=name):
                r = run_hook("gate-merge.sh", command, cwd)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_lane_markers_on_another_tree_deny_naming_both_stores(self):
        # Fails if a lane marker counts for a tree the branch does not point
        # at, or if the denial hides where it looked.
        self.repo.prove_head()
        (self.lane / "late.txt").write_text("after the gates ran\n")
        git(self.lane, "add", "late.txt")
        git(self.lane, "commit", "-q", "-m", "late commit, never gated")

        r = run_hook("gate-merge.sh", f"git -C {self.primary} merge --squash {CHANGE}", self.lane)

        self.assertEqual(r.returncode, 2, r.stderr)
        lane_git_dir = git(self.lane, "rev-parse", "--absolute-git-dir")
        self.assertIn(markers_dir(Path(self.primary) / ".git"), r.stderr)
        self.assertIn(markers_dir(lane_git_dir), r.stderr)

    def test_the_commit_gate_in_the_primary_ignores_the_lanes_marker(self):
        # Fails if the commit gate is widened along with the merge: the lane
        # holds a green ci marker for this exact tree, the primary has none.
        self.repo.prove_head()
        git(self.primary, "read-tree", CHANGE)
        self.assertEqual(
            git(self.primary, "write-tree"), git(self.primary, "rev-parse", f"{CHANGE}^{{tree}}"),
        )

        r = run_hook("gate-commit.sh", "git commit -m 'in the primary'", self.primary)

        self.assertEqual(r.returncode, 2, r.stderr)


if __name__ == "__main__":
    unittest.main()
