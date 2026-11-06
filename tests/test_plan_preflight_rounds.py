"""`gates plan round`, `gates plan record` and `gates plan resume` (openspec
change `plan-preflight`, design D4, D5; task 6.1).

A round opens only on a plan with no static finding, and, on a light floor,
only once a classifier verdict (or a recorded `--unavailable` cause) exists
for the current digests. The budget is `rounds` under full and 1 under
light, counted from `plan-round` rows; past it a `stalled` row is appended
and the command exits 1. `record` refuses without an open round, after an
amendment, for a checker the tier does not run, and a `--verdict` for the
dry run, which it runs itself. `resume` starts a new loop with a fresh
budget and a recorded reason.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, MANIFEST, PreflightRepo, write  # noqa: E402

MODIFIED_SPEC = "# Spec Delta\n\n## MODIFIED Requirements\n\n### Requirement: X\n\nY.\n"
ECHO = "import os\nprint(os.environ['PF_VERDICT'])\n"
VERDICT = json.dumps({"tier": "light", "confidence": 0.4,
                      "evidence": [{"dimension": "persisted-data", "value": 0.9, "confidence": 0.6}],
                      "reason": None})


class PlanRoundTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def full(self, manifest=MANIFEST, **kw) -> PreflightRepo:
        """A plan whose floor is full (it modifies a requirement)."""
        return PreflightRepo(self.tmp / "full", manifest=manifest, specs={"widget": MODIFIED_SPEC}, **kw)

    def light(self, manifest=MANIFEST, **kw) -> PreflightRepo:
        return PreflightRepo(self.tmp / "light", manifest=manifest, **kw)

    def rounds(self, r) -> list[dict]:
        return [x for x in r.rows() if x["gate"] == "plan-round"]

    def reviews(self, r) -> list[dict]:
        return [x for x in r.rows() if x["gate"] == "plan-review"]

    def classify_unavailable(self, r):
        self.assertEqual(r.gates("plan", "classify", CHANGE, "--unavailable", "no lens").returncode, 0)

    def test_the_full_budget_then_a_stall(self):
        r = self.full(manifest=MANIFEST + "loop:\n  plan-preflight:\n    rounds: 2\n")
        for n in (1, 2):
            out = r.gates("plan", "round", CHANGE)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertIn(f"round {n} of 2", out.stdout)
        out = r.gates("plan", "round", CHANGE)
        self.assertEqual(out.returncode, 1)
        self.assertIn("stalled", out.stderr)
        self.assertEqual([x["outcome"] for x in self.rounds(r)], ["open", "open", "stalled"])
        self.assertEqual([x["checker"] for x in self.reviews(r)], ["plan-check", "plan-check"])

    def test_the_light_budget_is_one(self):
        r = self.light()
        self.classify_unavailable(r)
        self.assertEqual(r.gates("plan", "round", CHANGE).returncode, 0)
        self.assertEqual(r.gates("plan", "round", CHANGE).returncode, 1)
        self.assertEqual([x["outcome"] for x in self.rounds(r)], ["open", "stalled"])

    def test_a_round_row_carries_every_layer(self):
        script = write(self.tmp, "fixture/classify.py", ECHO)
        cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
        r = self.light(manifest=MANIFEST + "loop:\n  plan-preflight:\n    classifier: "
                       + json.dumps(cmd) + "\n    classifier-input-limit: 900\n")
        out = r.gates("plan", "round", CHANGE, PF_VERDICT=VERDICT)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        row = self.rounds(r)[0]
        self.assertEqual((row["loop"], row["round"], row["floor"], row["tier"]), (1, 1, "light", "full"))
        self.assertRegex(row["plan_sha"], r"^[0-9a-f]{64}$")
        self.assertRegex(row["tasks_sha"], r"^[0-9a-f]{64}$")
        c = row["classifier"]
        self.assertEqual((c["provider"], c["raised_by"], c["confidence"]), ("external", "persisted-data", 0.4))
        self.assertEqual(c["evidence"][0]["confidence"], 0.6)
        self.assertTrue(c["trimmed"], c)
        self.assertRegex(c["digest_sha"], r"^[0-9a-f]{64}$")
        self.assertEqual([s["id"] for s in row["signals"]][0], "tasks")

    def test_a_fallback_cause_is_in_the_row(self):
        r = self.light()
        write(self.tmp, "v.json", VERDICT)
        self.assertEqual(r.gates("plan", "classify", CHANGE, "--verdict", str(self.tmp / "v.json")).returncode, 0)
        self.assertEqual(r.gates("plan", "round", CHANGE).returncode, 0)
        c = self.rounds(r)[0]["classifier"]
        self.assertEqual((c["provider"], c["cause"], c["combined"]), ("builtin", "none-declared", "full"))

    def test_a_light_floor_needs_a_verdict(self):
        r = self.light()
        out = r.gates("plan", "round", CHANGE)
        self.assertEqual(out.returncode, 1)
        self.assertIn("classifier verdict", out.stderr)
        self.assertEqual(self.rounds(r), [])
        write(self.tmp, "v.json", VERDICT)
        self.assertEqual(r.gates("plan", "classify", CHANGE, "--verdict", str(self.tmp / "v.json")).returncode, 0)
        self.assertEqual(r.gates("plan", "round", CHANGE).returncode, 0)

    def test_a_skipped_classifier_needs_no_verdict(self):
        r = self.light(manifest=MANIFEST + "loop:\n  plan-preflight:\n    classifier-input-limit: 50\n")
        out = r.gates("plan", "round", CHANGE)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(self.rounds(r)[0]["classifier"]["provider"], "skipped")

    def test_static_findings_open_no_round(self):
        r = self.full(manifest=MANIFEST + "loop:\n  task-oracle: required\n",
                      tasks="- [ ] 1.1 Tagged [oracle: unit]\n- [ ] 3.2 Untagged\n")
        out = r.gates("plan", "round", CHANGE)
        self.assertEqual(out.returncode, 1)
        self.assertIn("3.2", out.stdout + out.stderr)
        self.assertEqual(r.rows(), [])

    def test_the_tier_flag_raises_and_is_recorded(self):
        r = self.light()
        self.classify_unavailable(r)
        self.assertEqual(r.gates("plan", "round", CHANGE, "--tier", "full").returncode, 0)
        row = self.rounds(r)[0]
        self.assertEqual((row["floor"], row["tier"], row["override"]["source"]),
                         ("light", "full", "raised-flag"))

    def test_resume_starts_loop_two_with_a_fresh_budget(self):
        r = self.light()
        self.classify_unavailable(r)
        self.assertEqual(r.gates("plan", "round", CHANGE).returncode, 0)
        self.assertEqual(r.gates("plan", "resume", CHANGE, "--reason", "  ").returncode, 1)
        out = r.gates("plan", "resume", CHANGE, "--reason", "retention: 30 days, per review")
        self.assertEqual(out.returncode, 0, out.stderr)
        out = r.gates("plan", "round", CHANGE)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        rows = self.rounds(r)
        self.assertEqual([(x["loop"], x["round"], x["outcome"]) for x in rows],
                         [(1, 1, "open"), (2, 0, "resume"), (2, 1, "open")])
        self.assertEqual(rows[1]["detail"], "retention: 30 days, per review")


class PlanRecordTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.r = PreflightRepo(self.tmp / "work", specs={"widget": MODIFIED_SPEC})

    def tearDown(self):
        self._tmp.cleanup()

    def record(self, *args):
        return self.r.gates("plan", "record", CHANGE, *args)

    def open_round(self):
        out = self.r.gates("plan", "round", CHANGE)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_no_open_round(self):
        out = self.record("--checker", "lens:gatedloop.implementability", "--verdict", "clean")
        self.assertEqual(out.returncode, 1)
        self.assertIn("no plan round is open", out.stderr)

    def test_an_amended_plan_needs_a_new_round(self):
        self.open_round()
        self.r.edit(f"{self.r.rel_dir}/tasks.md", "Add the widget", "Add the small widget")
        out = self.record("--checker", "lens:gatedloop.zero-decision", "--verdict", "clean")
        self.assertEqual(out.returncode, 1)
        self.assertIn("changed since round 1 opened", out.stderr)

    def test_a_checker_the_tier_does_not_run(self):
        r = PreflightRepo(self.tmp / "light")
        self.assertEqual(r.gates("plan", "classify", CHANGE, "--unavailable", "x").returncode, 0)
        self.assertEqual(r.gates("plan", "round", CHANGE).returncode, 0)
        out = r.gates("plan", "record", CHANGE, "--checker", "lens:gatedloop.zero-decision",
                      "--verdict", "clean")
        self.assertEqual(out.returncode, 1)
        self.assertIn("not one the round's light tier runs", out.stderr)

    def test_a_verdict_for_the_dry_run_is_refused(self):
        self.open_round()
        out = self.record("--checker", "dry-run", "--verdict", "clean")
        self.assertEqual(out.returncode, 1)
        self.assertIn("own run", out.stderr)

    def test_an_llm_checker_needs_a_verdict(self):
        self.open_round()
        self.assertEqual(self.record("--checker", "test-author").returncode, 1)

    def test_the_dry_run_is_recorded_from_its_own_exit(self):
        self.open_round()
        out = self.record("--checker", "dry-run")
        self.assertEqual(out.returncode, 1)
        self.assertEqual(self.r.gates("tests", "brief", CHANGE, "--preflight").returncode, 0)
        self.r.hold("1.1", "tests/test_widget.py.authored", "def test_widget():\n    assert False\n")
        self.r.hold("1.2", "tests/test_gadget.py.authored", "def test_gadget():\n    assert 2\n")
        self.r.hold("2.1", "NO-TESTS", "docs only\n")
        out = self.record("--checker", "dry-run")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        dry = [x for x in self.r.rows() if x.get("checker") == "dry-run"]
        self.assertEqual([x["verdict"] for x in dry], ["findings", "clean"])
        self.assertTrue((self.r.root / dry[1]["report"]).is_file())

    def test_a_report_is_copied_to_the_store(self):
        self.open_round()
        report = write(self.tmp, "lens.md", "lens:gatedloop.implementability #1 — fine\n")
        out = self.record("--checker", "lens:gatedloop.implementability", "--verdict", "findings",
                          "--report", str(report))
        self.assertEqual(out.returncode, 0, out.stderr)
        row = [x for x in self.r.rows() if (x.get("checker") or "").startswith("lens:")][0]
        self.assertEqual((self.r.root / row["report"]).read_text(), report.read_text())
        self.assertEqual((row["loop"], row["round"], row["verdict"]), (1, 1, "findings"))
        self.assertIn("snapshot", row)


if __name__ == "__main__":
    unittest.main()
