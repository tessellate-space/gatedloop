"""`hooks/continue-loop.sh` flushes the task in flight at every stop
(openspec change `token-ledger`, design D1 and D2; the token-accounting
delta's "The session stop flushes the task in flight").

The flush runs before the continue decision and on every stop, including a
re-invoked one. A row that only appends usage to the ledger is not a task left
mid-edit: the loop still continues from a clean task boundary, and a fresh
restart is still allowed from one.

Stdlib only, per `zero-dep-shim`. The hook runs as a subprocess against a
throwaway git repo, fed the JSON a host would send it.
Run with: python3 -m unittest discover -s tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import (  # noqa: E402
    HOOKS, MODEL_A, SESSION, assistant, at, change_repo, counts, env, git,
    run_gates, seed, task_start, usage_rows, write_transcript,
)


def _stop(root, transcript=None, active=False):
    payload = {"session_id": SESSION, "stop_hook_active": active,
               "hook_event_name": "Stop"}
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    return subprocess.run(["bash", str(HOOKS / "continue-loop.sh")], input=json.dumps(payload),
                          cwd=root, capture_output=True, text=True,
                          env=env(CLAUDE_PROJECT_DIR=str(root)), timeout=120)


def _commit_ledger(root, msg):
    """Commit the ledger at a gated boundary, as the loop does: a green `ci`
    on the tree first, so the Stop hook's audit finds nothing to taint."""
    r = run_gates(root, "run", "ci")
    assert r.returncode == 0, r.stderr
    git(root, "add", ".gatedloop/runs")
    git(root, "commit", "-m", msg)


class TestTheStopFlush(unittest.TestCase):
    def test_a_halt_followed_by_a_stop_leaves_a_usage_row(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            r = run_gates(root, "halt", "record", "weak-spec", "--task", "1.1")
            self.assertEqual(r.returncode, 0, r.stderr)
            _commit_ledger(root, "record halt")
            path = write_transcript(tdir, [assistant(at(5), input=30, output=4)])
            r = _stop(root, path)
            self.assertEqual(r.returncode, 0, r.stderr)
            (row,) = usage_rows(root)
            self.assertEqual(row["task"], "1.1")
            self.assertEqual(row["tokens"], {MODEL_A: counts(input=30, output=4)})
            self.assertNotIn('"decision"', r.stdout, "a halted change does not continue")

    def test_a_reinvoked_stop_still_flushes(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            _commit_ledger(root, "task start")
            path = write_transcript(tdir, [assistant(at(5), input=2)])
            _stop(root, path, active=True)
            self.assertEqual(len(usage_rows(root)), 1)

    def test_no_task_in_flight_is_flushed_as_task_null(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, {"ts": at(0), "gate": "tests-handoff", "task": None, "exit": 0})
            _commit_ledger(root, "handoff")
            path = write_transcript(tdir, [assistant(at(5), output=9)])
            _stop(root, path)
            (row,) = usage_rows(root)
            self.assertIsNone(row["task"])
            self.assertEqual(row["tokens"], {MODEL_A: counts(output=9)})


class TestAFlushIsNotWorkInProgress(unittest.TestCase):
    def test_the_loop_still_continues_from_a_clean_boundary(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            _commit_ledger(root, "task start")
            path = write_transcript(tdir, [assistant(at(5), input=2)])
            r = _stop(root, path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(usage_rows(root)), 1)
            decision = json.loads(r.stdout)
            self.assertEqual(decision["decision"], "block")
            self.assertIn("1.1", decision["reason"])

    def test_real_edits_still_stop_the_loop(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            _commit_ledger(root, "task start")
            (root / "openspec" / "changes" / "my-change" / "tasks.md").write_text("edited\n- [ ] 1.1 x\n")
            path = write_transcript(tdir, [assistant(at(5), input=2)])
            r = _stop(root, path)
            self.assertNotIn('"decision"', r.stdout)

    def test_a_restart_is_allowed_after_a_flush(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            _commit_ledger(root, "task start")
            path = write_transcript(tdir, [assistant(at(5), input=2)])
            _stop(root, path)
            self.assertEqual(len(usage_rows(root)), 1)
            r = run_gates(root, "attempt", "restart", "1.1")
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
