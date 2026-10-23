"""`_marker_stores(root, ref)`: which worktrees' marker stores may vouch for
an incoming ref (design D1 of `cross-worktree-evidence`, task 1.1).

Markers are kept per worktree, so a lane's green gates live under
`.git/worktrees/<lane>/gatedloop/markers`. A merge run from the primary used
to read only the primary's store and was always refused. The helper names
the current worktree's store first, then the store of the worktree holding
the incoming ref -- but only when the ref is a local branch some OTHER
worktree has checked out. Every other ref keeps today's single store.

Real linked worktrees: which worktree holds a branch is git's answer
(`git worktree list`), and only a real repository can give it.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _lane_fixture import GATES_SHIM, lane_repo
from _merge_fixture import CHANGE, clean_env, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_marker_stores", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _resolved(paths) -> list:
    return [Path(p).resolve() for p in paths]


class TestMarkerStores(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # The in-process calls run git too: give them the same clean
        # environment the subprocesses get.
        patcher = mock.patch.dict(os.environ, clean_env(), clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.repo = lane_repo(self._tmp.name)
        self.primary = self.repo.primary
        self.lane = self.repo.lane

    def test_a_local_branch_held_by_another_worktree_adds_that_store(self):
        # Fails if the holder's store is never consulted -- the lane-proven
        # merge from the primary stays refused with "no marker" (issue #38).
        for ref in (CHANGE, f"refs/heads/{CHANGE}"):
            with self.subTest(ref=ref):
                self.assertEqual(
                    _resolved(gates._marker_stores(self.primary, ref)),
                    _resolved([self.primary, self.lane]),
                )

    def test_refs_no_other_worktree_holds_keep_the_current_store_alone(self):
        # Fails if a ref that names no held local branch widens the lookup:
        # a remote branch, a sha, or a branch nobody has checked out.
        git(self.primary, "branch", "idle", CHANGE)
        git(self.primary, "push", "-q", "origin", f"{CHANGE}:{CHANGE}")
        git(self.primary, "fetch", "-q", "origin")
        sha = git(self.primary, "rev-parse", CHANGE)
        for ref in ("idle", f"origin/{CHANGE}", f"refs/remotes/origin/{CHANGE}", sha):
            with self.subTest(ref=ref):
                self.assertEqual(
                    _resolved(gates._marker_stores(self.primary, ref)),
                    _resolved([self.primary]),
                )

    def test_the_holder_being_root_is_listed_once(self):
        # Fails if the merging worktree's own store is read twice when it is
        # itself the holder (a merge run from inside the lane).
        self.assertEqual(
            _resolved(gates._marker_stores(self.lane, CHANGE)),
            _resolved([self.lane]),
        )


if __name__ == "__main__":
    unittest.main()
