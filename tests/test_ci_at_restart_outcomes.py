"""A restart's recovery under `loop.ci-at: ready` (openspec change `ci-at`,
design D5; the escalation-record delta's "A stalled halt says whether a fresh
restart remains" requirement).

Under `ready` a task reaches its commit on a green `unit`, with no `ci` run
of its own, so reading recovery from `ci` alone would count every recovered
restart as zero. The regressions: that, and `task` starting to count a green
`unit`.

The arithmetic is the pure `outcomes_from_rows`; one CLI run confirms
`gates stats --outcomes` reads the mode from the manifest.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
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

_loader = importlib.machinery.SourceFileLoader("gates_shim_ci_at_restart_outcomes", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

TS = "2026-10-01T00:00:00+00:00"
CHANGE = "ready-restart"


def row(gate, task=None, **kw):
    r = {"ts": TS, "gate": gate, "task": task, "session": "agent", "exit": None,
         "change": CHANGE}
    r.update(kw)
    return r


def restarted_then_green_unit():
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


class TestRecoveryReadsTheCommitGate(unittest.TestCase):
    def test_under_ready_a_green_unit_recovers_the_restart(self):
        out = gates.outcomes_from_rows(restarted_then_green_unit(), ci_at="ready")
        self.assertEqual((out["restarts"], out["restart_recovered"]), (1, 1))
        self.assertEqual(out["interventions"]["ask"], 0)

    def test_under_task_a_green_unit_does_not(self):
        out = gates.outcomes_from_rows(restarted_then_green_unit())
        self.assertEqual((out["restarts"], out["restart_recovered"]), (1, 0))
        out = gates.outcomes_from_rows(restarted_then_green_unit(), ci_at="task")
        self.assertEqual((out["restarts"], out["restart_recovered"]), (1, 0))

    def test_under_ready_a_green_ci_still_recovers_it(self):
        rows = restarted_then_green_unit()[:-1] + [row("ci", "1.2", exit=0)]
        out = gates.outcomes_from_rows(rows, ci_at="ready")
        self.assertEqual(out["restart_recovered"], 1)

    def test_under_ready_a_halt_before_the_green_still_means_not_recovered(self):
        rows = restarted_then_green_unit()[:-1] + [
            row("halt", "1.2", cause="stalled", restart_available=False),
            row("unit", "1.2", exit=0)]
        out = gates.outcomes_from_rows(rows, ci_at="ready")
        self.assertEqual(out["restart_recovered"], 0)


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


class TestTheCliReadsTheMode(unittest.TestCase):
    def _recovered(self, manifest):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True,
                           capture_output=True, env=_env())
            (root / ".gates.yaml").write_text(manifest)
            ledger = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text("".join(json.dumps(r) + "\n" for r in restarted_then_green_unit()))
            r = subprocess.run(
                [sys.executable, str(GATES_SHIM), "stats", "--outcomes", "--change", CHANGE,
                 "--json"], cwd=root, capture_output=True, text=True, env=_env(), timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            doc = json.loads(r.stdout)
            return doc["changes"][0]["restart_recovered"]

    def test_ready_counts_the_green_unit(self):
        self.assertEqual(self._recovered(
            'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\nloop:\n  ci-at: ready\n'), 1)

    def test_task_does_not(self):
        self.assertEqual(self._recovered('gatesVersion: 1\ngates:\n  ci: "true"\n'), 0)


if __name__ == "__main__":
    unittest.main()
