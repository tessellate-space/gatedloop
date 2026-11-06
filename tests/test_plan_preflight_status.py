"""`gates plan status <change> [--json|--markdown]` (openspec change
`plan-preflight`, design D4; task 6.2).

The loop's state is computed from the rows, never declared: `green` when
the latest round has `clean` from every checker its tier runs, `question`
when a checker recorded one, `stalled` past the budget, `amended` for a
light pass with findings, `open` otherwise. It says when the plan moved
after its last green round, and `--markdown` is a block for a PR body.

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

LENS = "lens:gatedloop.implementability"


class PlanStatusTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.r = PreflightRepo(self.tmp / "work")
        self.assertEqual(self.r.gates("plan", "classify", CHANGE, "--unavailable", "x").returncode, 0)

    def tearDown(self):
        self._tmp.cleanup()

    def ok(self, *args, code=0):
        out = self.r.gates("plan", *args)
        self.assertEqual(out.returncode, code, out.stdout + out.stderr)
        return out

    def status(self) -> dict:
        return json.loads(self.ok("status", CHANGE, "--json").stdout)

    def test_open_then_green(self):
        self.ok("round", CHANGE)
        self.assertEqual(self.status()["state"], "open")
        report = write(self.tmp, "lens.md", "no findings\n")
        self.ok("record", CHANGE, "--checker", LENS, "--verdict", "clean", "--report", str(report))
        doc = self.status()
        self.assertEqual(doc["state"], "green")
        rnd = doc["loops"][0]["rounds"][0]
        self.assertEqual(rnd["checkers"][LENS]["verdict"], "clean")
        self.assertTrue(rnd["checkers"][LENS]["report"].endswith("1.1-lens-gatedloop.implementability.md"))
        self.assertFalse(doc["green_round_moved"])

    def test_question(self):
        self.ok("round", CHANGE)
        self.ok("record", CHANGE, "--checker", LENS, "--verdict", "question")
        self.assertEqual(self.status()["state"], "question")

    def test_a_light_pass_with_findings_is_amended(self):
        self.ok("round", CHANGE)
        self.ok("record", CHANGE, "--checker", LENS, "--verdict", "findings")
        self.assertEqual(self.status()["state"], "amended")

    def test_stalled_then_resumed(self):
        self.ok("round", CHANGE)
        self.ok("round", CHANGE, code=1)
        self.assertEqual(self.status()["state"], "stalled")
        self.ok("resume", CHANGE, "--reason", "continue past the stall, per review")
        doc = self.status()
        self.assertEqual(doc["state"], "open")
        self.assertEqual([lp["resume"] for lp in doc["loops"]],
                         [None, "continue past the stall, per review"])

    def test_the_digest_moved_line(self):
        self.ok("round", CHANGE)
        self.ok("record", CHANGE, "--checker", LENS, "--verdict", "clean")
        self.r.edit(f"{self.r.rel_dir}/tasks.md", "Add the widget", "Add the small widget")
        self.assertTrue(self.status()["green_round_moved"])
        self.assertIn("moved since its last green round", self.ok("status", CHANGE).stdout)

    def test_the_markdown_block(self):
        self.ok("round", CHANGE)
        self.ok("record", CHANGE, "--checker", LENS, "--verdict", "clean")
        self.ok("save", CHANGE)
        md = self.ok("status", CHANGE, "--markdown").stdout
        self.assertTrue(md.startswith(f"### Plan preflight: `{CHANGE}` — **green**"), md)
        self.assertIn("round 1 — plan ", md)
        self.assertIn("classifier builtin (none-declared)", md)
        self.assertIn(f"  - {LENS}: clean", md)
        self.assertRegex(md, rf"`gatedloop/preflight/{CHANGE}` at [0-9a-f]{{12}}")


if __name__ == "__main__":
    unittest.main()
