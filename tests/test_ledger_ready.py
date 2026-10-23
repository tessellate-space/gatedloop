"""`gates ledger record-ready <change>` (design D4 of `merge-pull-request`).

Readiness used to exist only in the implementer's report, so an orchestrator
had to remember it. A `ready` row makes it a ledger fact any process with the
repository can read. The regressions: no row, a row that is not last (so a
reader comparing it to the latest `task-start` or `halt` misreads the lane),
and the row counted by `gates stats` as a gate run it never was.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, LEDGER_REL, MergeRepo, combined, rows_from_text


class RecordReadyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repo = MergeRepo(self.tmp)
        self.repo.start_change(lane=False)
        started = self.repo.gates("task", "start", "1.1")
        self.assertEqual(started.returncode, 0, combined(started))
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        self.repo.prove_head()

    def tearDown(self):
        self._tmp.cleanup()

    def _rows(self) -> list:
        return rows_from_text((self.repo.primary / LEDGER_REL).read_text())

    def test_the_ready_row_is_the_newest_row(self):
        r = self.repo.gates("ledger", "record-ready", CHANGE)

        self.assertEqual(r.returncode, 0, combined(r))
        last = self._rows()[-1]
        self.assertEqual((last.get("gate"), last.get("exit"), last.get("change")), ("ready", 0, CHANGE))
        self.assertTrue(last.get("ts"))

    def test_the_ready_row_is_not_a_gate_run(self):
        ready = self.repo.gates("ledger", "record-ready", CHANGE)
        self.assertEqual(ready.returncode, 0, combined(ready))

        r = self.repo.gates("stats", "--change", CHANGE, "--json")

        self.assertEqual(r.returncode, 0, combined(r))
        gates_seen = json.loads(r.stdout)["changes"][0]["gates"]
        self.assertNotIn("ready", gates_seen)
        self.assertIn("ci", gates_seen)


if __name__ == "__main__":
    unittest.main()
