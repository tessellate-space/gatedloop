"""The token budget, refused in `gates run` (openspec change `token-ledger`,
design D5; the token-accounting delta's "A token budget is enforced in code").

Once the change's recorded usage reaches `loop.token-budget`, a task-bearing
`gates run unit` or `gates run ci` refuses with exit 1 without running the
gate, naming the budget, the recorded spend, that the task in flight is only
counted at its commit or the session stop, and the halt to record. `--full`
(the merge lane's proof) and a run with no task are never budgeted, and
without the key nothing is.

Stdlib only, per `zero-dep-shim`. The gate command touches a `ran` file, so
"refused without running the gate" is observable.
Run with: python3 -m unittest discover -s tests
"""

import argparse
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import (  # noqa: E402
    MODEL_A, MODEL_B, at, change_repo, counts, git, load_shim, run_gates, seed,
    task_start, usage_row,
)

gates = load_shim("gates_shim_token_budget_refusal")

GATE = "sh -c 'touch ran'"


def _manifest(loop_block):
    return f'gatesVersion: 1\ngates:\n  ci: "{GATE}"\n  unit: "{GATE}"\n' + loop_block


BUDGET = "loop:\n  token-budget: 2000000\n"


def _repo(tmp, loop_block=BUDGET, spent=2_100_000, task_started=True):
    root = change_repo(tmp, manifest=_manifest(loop_block))
    (root / ".gitignore").write_text("ran\n")
    git(root, "add", ".gitignore")
    git(root, "commit", "-m", "ignore")
    if task_started:
        seed(root, task_start(at(0), "1.3"))
    seed(root,
         usage_row(at(1), "1.1", {MODEL_A: counts(input=spent - 100_000)}),
         usage_row(at(2), "1.2", {MODEL_B: counts(cache_read=100_000)}),
         usage_row(at(3), "1.2", None, source="no-transcript"))
    return root


def _ran(root):
    return (root / "ran").exists()


class TestTheRefusal(unittest.TestCase):
    def test_at_or_over_the_budget_a_task_run_refuses_without_running(self):
        for spent in (2_000_000, 2_100_000):
            for gate in ("unit", "ci"):
                with self.subTest(spent=spent, gate=gate), tempfile.TemporaryDirectory() as tmp:
                    root = _repo(tmp, spent=spent)
                    r = run_gates(root, "run", gate, "--task", "1.3")
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertFalse(_ran(root), "the gate must not run")
                    self.assertIn("2000000", r.stderr)
                    self.assertIn(str(spent), r.stderr)
                    self.assertIn("gates halt record budget", r.stderr)
                    self.assertIn("in flight", r.stderr)

    def test_the_task_in_flight_is_budgeted_without_task_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = run_gates(root, "run", "unit")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse(_ran(root))


class TestWhatIsNeverBudgeted(unittest.TestCase):
    def test_below_the_budget_the_gate_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, spent=1_999_999)
            r = run_gates(root, "run", "unit", "--task", "1.3")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(_ran(root))

    def test_full_is_never_budgeted(self):
        """`full` is the merge lane's unscoped proof (`gates merge` step 3 runs
        it in-process); it has no command-line flag, so it is driven here the
        way the merge drives it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            m = gates._load(root / ".gates.yaml")
            args = argparse.Namespace(
                gate="ci", gate_args=[], changed=None, all=False, change=None, task="1.3",
                attempt=None, verbose=False, full=True, merge_priority=True)
            cwd = os.getcwd()
            os.chdir(root)
            try:
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    rc = gates.cmd_run(m, root, args)
            finally:
                os.chdir(cwd)
            self.assertEqual(rc, 0)
            self.assertTrue(_ran(root))

    def test_a_run_with_no_task_is_never_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, task_started=False)
            r = run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(_ran(root))

    def test_without_the_key_nothing_is_budgeted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, loop_block="")
            r = run_gates(root, "run", "unit", "--task", "1.3")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(_ran(root))


if __name__ == "__main__":
    unittest.main()
