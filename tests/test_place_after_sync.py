"""Placement accepts main's content for a file (loop-hardening D9, #111).

The regression: a handoff records each test file's content before the
change touched it (its base). When main later changed a pre-existing test
file and the lane synced, `gates tests place` found content matching neither
the base nor any placed test, and called it a test defect -- blaming the
author for main's commit. The allowed set now also holds the file's content
at `git merge-base HEAD <target>`: what the branch last received from main.
A lane's own edit still refuses, as before.

Real git with a bare remote (`_lock_fixture`'s repository): the target and
the sync are git facts.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _lock_fixture import TEST_BASE, TEST_EDITED, TEST_REL, TEST_V1, LockRepo
from _merge_fixture import combined, git


def _authored_on_a_pre_existing_test(tmp: str) -> LockRepo:
    """`TEST_REL` exists on main before the change; the lane hands off
    tests that extend it."""
    repo = LockRepo(Path(tmp))
    (repo.primary / TEST_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo.primary / TEST_REL).write_text(TEST_BASE)
    git(repo.primary, "add", "-A")
    git(repo.primary, "commit", "-q", "-m", "the thing's existing tests")
    git(repo.primary, "push", "-q", "origin", "HEAD:main")
    repo.start_change(lane=True)
    repo.author(with_base=False)
    return repo


class PlacementAfterASync(unittest.TestCase):
    def test_main_changing_a_pre_existing_test_does_not_refuse_placement(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _authored_on_a_pre_existing_test(tmp)
            repo.advance_origin(TEST_REL, TEST_BASE + "# main's later edit\n", "main edits the tests")
            git(repo.lane, "fetch", "-q", "origin")
            git(repo.lane, "merge", "-q", "--no-edit", "origin/main")

            repo.must("task", "start", "1.1")
            r = repo.gates("tests", "place", "1.1", cwd=repo.lane)

            self.assertEqual(r.returncode, 0, combined(r))
            self.assertEqual((repo.lane / TEST_REL).read_text(), TEST_V1)

    def test_a_lane_only_edit_still_refuses_as_a_test_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _authored_on_a_pre_existing_test(tmp)
            repo.edit_past_the_hooks(TEST_REL, TEST_EDITED)

            repo.must("task", "start", "1.1")
            r = repo.gates("tests", "place", "1.1", cwd=repo.lane)

            self.assertEqual(r.returncode, 1, combined(r))
            self.assertIn("changed since authoring", r.stderr)
            self.assertIn("test defect", r.stderr)
            self.assertEqual((repo.lane / TEST_REL).read_text(), TEST_EDITED)


if __name__ == "__main__":
    unittest.main()
