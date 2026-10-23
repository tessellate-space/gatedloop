"""`epic-linkage` task 1.1 (design D1): a change names its epic with a
top-level `x-gatedloop-epic` key in its own `.openspec.yaml`, read through
`_load`, for active and archived changes alike, with or without PyYAML.

The reader under test is the shim's `_epic_links(root)`: every change that
names an epic, as `{"change", "epic", "archived"}`, sorted by change name.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epic_fixture import EpicRepo, load_shim  # noqa: E402

gates = load_shim("gates_shim_epic_links")


def _links(root: Path, no_yaml: bool) -> list[dict]:
    if no_yaml:
        with mock.patch.dict(sys.modules, {"yaml": None}):
            return gates._epic_links(root)
    return gates._epic_links(root)


class TestEpicLinks(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = EpicRepo(self._tmp.name)
        self.repo.change("autonomous-dev")
        self.repo.change("lane-permissions", epic="autonomous-dev")
        self.repo.change("ledger-rollup", epic="autonomous-dev", archived=True)
        self.repo.change("unrelated")

    def tearDown(self):
        self._tmp.cleanup()

    def test_active_and_archived_children_are_read_with_and_without_pyyaml(self):
        expected = [
            {"change": "lane-permissions", "epic": "autonomous-dev", "archived": False},
            {"change": "ledger-rollup", "epic": "autonomous-dev", "archived": True},
        ]
        for no_yaml in (False, True):
            with self.subTest(no_yaml=no_yaml):
                self.assertEqual(_links(self.repo.root, no_yaml), expected)

    def test_an_unprefixed_epic_key_is_not_a_link(self):
        # OpenSpec 1.14 fails --strict on a bare `epic:`; it is not ours to read.
        d = self.repo.root / "openspec" / "changes" / "unrelated"
        (d / ".openspec.yaml").write_text("schema: spec-driven\nepic: autonomous-dev\n")
        names = [link["change"] for link in gates._epic_links(self.repo.root)]
        self.assertNotIn("unrelated", names)

    def test_no_openspec_directory_reads_as_no_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gates._epic_links(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
