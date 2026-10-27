"""`hooks/gate-commit.sh` records the task's usage at its gated commit
(openspec change `token-ledger`, design D1; the token-accounting delta's "A
gated commit records the task's usage" and "A human session commits").

Once the commit passes the marker and the test lock, the hook hands the hook
input's `transcript_path` to `gates usage record` and stages the ledger, so the
row lands in the commit it costs. Nothing about recording can deny a commit:
a missing or broken transcript, or a ledger that cannot be written, leaves the
hook's allow verdict as it was. A denied commit records nothing.

Stdlib only, per `zero-dep-shim`. The hook runs as a subprocess against a
throwaway git repo, fed the JSON a host would send it.
Run with: python3 -m unittest discover -s tests
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import (  # noqa: E402
    HOOKS, MODEL_A, SESSION, assistant, at, change_repo, counts, env, git,
    ledger, run_gates, seed, task_start, usage_rows, write_transcript,
)


def _hook(root, transcript=None):
    payload = {"tool_input": {"command": "git commit -m work"}, "cwd": str(root),
               "session_id": SESSION, "hook_event_name": "PreToolUse"}
    if transcript is not None:
        payload["transcript_path"] = str(transcript)
    return subprocess.run(["bash", str(HOOKS / "gate-commit.sh")], input=json.dumps(payload),
                          cwd=root, capture_output=True, text=True, env=env(), timeout=120)


def _gated_work(root):
    """A task in flight with its work staged and a green `ci` on that tree."""
    seed(root, task_start(at(0), "1.1"))
    (root / "work.txt").write_text("work\n")
    git(root, "add", "work.txt")
    r = run_gates(root, "run", "ci", "--task", "1.1")
    assert r.returncode == 0, r.stderr


def _staged(root):
    return subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=root,
                          capture_output=True, text=True, env=env()).stdout.split()


class TestTheGatedCommitRecordsUsage(unittest.TestCase):
    def test_a_passing_commit_records_and_stages_the_tasks_usage(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            _gated_work(root)
            path = write_transcript(tdir, [assistant(at(4), input=12, output=8)])
            r = _hook(root, path)
            self.assertEqual(r.returncode, 0, r.stderr)
            (row,) = usage_rows(root)
            self.assertEqual(row["task"], "1.1")
            self.assertEqual(row["source"], "claude-code-transcript")
            self.assertEqual(row["tokens"], {MODEL_A: counts(input=12, output=8)})
            self.assertIn(".gatedloop/runs/my-change.jsonl", _staged(root))

    def test_no_transcript_path_still_allows_the_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            _gated_work(root)
            r = _hook(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            (row,) = usage_rows(root)
            self.assertEqual(row["source"], "no-transcript")
            self.assertIsNone(row["tokens"])

    def test_an_unreadable_transcript_still_allows_the_commit(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            _gated_work(root)
            bad = Path(tdir) / "bad.jsonl"
            bad.write_text("{{{{\n")
            r = _hook(root, bad)
            self.assertEqual(r.returncode, 0, r.stderr)
            (row,) = usage_rows(root)
            self.assertEqual(row["source"], "unreadable-transcript")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores file modes")
    def test_a_ledger_that_cannot_be_written_never_denies(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            _gated_work(root)
            path = write_transcript(tdir, [assistant(at(4), input=1)])
            mode = ledger(root).stat().st_mode
            ledger(root).chmod(stat.S_IRUSR)
            try:
                r = _hook(root, path)
            finally:
                ledger(root).chmod(mode)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(usage_rows(root), [])


class TestADeniedCommitRecordsNothing(unittest.TestCase):
    def test_no_green_ci_means_no_usage_row(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            (root / "work.txt").write_text("work\n")
            git(root, "add", "work.txt")
            path = write_transcript(tdir, [assistant(at(4), input=1)])
            r = _hook(root, path)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(usage_rows(root), [])


if __name__ == "__main__":
    unittest.main()
