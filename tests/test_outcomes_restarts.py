"""`gates stats --outcomes` counts restarts (openspec change `retry-budget`,
design D6; the escalation-record delta's "A stalled halt says whether a fresh
restart remains" requirement, its outcomes half).

Stdlib only, per `zero-dep-shim`. The arithmetic is the pure
`outcomes_from_rows`, tested directly; one CLI test confirms the human report
carries the counts.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_outcomes_restarts", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

TS = "2026-10-01T00:00:00+00:00"


def row(gate, task=None, **kw):
    r = {"ts": TS, "gate": gate, "task": task, "session": "agent", "exit": None}
    r.update(kw)
    return r


def stalled_then_restarted():
    return [
        row("task-start", "1.2", tree="a" * 40),
        row("unit", "1.2", exit=1),
        row("unit", "1.2", exit=1),
        row("unit", "1.2", exit=1),
        row("halt", "1.2", cause="stalled", restart_available=True),
        row("restart", "1.2"),
        row("task-start", "1.2", tree="a" * 40),
        row("unit", "1.2", exit=1),
        row("unit", "1.2", exit=0),
    ]


class TestRestartOutcomes(unittest.TestCase):
    def test_no_restart_reads_zero(self):
        out = gates.outcomes_from_rows([row("task-start", "1.1", tree="a" * 40),
                                        row("ci", "1.1", exit=0)])
        self.assertEqual(out["restarts"], 0)
        self.assertEqual(out["restart_recovered"], 0)

    def test_a_restart_that_recovered(self):
        rows = stalled_then_restarted() + [row("ci", "1.2", exit=0)]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(out["restarts"], 1)
        self.assertEqual(out["restart_recovered"], 1)
        self.assertEqual(sum(out["interventions"].values()), 0,
                         "a restart is never an intervention")

    def test_a_restart_with_no_green_ci_did_not_recover(self):
        out = gates.outcomes_from_rows(stalled_then_restarted())
        self.assertEqual(out["restarts"], 1)
        self.assertEqual(out["restart_recovered"], 0)

    def test_a_restart_that_halted_again_did_not_recover(self):
        rows = stalled_then_restarted() + [
            row("ci", "1.2", exit=1), row("ci", "1.2", exit=1),
            row("halt", "1.2", cause="stalled", restart_available=False),
        ]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(out["restarts"], 1)
        self.assertEqual(out["restart_recovered"], 0)

    def test_a_green_ci_of_another_task_does_not_recover_it(self):
        rows = stalled_then_restarted() + [row("ci", "1.3", exit=0)]
        self.assertEqual(gates.outcomes_from_rows(rows)["restart_recovered"], 0)

    def test_a_green_ci_before_the_restart_does_not_count(self):
        rows = [row("task-start", "1.2", tree="a" * 40), row("unit", "1.2", exit=1),
                row("ci", "1.2", exit=0), row("ci", "1.2", exit=1),
                row("ci", "1.2", exit=1), row("halt", "1.2", cause="stalled"),
                row("restart", "1.2")]
        self.assertEqual(gates.outcomes_from_rows(rows)["restart_recovered"], 0)


class TestRestartOutcomesCli(unittest.TestCase):
    def test_the_report_carries_restart_counts(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env["CLAUDECODE"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True,
                           capture_output=True, env=env)
            (root / ".gates.yaml").write_text('gatesVersion: 1\ngates:\n  ci: "true"\n')
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True)
            ledger = root / ".gatedloop" / "runs" / "my-change.jsonl"
            ledger.parent.mkdir(parents=True)
            rows = stalled_then_restarted() + [row("ci", "1.2", exit=0)]
            ledger.write_text("".join(json.dumps(dict(r, change="my-change")) + "\n"
                                      for r in rows))
            r = subprocess.run(
                [sys.executable, str(GATES_SHIM), "stats", "--outcomes", "--change", "my-change",
                 "--json"],
                cwd=root, capture_output=True, text=True, env=env, timeout=60,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(r.stdout)
            change = doc["changes"][0]
            self.assertEqual((change["restarts"], change["restart_recovered"]), (1, 1))

            r = subprocess.run(
                [sys.executable, str(GATES_SHIM), "stats", "--outcomes", "--change", "my-change"],
                cwd=root, capture_output=True, text=True, env=env, timeout=60,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("restarts", r.stdout)


if __name__ == "__main__":
    unittest.main()
