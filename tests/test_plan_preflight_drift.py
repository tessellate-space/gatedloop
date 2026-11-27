"""`gates plan check <change> --against <ref>` (openspec change
`plan-preflight`, design D11; task 3.2).

With `--against`, the existence checks run at `<ref>`, and every path the
plan names (task lines, `rewrites:` clauses, backticked paths in
`design.md`, never the change's own directory) that was modified, deleted
or renamed between the plan's base and `<ref>` is a `drift` finding. The
base is the latest commit in `<ref>`'s history touching the change's
directory when `<ref>` holds the change, `git merge-base HEAD <ref>`
otherwise. An unresolvable `<ref>` exits 1.

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

from _preflight_fixture import CHANGE, PreflightRepo, git, write  # noqa: E402

DESIGN = """\
# Design

## Decisions

### D1. The widget reads `src/gadget.py` and `src/other.py`

It does.
"""


class PlanDriftTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.r = PreflightRepo(self._tmp.name, design=DESIGN)

    def tearDown(self):
        self._tmp.cleanup()

    def against(self, ref="main"):
        out = self.r.gates("plan", "check", CHANGE, "--json", "--against", ref)
        return out.returncode, (json.loads(out.stdout) if out.stdout.strip() else None), out

    def drift(self, doc) -> dict[str, str]:
        return {f["path"]: f["detail"] for f in doc["findings"] if f["kind"] == "drift"}

    def land_on_main(self, *changes):
        git(self.r.root, "checkout", "-q", "main")
        for fn in changes:
            fn()
        git(self.r.root, "add", "-A")
        git(self.r.root, "commit", "-q", "-m", "target moves")

    def merge_plan(self):
        git(self.r.root, "checkout", "-q", "main")
        git(self.r.root, "merge", "-q", "--ff-only", f"plan/{CHANGE}")

    def moves(self):
        return (
            lambda: write(self.r.root, "src/gadget.py", "def gadget():\n    return 2\n"),
            lambda: git(self.r.root, "mv", "src/other.py", "src/moved.py"),
            lambda: git(self.r.root, "rm", "-q", "tests/test_gadget.py"),
        )

    def test_named_files_moved_after_the_plan_merged(self):
        self.merge_plan()
        self.land_on_main(*self.moves())
        git(self.r.root, "checkout", "-q", "-b", CHANGE)
        code, doc, _ = self.against()
        self.assertEqual(code, 1)
        self.assertEqual(doc["against"], "main")
        drift = self.drift(doc)
        self.assertEqual(set(drift), {"src/gadget.py", "src/other.py", "tests/test_gadget.py"})
        self.assertIn("modified", drift["src/gadget.py"])
        self.assertIn("renamed to src/moved.py", drift["src/other.py"])
        self.assertIn("deleted", drift["tests/test_gadget.py"])
        absent = [(f["task"], f["path"]) for f in doc["findings"] if f["kind"] == "rewrite-absent"]
        self.assertEqual(absent, [("1.2", "tests/test_gadget.py")])

    def test_named_files_moved_while_the_plan_branch_waited(self):
        self.land_on_main(self.moves()[0])
        git(self.r.root, "checkout", "-q", f"plan/{CHANGE}")
        code, doc, _ = self.against()
        self.assertEqual(code, 1)
        self.assertEqual(set(self.drift(doc)), {"src/gadget.py"})

    def test_an_unrelated_commit_adds_no_finding(self):
        self.merge_plan()
        self.land_on_main(lambda: write(self.r.root, "notes/unrelated.txt", "x\n"),
                          lambda: write(self.r.root, "src/brand_new.py", "Y = 2\n"))
        code, doc, out = self.against()
        self.assertEqual(code, 0, out.stdout + out.stderr)
        self.assertEqual(doc["findings"], [])

    def test_the_change_directory_itself_is_not_watched(self):
        self.merge_plan()
        self.land_on_main(lambda: self.r.edit(f"{self.r.rel_dir}/design.md", "It does.", "It did."))
        self.assertEqual(self.drift(self.against()[1]), {})

    def test_a_bad_ref_exits_1(self):
        code, _doc, out = self.against("no-such-ref")
        self.assertEqual(code, 1)
        self.assertIn("no-such-ref", out.stderr)


if __name__ == "__main__":
    unittest.main()
