"""`epic-linkage` task 2.1 (design D3): an epic is never implemented. The
real `hooks/gate-implement.sh`, fed PreToolUse JSON for
`git checkout -b <epic>`, denies the cut, naming the children to implement
instead -- even when the epic's plan is merged and approved. A child's own
cut is still governed by the approval check alone.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epic_fixture import EpicRepo  # noqa: E402


class TestAnEpicIsNeverImplemented(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = EpicRepo(self._tmp.name)
        self.repo.change("autonomous-dev", tasks=(0, 1))
        self.repo.change("lane-permissions", epic="autonomous-dev", tasks=(0, 2))
        self.repo.change("ledger-rollup", epic="autonomous-dev", tasks=(0, 2))
        self.repo.commit("plans merged")
        for change in ("autonomous-dev", "lane-permissions"):
            r = self.repo.gates("approval", "attest", change, "--local")
            self.assertEqual(r.returncode, 0, r.stderr)
        self.repo.commit("attest approvals")

    def tearDown(self):
        self._tmp.cleanup()

    def test_cutting_a_branch_for_an_approved_epic_is_denied_naming_its_children(self):
        r = self.repo.hook("gate-implement.sh", "git checkout -b autonomous-dev")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("autonomous-dev", r.stderr)
        self.assertIn("lane-permissions", r.stderr)
        self.assertIn("ledger-rollup", r.stderr)

    def test_cutting_a_branch_for_an_approved_child_is_allowed(self):
        r = self.repo.hook("gate-implement.sh", "git checkout -b lane-permissions")
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
