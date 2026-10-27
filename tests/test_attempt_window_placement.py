"""The failed-attempt window starts at the task's latest placement (change
`unblock-authored-lock`, design D6; issue #56, "seen at the same time").

A `setup` defect cycle ran the task's tests red against a fixture that was
wrong, re-handed off, placed again, and ran red once more, the first red
run against the right tests; `gates run ci --task` was then refused for a
used budget before anything had been implemented. The regressions: the red
runs before a re-placement counted as attempts, the first red run after it
not taken as the task's red run, and a window that ignores the task's
latest `task-start` when it comes after the placement.

The counter is pure, so it is tested on rows directly; one case drives the
shim to show that the gate runs.

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

_loader = importlib.machinery.SourceFileLoader("gates_shim_attempt_window", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "my-change"


def _row(gate, task="1.1", exit_code=None, **extra):
    return {"ts": "2026-10-27T00:00:00+00:00", "gate": gate, "exit": exit_code,
            "change": CHANGE, "task": task, **extra}


def _defect_cycle():
    """Task start, a placement, its red run, two more red runs against the
    wrong fixture, a `setup` defect, a re-handoff and a re-placement."""
    return [
        _row("task-start"),
        _row("tests-placed", tests={"1.1": {"tests/test_x.py": "a" * 40}}),
        _row("unit", exit_code=1),
        _row("unit", exit_code=1),
        _row("ci", exit_code=1),
        _row("test-defect", kind="setup", detail="imports a module that moved"),
        _row("tests-handoff", tests={"1.1": {"tests/test_x.py": "b" * 40}}),
        _row("tests-placed", tests={"1.1": {"tests/test_x.py": "b" * 40}}),
    ]


class AttemptWindowTest(unittest.TestCase):
    def test_a_defect_cycle_before_the_re_placement_spends_nothing(self):
        rows = _defect_cycle() + [_row("unit", exit_code=1)]

        red_seen, count = gates._attempt_state(rows, "1.1")

        self.assertTrue(red_seen)
        self.assertEqual(count, 0)
        self.assertEqual(gates.failed_attempt_count(rows, "1.1"), 0)

    def test_before_the_first_red_run_after_re_placement_no_red_run_is_seen(self):
        red_seen, count = gates._attempt_state(_defect_cycle(), "1.1")

        self.assertFalse(red_seen)
        self.assertEqual(count, 0)

    def test_failed_runs_after_the_new_red_run_still_count(self):
        rows = _defect_cycle() + [_row("unit", exit_code=1), _row("unit", exit_code=1),
                                  _row("ci", exit_code=1)]

        self.assertEqual(gates.failed_attempt_count(rows, "1.1"), 2)

    def test_a_later_task_start_still_opens_the_window(self):
        rows = _defect_cycle() + [_row("unit", exit_code=1), _row("unit", exit_code=1),
                                  _row("task-start"), _row("unit", exit_code=1)]

        red_seen, count = gates._attempt_state(rows, "1.1")

        self.assertTrue(red_seen)
        self.assertEqual(count, 0)

    def test_the_gate_runs_after_a_defect_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            env["CLAUDECODE"] = "1"
            for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.com"),
                         ("config", "user.name", "T")):
                subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, env=env)
            (root / ".gates.yaml").write_text(
                'gatesVersion: 1\ngates:\n  ci: "false"\n  unit: "false"\n')
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
            subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True, env=env)
            subprocess.run(["git", "checkout", "-q", "-b", CHANGE], cwd=root, check=True, env=env)
            (root / "openspec" / "changes" / CHANGE).mkdir(parents=True)
            ledger = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text("".join(json.dumps(r) + "\n" for r in
                                      _defect_cycle() + [_row("unit", exit_code=1)]))

            r = subprocess.run([sys.executable, str(GATES_SHIM), "run", "ci", "--task", "1.1"],
                               cwd=root, capture_output=True, text=True, env=env)

        self.assertNotIn("attempt budget", r.stdout + r.stderr)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
