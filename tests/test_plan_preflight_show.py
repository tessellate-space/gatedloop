"""`gates tests show <change> --preflight` reports the preflight store
without a handoff (openspec change `plan-preflight`, design D7; task 1.3).

It lists each held task with its paths in the text and `--json` shapes
`gates tests show` uses, takes each rewrite's counts and `--diff` against the
path at `HEAD`, reads no ledger row and writes nothing.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, PreflightRepo, write  # noqa: E402

GADGET_REWRITE = "def test_gadget():\n    assert 1 == 1\n"


class PreflightShowTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.r = PreflightRepo(self._tmp.name)
        self.r.hold("1.1", "tests/test_widget.py.authored", "def test_w():\n    assert 0\n")
        self.r.hold("1.2", "tests/test_gadget.py.authored", GADGET_REWRITE)
        self.r.hold("2.1", "NO-TESTS", "docs only\n")
        # A ledger row a ledger-reading show would report; --preflight must not.
        write(self.r.root, f".gatedloop/runs/{CHANGE}.jsonl", json.dumps({
            "gate": "tests-handoff", "change": CHANGE, "task": None, "author": "separate",
            "tests": {"9.9": {"tests/test_ledger.py": "0" * 40}}, "base": {},
            "no_behaviour": {}, "characterization": {}}) + "\n")

    def tearDown(self):
        self._tmp.cleanup()

    def show(self, *extra):
        before = self.r.status()
        out = self.r.gates("tests", "show", CHANGE, "--preflight", *extra)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.r.status(), before)
        return out.stdout

    def test_text_lists_the_held_tasks_without_a_handoff(self):
        out = self.show()
        for token in ("1.1", "1.2", "2.1", "tests/test_widget.py", "+1 -1 vs HEAD"):
            self.assertIn(token, out)
        self.assertNotIn("9.9", out)
        self.assertNotIn("test_ledger", out)

    def test_json_shape(self):
        doc = json.loads(self.show("--json"))
        self.assertEqual(doc["change"], CHANGE)
        self.assertTrue(doc["preflight"])
        self.assertFalse(doc["handoff"])
        self.assertEqual(sorted(doc["tasks"]), ["1.1", "1.2", "2.1"])
        t = doc["tasks"]["1.2"]
        self.assertEqual(t["tests"], ["tests/test_gadget.py"])
        self.assertEqual(t["oracle"], "unit rewrites: tests/test_gadget.py")
        self.assertEqual(t["rewrites"]["tests/test_gadget.py"]["added"], 1)
        self.assertEqual(t["rewrites"]["tests/test_gadget.py"]["removed"], 1)
        self.assertEqual(doc["tasks"]["2.1"]["no_behaviour"], "docs only")

    def test_diff_against_head(self):
        out = self.show("--diff")
        self.assertIn("## task 1.2: rewrites tests/test_gadget.py", out)
        self.assertIn("--- a/tests/test_gadget.py", out)
        self.assertIn("+++ b/tests/test_gadget.py", out)
        self.assertIn("-    assert True", out)
        self.assertIn("+    assert 1 == 1", out)

    def test_an_empty_store_says_so_and_creates_nothing(self):
        import shutil
        shutil.rmtree(self.r.store)
        out = self.show()
        self.assertNotIn("tests/test_widget.py", out)
        self.assertEqual(json.loads(self.show("--json"))["tasks"], {})
        self.assertFalse(self.r.store.exists())


class PreflightDocsTest(unittest.TestCase):
    """docs-follow-surface: the release docs check finds no gap."""

    def test_release_docs_reports_no_gap(self):
        import subprocess
        from _preflight_fixture import REPO
        out = subprocess.run([sys.executable, str(REPO / "scripts" / "release"), "docs"],
                             cwd=REPO, capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
