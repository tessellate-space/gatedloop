"""`epic-linkage` task 2.2 (design D4): an epic archives only after every
child. The real `hooks/gate-archive.sh`, fed PreToolUse JSON for
`openspec archive <epic>`, denies while any child is not archived, listing
each open child with its state; a drained epic is allowed, and the existing
merge check still applies to it.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epic_fixture import EpicRepo, row  # noqa: E402


class TestAnEpicArchivesAfterItsChildren(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = EpicRepo(self._tmp.name)
        self.repo.change("autonomous-dev")
        self.repo.change("ledger-rollup", epic="autonomous-dev", archived=True, tasks=(2, 2))

    def tearDown(self):
        self._tmp.cleanup()

    def _archive(self):
        return self.repo.hook("gate-archive.sh", "openspec archive autonomous-dev --yes")

    def test_an_open_child_refuses_the_archive_naming_it_and_its_state(self):
        self.repo.change("lane-permissions", epic="autonomous-dev", approved=True, tasks=(1, 3))
        self.repo.ledger("lane-permissions", row("task-start", 1, task="1.1"))
        self.repo.commit("one child archived, one underway")

        r = self._archive()
        self.assertEqual(r.returncode, 2, r.stderr)
        line = next((l for l in r.stderr.splitlines() if "lane-permissions" in l), "")
        self.assertIn("implementing", line, r.stderr)
        self.assertNotIn("ledger-rollup", r.stderr)

    def test_a_drained_epic_is_allowed(self):
        self.repo.change("lane-permissions", epic="autonomous-dev", archived=True, tasks=(3, 3))
        self.repo.commit("every child archived")

        r = self._archive()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_drained_epic_still_needs_its_plan_merged(self):
        self.repo.commit("child archived on main")
        self.repo.root.joinpath("openspec", "changes", "autonomous-dev").rename(
            self.repo.root / "parked")
        self.repo.commit("epic not on main")
        self.repo.root.joinpath("parked").rename(
            self.repo.root / "openspec" / "changes" / "autonomous-dev")

        r = self._archive()
        self.assertEqual(r.returncode, 2, r.stderr)


if __name__ == "__main__":
    unittest.main()
