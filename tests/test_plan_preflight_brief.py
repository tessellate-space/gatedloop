"""`gates tests brief <change> --preflight` names the preflight store and
what an earlier round already authored (openspec change `plan-preflight`,
design D7; task 1.1).

The store is `.gatedloop/out/preflight/<change>/`, ignored because
`.gatedloop/out/` ignores itself, and left alone by log rotation. The brief
prints it as the place to write, in place of the real holding area, which a
preflight never creates. Its "Preflight reuse" section compares each task's
digest with `digests.json`: a task is stale when its digest moved or is
absent, or when it holds a path a stale task holds.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, GATES_SHIM, PreflightRepo, write  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("gates_shim_pf_brief", str(GATES_SHIM))
shim = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(shim)


def reuse(stdout: str) -> tuple[list[str], list[str]]:
    """`(stale, kept)` from the brief's "Preflight reuse" section."""
    stale = kept = None
    for line in stdout.splitlines():
        if line.startswith("Stale"):
            stale = line.split(":", 1)[1].strip()
        elif line.startswith("Kept"):
            kept = line.split(":", 1)[1].strip()
    assert stale is not None and kept is not None, stdout

    def ids(v):
        return [] if v == "none" else [x.strip() for x in v.split(",")]

    return ids(stale), ids(kept)


class PreflightBriefTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.r = PreflightRepo(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def brief(self):
        out = self.r.gates("tests", "brief", CHANGE, "--preflight")
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def save_digests(self):
        m = shim._load(self.r.root / ".gates.yaml")
        digests = shim._preflight_task_digests(m, self.r.root, CHANGE)
        write(self.r.store, "digests.json", json.dumps({"tasks": digests}))

    def test_the_brief_names_the_store_not_the_holding_area(self):
        out = self.brief()
        self.assertIn(f".gatedloop/out/preflight/{CHANGE}/authored/", out)
        self.assertTrue((self.r.store / "authored").is_dir())
        self.assertTrue((self.r.store / "reports").is_dir())
        self.assertFalse(self.r.holding.exists())
        self.assertFalse((self.r.root / ".gatedloop" / "authored").exists())

    def test_a_file_in_the_store_is_ignored_without_a_gitignore_entry(self):
        self.brief()
        self.assertFalse((self.r.root / ".gitignore").exists())
        self.r.hold("1.1", "tests/test_widget.py.authored", "def test_w():\n    assert 0\n")
        self.assertEqual(self.r.status(), "")

    def test_log_rotation_leaves_the_store(self):
        self.brief()
        held = self.r.hold("1.1", "tests/test_widget.py.authored", "x\n")
        out_dir = self.r.root / ".gatedloop" / "out"
        for i in range(3):
            write(out_dir, f"ci-2026010{i}T000000Z.log", "log\n")
        shim._rotate_out_logs(self.r.root, "ci", keep=0)
        self.assertEqual(list(out_dir.glob("ci-*.log")), [])
        self.assertTrue(held.is_file())

    def test_without_digests_every_task_is_stale(self):
        stale, kept = reuse(self.brief())
        self.assertEqual(stale, ["1.1", "1.2", "2.1"])
        self.assertEqual(kept, [])

    def test_with_matching_digests_every_task_is_kept(self):
        self.save_digests()
        stale, kept = reuse(self.brief())
        self.assertEqual(stale, [])
        self.assertEqual(kept, ["1.1", "1.2", "2.1"])

    def test_an_edited_task_line_makes_only_that_task_stale(self):
        self.save_digests()
        self.r.edit(f"{self.r.rel_dir}/tasks.md", "Document the widget", "Describe the widget")
        stale, kept = reuse(self.brief())
        self.assertEqual(stale, ["2.1"])
        self.assertEqual(kept, ["1.1", "1.2"])

    def test_a_task_sharing_a_held_path_with_a_stale_task_is_stale(self):
        self.brief()
        self.r.hold("1.1", "tests/test_widget.py.authored", "a\n")
        self.r.hold("2.1", "tests/test_widget.py.authored", "b\n")
        self.save_digests()
        self.r.edit(f"{self.r.rel_dir}/tasks.md", "Add the widget", "Add the new widget")
        stale, kept = reuse(self.brief())
        self.assertEqual(stale, ["1.1", "2.1"])
        self.assertEqual(kept, ["1.2"])

    def test_an_edited_design_makes_every_task_stale(self):
        self.save_digests()
        self.r.edit(f"{self.r.rel_dir}/design.md", "It does.", "It really does.")
        stale, kept = reuse(self.brief())
        self.assertEqual(stale, ["1.1", "1.2", "2.1"])
        self.assertEqual(kept, [])

    def test_a_moved_rewrite_base_makes_its_task_stale(self):
        self.save_digests()
        write(self.r.root, "tests/test_gadget.py", "def test_gadget():\n    assert 1\n")
        from _preflight_fixture import git
        git(self.r.root, "commit", "-qam", "move gadget test")
        stale, _kept = reuse(self.brief())
        self.assertEqual(stale, ["1.2"])

    def test_the_plain_brief_is_unchanged(self):
        out = self.r.gates("tests", "brief", CHANGE)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("Preflight", out.stdout)
        self.assertFalse(self.r.store.exists())


if __name__ == "__main__":
    unittest.main()
