"""Tests for `stats_from_rows`, the pure aggregation core behind `gates stats`
(design gates-stats D1/D2).

`stats_from_rows(rows, idle_gap_ms)` takes already-parsed ledger rows (the
same shape `_read_ledger_rows` produces) and an idle-gap threshold in
milliseconds, and returns a stats structure with no I/O, no git, and no
clock — a synthetic list of dicts is enough to exercise every metric.

Stdlib only, per `zero-dep-shim`. Run with:
    python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

# `bin/gates` has no `.py` suffix, so it is loaded by path (matches
# test_selection.py / test_manifest.py) to call `stats_from_rows` directly.
_loader = importlib.machinery.SourceFileLoader("gates_shim_stats", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

IDLE_GAP_MS = 30 * 60 * 1000  # design's default: 30 minutes


def row(ts, gate, exit=0, duration_ms=0, task=None, **extra):
    """A ledger row with only the fields a test cares about set explicitly;
    matches the shape `_read_ledger_rows` returns (a plain dict, possibly
    missing fields from other eras)."""
    r = {
        "ts": ts, "gate": gate, "exit": exit, "duration_ms": duration_ms,
        "change": "my-change", "task": task, "tree": None, "attempt": 1,
        "approved_by": None, "sha": None,
    }
    r.update(extra)
    return r


class TestGateVsEventClassification(unittest.TestCase):
    """Design D1: `gate` names the EVENT; five values are not gates (`merge`,
    `taint`, `taint-clear`, `review`, `task-start`) and are excluded from the
    per-gate table but still counted as events."""

    def test_gate_rows_and_event_rows_are_separated(self):
        rows = [
            row("2026-01-01T00:00:00+00:00", "ci", exit=0, duration_ms=1000),
            row("2026-01-01T00:01:00+00:00", "merge", exit=0, duration_ms=0),
            row("2026-01-01T00:02:00+00:00", "review", exit=0, duration_ms=0),
            row("2026-01-01T00:03:00+00:00", "task-start", exit=0, duration_ms=0),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertIn("ci", out["gates"])
        self.assertNotIn("merge", out["gates"])
        self.assertNotIn("review", out["gates"])
        self.assertNotIn("task-start", out["gates"])
        self.assertEqual(out["events"], {"merge": 1, "review": 1, "task-start": 1})
        self.assertEqual(out["gates"]["ci"]["runs"], 1)

    def test_halt_and_intervention_rows_are_never_gate_rows(self):
        """escalation-outcomes D2: a halt or intervention row contributes no
        gate time, no failed attempt and no green record."""
        rows = [
            row("2026-01-01T00:00:00+00:00", "ci", exit=0, duration_ms=1000),
            row("2026-01-01T00:01:00+00:00", "halt", exit=None, duration_ms=0,
                cause="stalled"),
            row("2026-01-01T00:02:00+00:00", "intervention", exit=None,
                duration_ms=0, cause="ask"),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(set(out["gates"]), {"ci"})
        self.assertEqual(out["events"], {"halt": 1, "intervention": 1})
        self.assertIn("halt", gates.NON_GATE_EVENTS)
        self.assertIn("intervention", gates.NON_GATE_EVENTS)


class TestFailedAttemptCounting(unittest.TestCase):
    def test_nonzero_exit_counts_as_failed_per_gate(self):
        rows = [
            row("2026-01-01T00:00:00+00:00", "ci", exit=1, duration_ms=500),
            row("2026-01-01T00:01:00+00:00", "ci", exit=1, duration_ms=500),
            row("2026-01-01T00:02:00+00:00", "ci", exit=0, duration_ms=500),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["gates"]["ci"]["runs"], 3)
        self.assertEqual(out["gates"]["ci"]["failed"], 2)


class TestIdleGapExclusion(unittest.TestCase):
    """Design D1: an interval longer than the idle threshold is excluded
    entirely from active loop time; the first row opens the window at zero
    elapsed."""

    def test_overnight_gap_excluded_shorter_gaps_summed(self):
        rows = [
            row("2026-01-01T09:00:00+00:00", "ci", duration_ms=0),
            row("2026-01-01T09:05:00+00:00", "ci", duration_ms=0),  # +5m, counted
            row("2026-01-02T09:05:00+00:00", "ci", duration_ms=0),  # +24h, excluded
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["active_ms"], 5 * 60 * 1000)


class TestSlowGateNoDoubleCount(unittest.TestCase):
    """Design Risks: a gate row's own duration lands *inside* the preceding
    interval (each row's `ts` is written at completion), so only the final
    row's duration is added on top — never both."""

    def test_intermediate_duration_not_added_on_top_of_interval(self):
        rows = [
            row("2026-01-01T09:00:00+00:00", "task-start", duration_ms=0),
            # This "ci" row's own execution (20 minutes) is already reflected
            # in the 20-minute gap between the two timestamps below — adding
            # its duration_ms again would double-count it.
            row("2026-01-01T09:20:00+00:00", "ci", duration_ms=20 * 60 * 1000),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        # One interval (20m) + the last row's own duration (20m, since it is
        # a gate row and is the final row) = 40m.
        self.assertEqual(out["active_ms"], 40 * 60 * 1000)

    def test_last_row_duration_added_once_when_it_is_a_gate_row(self):
        rows = [
            row("2026-01-01T09:00:00+00:00", "ci", duration_ms=1000),
            row("2026-01-01T09:01:00+00:00", "ci", duration_ms=2000),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        # interval (60s) + last row's own duration (2s) -- the first row's
        # 1000ms duration is never added on its own.
        self.assertEqual(out["active_ms"], 60 * 1000 + 2000)


class TestPerTaskAttribution(unittest.TestCase):
    """Design D1: per-task time is the active-time sum over intervals whose
    *ending* row carries that task id."""

    def test_interval_attributed_to_ending_rows_task(self):
        rows = [
            row("2026-01-01T09:00:00+00:00", "task-start", task="1.1"),
            row("2026-01-01T09:05:00+00:00", "ci", task="1.1", duration_ms=0),
            row("2026-01-01T09:15:00+00:00", "ci", task="1.2", duration_ms=0),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["tasks"]["1.1"]["active_ms"], 5 * 60 * 1000)
        self.assertEqual(out["tasks"]["1.2"]["active_ms"], 10 * 60 * 1000)

    def test_gate_time_and_failures_attributed_per_task(self):
        rows = [
            row("2026-01-01T09:00:00+00:00", "ci", task="1.1", duration_ms=1000, exit=1),
            row("2026-01-01T09:01:00+00:00", "ci", task="1.1", duration_ms=2000, exit=0),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["tasks"]["1.1"]["gate_ms"], 3000)
        self.assertEqual(out["tasks"]["1.1"]["failed"], 1)


class TestUnattributedBucket(unittest.TestCase):
    """Design: rows with `task: null` are reported under an explicit
    unattributed bucket — never guessed onto a nearby task."""

    def test_untagged_rows_go_to_unattributed_not_a_task(self):
        rows = [
            row("2026-01-01T09:00:00+00:00", "ci", task=None, duration_ms=500),
            row("2026-01-01T09:05:00+00:00", "ci", task=None, duration_ms=500),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["tasks"], {})
        # interval (5m) + the last row's own duration (500ms, since it is a
        # gate row and the final row) -- see TestSlowGateNoDoubleCount.
        self.assertEqual(out["unattributed"]["active_ms"], 5 * 60 * 1000 + 500)
        self.assertEqual(out["unattributed"]["gate_ms"], 1000)


class TestRowsWithoutUsableTimestamp(unittest.TestCase):
    def test_missing_or_unparseable_ts_excluded_but_counted(self):
        rows = [
            row("2026-01-01T09:00:00+00:00", "ci", duration_ms=1000),
            row(None, "ci", duration_ms=1000),
            row("not-a-timestamp", "ci", duration_ms=1000),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["rows_without_ts"], 2)
        self.assertEqual(out["rows"], 3)
        # Only the one usable row contributes to the gate table.
        self.assertEqual(out["gates"]["ci"]["runs"], 1)


class TestReadLedgerRowsAndSkipped(unittest.TestCase):
    """Task 1.2: a row-reading path that discloses how many lines could not
    be read as a JSON object, alongside `_read_ledger_rows`'s existing
    tolerant behavior (audit/taint's callers are untouched -- this is a new
    function, not a changed signature)."""

    def test_mixed_ledger_counts_skipped_lines_without_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger_dir = root / ".gatedloop" / "runs"
            ledger_dir.mkdir(parents=True)
            (ledger_dir / "my-change.jsonl").write_text(
                '{"ts": "2026-01-01T00:00:00+00:00", "gate": "ci", "exit": 0, '
                '"duration_ms": 100, "change": "my-change", "task": null, '
                '"tree": null, "attempt": 1, "approved_by": null, "sha": null}\n'
                "not-json-at-all\n"
                "[1, 2, 3]\n"
                '{"ts": "not-a-timestamp", "gate": "ci", "exit": 0}\n'
            )
            rows, skipped = gates._read_ledger_rows_and_skipped(root, "my-change")
            # The non-JSON line and the JSON-but-not-an-object line are both
            # skipped; the row with an unusable `ts` is still a valid JSON
            # object, so it is returned as a row (stats_from_rows is what
            # excludes it, counting it as `rows_without_ts`, per D4).
            self.assertEqual(skipped, 2)
            self.assertEqual(len(rows), 2)

    def test_missing_ledger_file_returns_empty_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows, skipped = gates._read_ledger_rows_and_skipped(root, "no-such-change")
            self.assertEqual(rows, [])
            self.assertEqual(skipped, 0)

    def test_row_with_unusable_ts_flows_through_to_stats_from_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger_dir = root / ".gatedloop" / "runs"
            ledger_dir.mkdir(parents=True)
            (ledger_dir / "my-change.jsonl").write_text(
                '{"ts": "2026-01-01T00:00:00+00:00", "gate": "ci", "exit": 0, '
                '"duration_ms": 100, "change": "my-change", "task": null, '
                '"tree": null, "attempt": 1, "approved_by": null, "sha": null}\n'
                '{"ts": null, "gate": "ci", "exit": 0, "duration_ms": 100, '
                '"change": "my-change", "task": null, "tree": null, '
                '"attempt": 1, "approved_by": null, "sha": null}\n'
            )
            rows, skipped = gates._read_ledger_rows_and_skipped(root, "my-change")
            self.assertEqual(skipped, 0)
            self.assertEqual(len(rows), 2)
            out = gates.stats_from_rows(rows, IDLE_GAP_MS)
            self.assertEqual(out["rows_without_ts"], 1)
            self.assertEqual(out["rows"], 2)


class TestEraTolerance(unittest.TestCase):
    """Task 1.3 / design D4: rows carrying fields this code doesn't know
    (`scope`, from `scale-gate-cost`) or missing optional fields aggregate
    normally, with a degraded (never crashing) contribution for what's
    missing. One ledger can span both eras."""

    def test_unknown_scope_field_is_ignored_not_fatal(self):
        rows = [
            row("2026-01-01T09:00:00+00:00", "ci", duration_ms=1000, scope="backend"),
            row("2026-01-01T09:01:00+00:00", "ci", duration_ms=1000, scope="frontend"),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["gates"]["ci"]["runs"], 2)
        self.assertEqual(out["gates"]["ci"]["total_ms"], 2000)

    def test_null_duration_ms_degrades_to_zero_but_still_counts_a_run(self):
        rows = [row("2026-01-01T09:00:00+00:00", "ci", duration_ms=None, exit=0)]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["gates"]["ci"]["runs"], 1)
        self.assertEqual(out["gates"]["ci"]["total_ms"], 0)

    def test_null_task_goes_to_unattributed_absent_attempt_does_not_crash(self):
        r = row("2026-01-01T09:00:00+00:00", "ci", duration_ms=500, task=None)
        del r["attempt"]  # simulates a row from an era before `attempt` existed
        out = gates.stats_from_rows([r], IDLE_GAP_MS)
        self.assertEqual(out["tasks"], {})
        self.assertEqual(out["unattributed"]["gate_ms"], 500)

    def test_mixed_era_ledger_aggregates_normally(self):
        """A `scope`-era row and a pre-`scope` row coexisting in one file."""
        rows = [
            row("2026-01-01T09:00:00+00:00", "ci", duration_ms=1000),
            row("2026-01-01T09:05:00+00:00", "ci", duration_ms=1000, scope="backend"),
        ]
        out = gates.stats_from_rows(rows, IDLE_GAP_MS)
        self.assertEqual(out["gates"]["ci"]["runs"], 2)
        self.assertEqual(out["rows_without_ts"], 0)


if __name__ == "__main__":
    unittest.main()
