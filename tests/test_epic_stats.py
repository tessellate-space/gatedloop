"""`epic-linkage` task 3.2 (design D6): `gates stats --epic <name> [--json]`
groups the existing per-change economics by child and totals them: per child
its state, tasks done of total, gate runs, gate milliseconds, red runs and
halts by cause.

JSON shape fixed by these tests:
    {"epic", "children": [{"change", "state", "halt_cause", "tasks",
                           "gate_runs", "gate_ms", "red_runs", "halts"}],
     "totals": {"tasks", "gate_runs", "gate_ms", "red_runs", "halts"}}

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epic_fixture import EpicRepo, row  # noqa: E402

EPIC = "autonomous-dev"


class TestEpicStats(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = EpicRepo(self._tmp.name)
        self.repo.change(EPIC)
        self.repo.change("lane-permissions", epic=EPIC, approved=True, tasks=(1, 3))
        self.repo.ledger(
            "lane-permissions",
            row("task-start", 0, task="1.1"),
            row("unit", 1, task="1.1", exit=1, duration_ms=60000),
            row("unit", 3, task="1.1", exit=0, duration_ms=120000),
            row("ci", 6, task="1.1", exit=0, duration_ms=180000),
            row("task-start", 10, task="1.2"),
            row("halt", 11, task="1.2", cause="weak-spec"),
        )
        self.repo.change("ledger-rollup", epic=EPIC, approved=True, tasks=(2, 2))
        self.repo.ledger(
            "ledger-rollup",
            row("task-start", 0, task="1.1"),
            row("ci", 1, task="1.1", exit=1, duration_ms=60000),
            row("ci", 2, task="1.1", exit=0, duration_ms=60000),
            row("ready", 4),
        )
        self.repo.change("not-started", epic=EPIC, approved=True, tasks=(0, 4))
        self.repo.change("elsewhere")
        self.repo.ledger("elsewhere", row("ci", 1, exit=1, duration_ms=999000))
        self.repo.commit("changes")

    def tearDown(self):
        self._tmp.cleanup()

    def test_per_child_economics_and_totals(self):
        doc = self.repo.gates_json("stats", "--epic", EPIC, "--json")
        self.assertEqual(doc["epic"], EPIC)
        kids = {c["change"]: c for c in doc["children"]}
        self.assertEqual(sorted(kids), ["lane-permissions", "ledger-rollup", "not-started"])

        lane = kids["lane-permissions"]
        self.assertEqual(lane["state"], "halted")
        self.assertEqual(lane["tasks"], {"done": 1, "total": 3})
        self.assertEqual((lane["gate_runs"], lane["gate_ms"], lane["red_runs"]), (3, 360000, 1))
        self.assertEqual(lane["halts"].get("weak-spec"), 1)

        rollup = kids["ledger-rollup"]
        self.assertEqual(rollup["state"], "ready")
        self.assertEqual((rollup["gate_runs"], rollup["gate_ms"], rollup["red_runs"]), (2, 120000, 1))
        self.assertEqual(sum(rollup["halts"].values()), 0)

        idle = kids["not-started"]
        self.assertEqual(idle["state"], "approved")
        self.assertEqual((idle["gate_runs"], idle["gate_ms"], idle["red_runs"]), (0, 0, 0))

        totals = doc["totals"]
        self.assertEqual(totals["tasks"], {"done": 3, "total": 9})
        self.assertEqual((totals["gate_runs"], totals["gate_ms"], totals["red_runs"]), (5, 480000, 2))
        self.assertEqual(totals["halts"].get("weak-spec"), 1)
        self.assertEqual(sum(totals["halts"].values()), 1)

    def test_the_human_report_names_every_child(self):
        r = self.repo.gates("stats", "--epic", EPIC)
        self.assertEqual(r.returncode, 0, r.stderr)
        for child in ("lane-permissions", "ledger-rollup", "not-started"):
            self.assertIn(child, r.stdout)
        self.assertNotIn("elsewhere", r.stdout)

    def test_a_name_no_change_claims_as_epic_fails_loud(self):
        r = self.repo.gates("stats", "--epic", "elsewhere", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("elsewhere", r.stderr)


if __name__ == "__main__":
    unittest.main()
