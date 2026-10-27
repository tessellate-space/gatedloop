"""`loop.token-budget` in the manifest and the `budget` halt cause (openspec
change `token-ledger`, design D5; the escalation-record delta's "A budget halt
is accepted" and the gate-economics delta's "A budget halt in the outcomes
view").

`loop.token-budget` is optional and, when present, a positive integer of
tokens per change. `budget` joins the closed cause set: a halt recorded with it
is written, and `gates stats --outcomes` counts it under halts by cause.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import (  # noqa: E402
    CHANGE, at, change_repo, load_shim, rows, run_gates, seed, task_start,
)

gates = load_shim("gates_shim_token_budget_cause")

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _loop_errors(loop_block):
    m = gates._mini_yaml(BASE + loop_block)
    with tempfile.TemporaryDirectory() as tmp:
        return [e for e in gates._errors(m, Path(tmp)) if "loop" in e]


class TestTheBudgetKey(unittest.TestCase):
    def test_a_positive_integer_is_valid_and_absence_is_too(self):
        self.assertEqual(_loop_errors("loop:\n  token-budget: 2000000\n"), [])
        self.assertEqual(_loop_errors(""), [])

    def test_anything_but_a_positive_integer_is_refused(self):
        for value in ("0", "-5", "1.5", "true", '"lots"'):
            with self.subTest(value):
                errs = _loop_errors(f"loop:\n  token-budget: {value}\n")
                self.assertTrue(any("loop.token-budget" in e for e in errs), errs)


class TestTheBudgetCause(unittest.TestCase):
    def test_a_budget_halt_round_trips_into_the_outcomes_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.2"))
            r = run_gates(root, "halt", "record", "budget", "--task", "1.2")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(rows(root)[-1]["cause"], "budget")
            r = run_gates(root, "stats", "--outcomes", "--change", CHANGE, "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            (c,) = json.loads(r.stdout)["changes"]
            self.assertEqual(c["halts"]["budget"], 1)
            self.assertEqual(c["halt_cause"], "budget")
            table = run_gates(root, "stats", "--outcomes", "--change", CHANGE).stdout
            self.assertIn("budget: 1", table)


if __name__ == "__main__":
    unittest.main()
