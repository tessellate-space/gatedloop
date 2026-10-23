"""`gates merge` step 1 requires the authored-test lock at the branch head
(change `test-lock-remote-check`, task 2.1, design D3).

Step 1 proved the head with the live-check and `ci` markers, `verify`,
taint and acceptance, and nothing about the lock, so a placed test edited
past the commit hooks was squashed, pushed or opened as a pull request
with the lock broken. The regressions: a broken lock that does not refuse
step 1 (in either integration mode), a refusal that does not name the path
and the task, a refusal that has already moved the target or opened a pull
request, and an intact lock that refuses.

Real git with a bare remote and the fake forge: what is under test is that
nothing reaches the remote or the forge, which only a real push can show.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _forge_fixture import NO_CI, PR_MODE, Forge
from _lock_fixture import TEST_EDITED, TEST_REL, finished_lane
from _merge_fixture import combined, git


class ProveHeadLockTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _broken(self, manifest_extra: str = ""):
        repo = finished_lane(self.tmp, lane=True, manifest_extra=manifest_extra)
        repo.edit_past_the_hooks(TEST_REL, TEST_EDITED)
        repo.prove_head()
        return repo

    def test_a_broken_lock_refuses_step_1_locally_naming_path_and_task(self):
        repo = self._broken()
        origin_before, primary_before = repo.origin_main(), repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn(TEST_REL, combined(r))
        self.assertIn("1.2", combined(r))
        self.assertEqual(repo.origin_main(), origin_before, "the remote target moved")
        self.assertEqual(repo.head_state()[:2], primary_before[:2], "the primary checkout moved")
        self.assertEqual(repo.pushes(), 0)

    def test_a_broken_lock_refuses_step_1_in_pull_request_mode(self):
        repo = self._broken(manifest_extra=PR_MODE)
        forge = Forge(self.tmp / "forge.json").install(repo.bin)
        head = git(repo.lane, "rev-parse", "HEAD")

        r = repo.merge(**NO_CI)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn(TEST_REL, combined(r))
        self.assertEqual(forge.prs(), [], "a pull request was opened")
        self.assertEqual(forge.statuses(head), [], "a status was published")
        self.assertEqual(repo.pushes(), 0, "the branch was pushed")

    def test_an_intact_lock_passes_step_1(self):
        repo = finished_lane(self.tmp, lane=True)
        repo.prove_head()

        r = repo.merge()

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIn("the head is proven", combined(r))


if __name__ == "__main__":
    unittest.main()
