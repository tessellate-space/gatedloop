"""`epic-linkage` task 1.2 (design D2): `gates validate` fails, naming the
child, when an active change's `x-gatedloop-epic` names a missing change,
itself, an epic that itself names an epic, or an archived epic.

Drives the real shim against throwaway repositories (`tests/_epic_fixture.py`).
Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epic_fixture import EpicRepo  # noqa: E402


class TestEpicValidation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = EpicRepo(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _validate(self):
        return self.repo.gates("validate")

    def test_a_child_of_an_active_epic_validates(self):
        self.repo.change("autonomous-dev")
        self.repo.change("lane-permissions", epic="autonomous-dev")
        r = self._validate()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_archived_child_of_an_archived_epic_validates(self):
        self.repo.change("old-epic", archived=True)
        self.repo.change("old-child", epic="old-epic", archived=True)
        r = self._validate()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_each_broken_link_fails_naming_the_changes(self):
        cases = {
            "missing": (
                [("lane-permissions", {"epic": "no-such-change"})],
                ["lane-permissions", "no-such-change"],
            ),
            "self": (
                [("lane-permissions", {"epic": "lane-permissions"})],
                ["lane-permissions"],
            ),
            "nested": (
                [("roadmap", {}), ("autonomous-dev", {"epic": "roadmap"}),
                 ("lane-permissions", {"epic": "autonomous-dev"})],
                ["lane-permissions", "autonomous-dev"],
            ),
            "archived epic, active child": (
                [("autonomous-dev", {"archived": True}),
                 ("lane-permissions", {"epic": "autonomous-dev"})],
                ["lane-permissions", "autonomous-dev"],
            ),
        }
        for label, (changes, named) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                repo = EpicRepo(tmp)
                for name, kw in changes:
                    repo.change(name, **kw)
                r = repo.gates("validate")
                self.assertEqual(r.returncode, 1, r.stdout)
                errors = [l for l in r.stderr.splitlines() if l.strip().startswith("- ")]
                epic_errors = [l for l in errors if "lane-permissions" in l]
                self.assertTrue(epic_errors, r.stderr)
                for name in named:
                    self.assertTrue(any(name in l for l in epic_errors), (label, name, r.stderr))

    def test_every_broken_link_is_listed_not_only_the_first(self):
        self.repo.change("first-child", epic="no-such-change")
        self.repo.change("second-child", epic="second-child")
        r = self._validate()
        self.assertEqual(r.returncode, 1)
        self.assertIn("first-child", r.stderr)
        self.assertIn("second-child", r.stderr)


if __name__ == "__main__":
    unittest.main()
