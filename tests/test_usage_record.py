"""`gates usage record` and `gates usage show` (openspec change `token-ledger`,
design D1, D2 and D7; the token-accounting delta).

A record appends one `usage` row for a task: the window runs from the later
of the task's latest `task-start` and its latest *counted* usage row to now,
and only assistant entries inside it count. A row with null counts (no
readable transcript) never moves the window, so a later readable record still
covers that span (design D7: "the stop flush covers the window"). With no task
in flight the row is `task: null`, bounded below by the change's first ledger
row. A missing source is a row with null counts and exit 0, never a failure.

Stdlib only, per `zero-dep-shim`. Throwaway git repos, shim driven as a
subprocess. Run with: python3 -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import (  # noqa: E402
    CHANGE, MODEL_A, SECRET, assistant, at, change_repo, counts, git, ledger,
    run_gates, seed, task_start, token_total, usage_row, usage_rows,
    write_transcript,
)


def _record(root, *args):
    return run_gates(root, "usage", "record", *args)


class TestTheWindow(unittest.TestCase):
    def test_the_window_starts_at_the_task_start(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(10), "1.1"))
            path = write_transcript(tdir, [
                assistant(at(5), input=1000),   # before the task began
                assistant(at(12), input=7, output=3),
            ])
            r = _record(root, "--transcript", str(path))
            self.assertEqual(r.returncode, 0, r.stderr)
            (row,) = usage_rows(root)
            self.assertEqual(row["task"], "1.1", "the task in flight")
            self.assertEqual(row["source"], "claude-code-transcript")
            self.assertEqual(row["messages"], 1)
            self.assertEqual(row["tokens"], {MODEL_A: counts(input=7, output=3)})
            self.assertEqual(row["window"]["from"], at(10))
            self.assertTrue(row["window"]["to"])

    def test_the_window_starts_after_the_previous_counted_usage_row(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"),
                 usage_row(at(20), "1.1", {MODEL_A: counts(input=5)}, window_from=at(0)))
            path = write_transcript(tdir, [
                assistant(at(15), input=5),     # already in the earlier row
                assistant(at(25), input=40),
            ])
            _record(root, "--task", "1.1", "--transcript", str(path))
            latest = usage_rows(root)[-1]
            self.assertEqual(latest["window"]["from"], at(20))
            self.assertEqual(latest["tokens"], {MODEL_A: counts(input=40)})

    def test_a_null_count_row_does_not_move_the_window(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"),
                 usage_row(at(30), "1.1", None, window_from=at(0), source="no-transcript"))
            path = write_transcript(tdir, [assistant(at(10), input=9)])
            _record(root, "--transcript", str(path))
            latest = usage_rows(root)[-1]
            self.assertEqual(latest["window"]["from"], at(0))
            self.assertEqual(latest["tokens"], {MODEL_A: counts(input=9)})

    def test_a_second_flush_with_nothing_new_counts_zero(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            path = write_transcript(tdir, [assistant(at(3), input=11, output=2)])
            _record(root, "--transcript", str(path))
            _record(root, "--transcript", str(path))
            first, second = usage_rows(root)
            self.assertEqual(token_total(first["tokens"]), 13)
            self.assertEqual(second["messages"], 0)
            self.assertEqual(token_total(second["tokens"]), 0)
            show = json.loads(run_gates(root, "usage", "show", "--json").stdout)
            self.assertEqual(show["total"], 13)

    def test_no_task_start_records_task_null_from_the_first_ledger_row(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, {"ts": at(30), "gate": "tests-handoff", "task": None, "exit": 0})
            path = write_transcript(tdir, [
                assistant(at(10), input=500),   # before this change's ledger began
                assistant(at(40), output=6),
            ])
            r = _record(root, "--transcript", str(path))
            self.assertEqual(r.returncode, 0, r.stderr)
            (row,) = usage_rows(root)
            self.assertIsNone(row["task"])
            self.assertEqual(row["tokens"], {MODEL_A: counts(output=6)})


class TestMissingSources(unittest.TestCase):
    def test_no_transcript_is_a_null_row_and_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            r = _record(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            (row,) = usage_rows(root)
            self.assertEqual(row["source"], "no-transcript")
            self.assertIsNone(row["tokens"])
            self.assertIsNone(row["messages"])
            self.assertTrue(row["detail"])

    def test_an_unreadable_transcript_is_a_null_row_and_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            bad = Path(tdir) / "bad.jsonl"
            bad.write_text("not json at all\n")
            r = _record(root, "--transcript", str(bad))
            self.assertEqual(r.returncode, 0, r.stderr)
            (row,) = usage_rows(root)
            self.assertEqual(row["source"], "unreadable-transcript")
            self.assertIsNone(row["tokens"])
            self.assertTrue(row["detail"])

    def test_off_a_change_branch_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            git(root, "add", "-A")
            git(root, "commit", "-m", "ledger")
            git(root, "checkout", "main")
            r = _record(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(ledger(root).exists())

    def test_a_change_with_no_ledger_yet_gets_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            r = _record(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(ledger(root).exists())


class TestCountsOnly(unittest.TestCase):
    def test_no_transcript_text_reaches_the_ledger(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as tdir:
            root = change_repo(tmp)
            seed(root, task_start(at(0), "1.1"))
            path = write_transcript(tdir, [assistant(at(2), input=1)])
            _record(root, "--transcript", str(path))
            self.assertNotIn(SECRET, ledger(root).read_text())


class TestShow(unittest.TestCase):
    def test_show_totals_the_change_by_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = change_repo(tmp)
            seed(root,
                 usage_row(at(1), "1.1", {MODEL_A: counts(input=10, output=5)}),
                 usage_row(at(2), "1.2", {MODEL_A: counts(cache_read=100)}),
                 usage_row(at(3), None, None, source="no-transcript"))
            r = run_gates(root, "usage", "show", "--change", CHANGE, "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(r.stdout)
            self.assertEqual(doc["change"], CHANGE)
            self.assertEqual(doc["total"], 115)
            self.assertEqual(len(doc["rows"]), 3)
            human = run_gates(root, "usage", "show").stdout
            self.assertIn("1.1", human)
            self.assertIn("no-transcript", human)
            self.assertIn("115", human)


if __name__ == "__main__":
    unittest.main()
