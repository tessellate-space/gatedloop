"""The Claude Code transcript adapter behind `usage` rows (openspec change
`token-ledger`, design D3; the token-accounting delta's "A usage row records a
task's token spend" and "A missing source is recorded, never a failure").

`transcript_usage(path, window_from, window_to)` reads the session transcript
at `path` and returns `{"source", "messages", "tokens", "detail"}`: per model,
the four counts of the assistant messages whose timestamp falls inside the
window (after `window_from`, at or before `window_to`; `None` for an open
start). Subagent turns count with the session, whether they sit in the main
file as sidechain entries or in sibling files under the session's directory.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import (  # noqa: E402
    MODEL_A, MODEL_B, OTHER_SESSION, assistant, at, load_shim, user,
    write_subagent, write_transcript,
)

gates = load_shim("gates_shim_usage_transcript")

NOW = at(0, day=20)


class TestTranscriptCounts(unittest.TestCase):
    def test_four_fields_summed_per_model_inside_the_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, [
                assistant(at(1), MODEL_A, input=1, output=2, cache_read=3, cache_write=4),
                user(at(2)),
                assistant(at(3), MODEL_A, input=10, output=20, cache_read=30, cache_write=40),
                assistant(at(4), MODEL_B, input=100, output=200, cache_read=300, cache_write=400),
            ])
            out = gates.transcript_usage(path, None, NOW)
        self.assertEqual(out["source"], "claude-code-transcript")
        self.assertEqual(out["messages"], 3)
        self.assertEqual(out["tokens"], {
            MODEL_A: {"input": 11, "output": 22, "cache_read": 33, "cache_write": 44},
            MODEL_B: {"input": 100, "output": 200, "cache_read": 300, "cache_write": 400},
        })

    def test_only_entries_inside_the_window_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, [
                assistant(at(5), input=1),     # at the start: already counted
                assistant(at(6), input=10),
                assistant(at(9), input=100),   # at the end: counted
                assistant(at(10), input=1000),
            ])
            out = gates.transcript_usage(path, at(5), at(9))
        self.assertEqual(out["messages"], 2)
        self.assertEqual(out["tokens"][MODEL_A]["input"], 110)

    def test_one_message_split_over_entries_counts_once(self):
        """The host writes one entry per content block, each repeating the
        message's usage under the same message id."""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, [
                assistant(at(1), input=5, output=7, msg_id="msg-1"),
                assistant(at(1), input=5, output=7, msg_id="msg-1"),
                assistant(at(2), input=1, output=1, msg_id="msg-2"),
            ])
            out = gates.transcript_usage(path, None, NOW)
        self.assertEqual(out["messages"], 2)
        self.assertEqual(out["tokens"][MODEL_A]["input"], 6)
        self.assertEqual(out["tokens"][MODEL_A]["output"], 8)

    def test_a_missing_field_reads_as_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, [
                assistant(at(1), usage={"input_tokens": 3, "output_tokens": 4}),
            ])
            out = gates.transcript_usage(path, None, NOW)
        self.assertEqual(out["source"], "claude-code-transcript")
        self.assertEqual(out["messages"], 1)
        self.assertEqual(out["tokens"][MODEL_A],
                         {"input": 3, "output": 4, "cache_read": 0, "cache_write": 0})

    def test_a_truncated_last_line_is_tolerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, [assistant(at(1), input=2)],
                                    tail='{"type": "assistant", "timest')
            out = gates.transcript_usage(path, None, NOW)
        self.assertEqual(out["source"], "claude-code-transcript")
        self.assertEqual(out["tokens"][MODEL_A]["input"], 2)


class TestSubagentTurns(unittest.TestCase):
    def test_sidechain_entries_and_sibling_files_count_with_the_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, [
                assistant(at(1), input=1),
                assistant(at(2), MODEL_B, input=2, sidechain=True, agent_id="a1"),
            ])
            write_subagent(tmp, "b2", [
                assistant(at(3), MODEL_B, input=4, sidechain=True, agent_id="b2"),
            ])
            out = gates.transcript_usage(path, None, NOW)
        self.assertEqual(out["messages"], 3)
        self.assertEqual(out["tokens"][MODEL_A]["input"], 1)
        self.assertEqual(out["tokens"][MODEL_B]["input"], 6)

    def test_a_sibling_file_of_another_session_is_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, [assistant(at(1), input=1)])
            write_subagent(tmp, "c3", [
                assistant(at(2), input=50, sidechain=True, session=OTHER_SESSION),
            ])
            out = gates.transcript_usage(path, None, NOW)
        self.assertEqual(out["messages"], 1)
        self.assertEqual(out["tokens"][MODEL_A]["input"], 1)


class TestMissingOrBrokenSource(unittest.TestCase):
    def test_an_unparsable_file_is_unreadable_with_null_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.jsonl"
            path.write_text("this is not json\n{also not\n")
            out = gates.transcript_usage(path, None, NOW)
        self.assertEqual(out["source"], "unreadable-transcript")
        self.assertIsNone(out["tokens"])
        self.assertIsNone(out["messages"])
        self.assertTrue(out["detail"])

    def test_no_path_or_a_missing_file_is_no_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in (None, Path(tmp) / "gone.jsonl"):
                out = gates.transcript_usage(path, None, NOW)
                self.assertEqual(out["source"], "no-transcript", path)
                self.assertIsNone(out["tokens"])
                self.assertIsNone(out["messages"])


class TestUsageIsNotAGateRun(unittest.TestCase):
    def test_a_usage_row_is_never_counted_as_a_gate(self):
        rows = [
            {"ts": at(0), "gate": "task-start", "task": "1.1"},
            {"ts": at(1), "gate": "ci", "task": "1.1", "exit": 0, "duration_ms": 1000},
            {"ts": at(2), "gate": "usage", "task": "1.1", "exit": None,
             "tokens": {MODEL_A: {"input": 1, "output": 1, "cache_read": 0, "cache_write": 0}}},
        ]
        out = gates.stats_from_rows(rows, 30 * 60000)
        self.assertEqual(set(out["gates"]), {"ci"})


if __name__ == "__main__":
    unittest.main()
