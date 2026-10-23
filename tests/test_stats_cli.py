"""CLI-surface tests for `gates stats` (design gates-stats D2/D4, task 2.1).

Exercises `cmd_stats` end-to-end as a subprocess (matching test_ledger.py /
test_task_baseline.py) rather than in-process: scope resolution (`--change`,
branch default, `--all`), and the fail-loud paths (no ledger for the resolved
change, `--all` with no ledger files at all, and running on `main`/`master`
with no `--change`) must never produce an empty-but-green report.

Stdlib only, per `zero-dep-shim`. Run with:
    python3 -m unittest discover -s tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _init_repo(root):
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class TestFailLoudScopeResolution(unittest.TestCase):
    def test_missing_ledger_for_resolved_change_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "some-change")
            (root / "openspec" / "changes" / "some-change").mkdir(parents=True, exist_ok=True)

            result = _run_gates(root, "stats")
            self.assertEqual(result.returncode, 1)
            self.assertIn("some-change", result.stderr)
            self.assertIn("no ledger", result.stderr.lower())

    def test_all_with_no_ledger_files_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)

            result = _run_gates(root, "stats", "--all")
            self.assertEqual(result.returncode, 1)
            self.assertIn("no ledger", result.stderr.lower())

    def test_main_branch_with_no_explicit_change_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)

            result = _run_gates(root, "stats")
            self.assertEqual(result.returncode, 1)
            self.assertIn("main", result.stderr.lower())

    def test_explicit_change_with_no_ledger_fails_loud_even_on_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)

            result = _run_gates(root, "stats", "--change", "nonexistent")
            self.assertEqual(result.returncode, 1)
            self.assertIn("nonexistent", result.stderr)


class TestScopeResolutionHappyPath(unittest.TestCase):
    def test_default_scope_is_current_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)
            _run_gates(root, "run", "ci", "--task", "1.1")

            result = _run_gates(root, "stats")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("my-change", result.stdout)

    def test_explicit_change_overrides_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "some-branch")
            _run_gates(root, "run", "ci", "--change", "explicit-name")

            result = _run_gates(root, "stats", "--change", "explicit-name")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("explicit-name", result.stdout)

    def test_all_spans_every_recorded_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _run_gates(root, "run", "ci", "--change", "change-a")
            _run_gates(root, "run", "ci", "--change", "change-b")

            result = _run_gates(root, "stats", "--all")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("change-a", result.stdout)
            self.assertIn("change-b", result.stdout)


class TestHumanTableSections(unittest.TestCase):
    """Task 2.2 / design D3: the human table's *sections* are a contract
    (header, per-gate table, per-task table with an unattributed row when
    applicable, a data-quality line, a limitations sentence, and a closing
    pointer to the playbook) -- exact column cosmetics are not."""

    def test_all_required_sections_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)
            _run_gates(root, "task", "start", "1.1")
            _run_gates(root, "run", "ci", "--task", "1.1")

            result = _run_gates(root, "stats")
            self.assertEqual(result.returncode, 0, result.stderr)
            out = result.stdout
            self.assertIn("my-change", out)
            self.assertIn("active", out.lower())
            self.assertIn("idle", out.lower())
            self.assertIn("ci", out)
            self.assertIn("1.1", out)
            self.assertIn("data quality", out.lower())
            self.assertIn("limitations", out.lower())
            self.assertIn("docs/gate-economics.md", out)

    def test_unattributed_row_appears_when_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)
            _run_gates(root, "run", "ci")  # no --task -> unattributed bucket

            result = _run_gates(root, "stats")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("unattributed", result.stdout.lower())

    def test_idle_gap_flag_is_disclosed_in_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)
            _run_gates(root, "run", "ci")

            result = _run_gates(root, "stats", "--idle-gap", "5")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("5", result.stdout)


class TestJsonMode(unittest.TestCase):
    """Task 2.3 / design D3: `--json` emits exactly one JSON document in the
    documented shape, and it is deterministic -- the same ledger content and
    flags produce byte-identical output."""

    def _seeded_repo(self, root):
        _init_repo(root)
        _git(root, "checkout", "-b", "my-change")
        (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)
        _run_gates(root, "task", "start", "1.1")
        _run_gates(root, "run", "ci", "--task", "1.1")

    def test_json_is_exactly_one_document_with_documented_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seeded_repo(root)

            result = _run_gates(root, "stats", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = json.loads(result.stdout)  # raises if more than one document

            self.assertIn("idle_gap_ms", doc)
            self.assertIsInstance(doc["idle_gap_ms"], int)
            self.assertIn("changes", doc)
            self.assertEqual(len(doc["changes"]), 1)
            change = doc["changes"][0]
            for key in (
                "change", "rows", "skipped_lines", "rows_without_ts",
                "active_ms", "gates", "tasks", "unattributed", "events",
            ):
                self.assertIn(key, change)
            self.assertEqual(change["change"], "my-change")
            self.assertIn("ci", change["gates"])
            for key in ("runs", "failed", "total_ms", "share"):
                self.assertIn(key, change["gates"]["ci"])
            self.assertIn("totals", doc)
            for key in ("active_ms", "gate_ms", "failed"):
                self.assertIn(key, doc["totals"])

    def test_json_output_is_deterministic_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seeded_repo(root)

            first = _run_gates(root, "stats", "--json").stdout
            second = _run_gates(root, "stats", "--json").stdout
            self.assertEqual(first, second)

    def test_all_json_mode_carries_every_change_uniform_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _run_gates(root, "run", "ci", "--change", "change-a")
            _run_gates(root, "run", "ci", "--change", "change-b")

            result = _run_gates(root, "stats", "--all", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            doc = json.loads(result.stdout)
            names = {c["change"] for c in doc["changes"]}
            self.assertEqual(names, {"change-a", "change-b"})


# ---------- `gates stats --outcomes` (escalation-outcomes D7, task 6.3) ------

def _orow(ts, gate, change, **extra):
    r = {
        "ts": ts, "gate": gate, "exit": 0, "duration_ms": 0, "change": change,
        "task": None, "tree": None, "attempt": 1, "approved_by": None,
        "sha": None, "session": "agent",
    }
    r.update(extra)
    return r


def _write_ledger(root, change, rows):
    runs = root / ".gatedloop" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{change}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )


def _seed_outcomes(root):
    _init_repo(root)
    _write_ledger(root, "clean-one", [
        _orow("2026-08-01T00:00:00+00:00", "task-start", "clean-one", task="1.1"),
        _orow("2026-08-01T00:01:00+00:00", "ci", "clean-one"),
        _orow("2026-08-01T00:02:00+00:00", "merge", "clean-one", sha="a"),
    ])
    _write_ledger(root, "asked-one", [
        _orow("2026-08-02T00:00:00+00:00", "task-start", "asked-one", task="1.1"),
        _orow("2026-08-02T00:01:00+00:00", "intervention", "asked-one", cause="ask",
              detail="which port?"),
        _orow("2026-08-02T00:02:00+00:00", "merge", "asked-one", sha="b"),
    ])
    _write_ledger(root, "stuck-one", [
        _orow("2026-09-01T00:00:00+00:00", "task-start", "stuck-one", task="2.1"),
        _orow("2026-09-01T00:01:00+00:00", "halt", "stuck-one", task="2.1",
              cause="stalled", exit=None),
    ])


class TestOutcomesCli(unittest.TestCase):
    def test_single_change_prints_terminal_verdict_and_breakdowns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            r = _run_gates(root, "stats", "--outcomes", "--change", "asked-one")
            self.assertEqual(r.returncode, 0, r.stderr)
            out = r.stdout
            self.assertIn("asked-one", out)
            self.assertIn("merged", out)
            self.assertIn("assisted", out)
            self.assertIn("ask: 1", out)
            self.assertIn("stalled: 0", out, "every cause listed, zeros included")

    def test_single_hands_off_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            r = _run_gates(root, "stats", "--outcomes", "--change", "clean-one")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("hands-off", r.stdout)
            self.assertNotIn("assisted", r.stdout)

    def test_halted_change_names_its_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            r = _run_gates(root, "stats", "--outcomes", "--change", "stuck-one")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("halted", r.stdout)
            self.assertIn("stalled: 1", r.stdout)

    def test_all_prints_the_north_star_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            r = _run_gates(root, "stats", "--outcomes", "--all")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("1 of 2 merged changes", r.stdout)
            self.assertIn("2026-08", r.stdout)
            self.assertIn("2026-09", r.stdout)

    def test_all_with_nothing_merged_is_not_computable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write_ledger(root, "stuck-one", [
                _orow("2026-09-01T00:00:00+00:00", "halt", "stuck-one", cause="stalled"),
            ])
            r = _run_gates(root, "stats", "--outcomes", "--all")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("not computable", r.stdout)
            self.assertNotIn("0 of 0", r.stdout)

    def test_human_report_ends_with_the_three_blind_spots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            r = _run_gates(root, "stats", "--outcomes", "--all")
            tail = r.stdout.strip().splitlines()[-1]
            self.assertIn("never recorded", tail)
            self.assertIn("question tool", tail)
            self.assertIn("after the last audit", tail)

    def test_pre_era_rows_are_disclosed_in_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            row = _orow("2026-09-01T00:00:00+00:00", "ci", "old-one")
            del row["session"]
            _write_ledger(root, "old-one", [row])
            r = _run_gates(root, "stats", "--outcomes", "--change", "old-one")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("1 row(s) without a session value", r.stdout)
            self.assertIn("human-commit classification unavailable", r.stdout)

    def test_json_is_one_document_with_the_documented_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            with (root / ".gatedloop" / "runs" / "stuck-one.jsonl").open("a") as f:
                f.write("not json\n")
            r = _run_gates(root, "stats", "--outcomes", "--all", "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(r.stdout)  # exactly one document, nothing interleaved
            self.assertEqual(set(doc), {"changes", "aggregate", "data_quality"})
            for c in doc["changes"]:
                for key in ("change", "terminal", "hands_off", "halts",
                            "interventions", "taints", "first_ts"):
                    self.assertIn(key, c)
            for key in ("by_terminal", "hands_off_share", "halts_by_cause",
                        "interventions_by_kind", "taints", "trend"):
                self.assertIn(key, doc["aggregate"])
            self.assertEqual(set(doc["aggregate"]["hands_off_share"]),
                             {"numerator", "denominator", "value"})
            for key in ("unparseable_lines", "rows_without_ts", "malformed_halts",
                        "rows_without_session", "unclassified_commits"):
                self.assertIn(key, doc["data_quality"])
            self.assertEqual(doc["data_quality"]["unparseable_lines"], 1)
            self.assertEqual([c["change"] for c in doc["changes"]],
                             ["asked-one", "clean-one", "stuck-one"])

    def test_json_is_byte_identical_across_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            a = _run_gates(root, "stats", "--outcomes", "--all", "--json").stdout
            b = _run_gates(root, "stats", "--outcomes", "--all", "--json").stdout
            self.assertEqual(a, b)

    def test_missing_ledger_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            r = _run_gates(root, "stats", "--outcomes", "--change", "nope")
            self.assertEqual(r.returncode, 1)
            self.assertIn("no ledger", r.stderr.lower())
            r = _run_gates(root, "stats", "--outcomes", "--all")
            self.assertEqual(r.returncode, 1)

    def test_undeclared_policy_states_the_metric_ends_at_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            r = _run_gates(root, "stats", "--outcomes", "--all")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("metric ends at merged — no acceptance policy declared", r.stdout)

    def test_declared_policy_terminates_at_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(
                MANIFEST + "approval:\n  plan: self\n  acceptance: self\n"
            )
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            _write_ledger(root, "shipped", [
                _orow("2026-08-01T00:00:00+00:00", "task-start", "shipped", task="1.1"),
                _orow("2026-08-01T00:01:00+00:00", "acceptance", "shipped", exit=None,
                      verdict="accept", tree="T1", accepted_by="po"),
                _orow("2026-08-01T00:02:00+00:00", "merge", "shipped", sha="a", tree="T1"),
            ])
            r = _run_gates(root, "stats", "--outcomes", "--all")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("terminal: accepted", r.stdout)
            self.assertIn("hands-off", r.stdout)
            self.assertNotIn("metric ends at merged", r.stdout)

    def test_authorship_and_defects_in_json_and_table(self):
        """split-test-author D11: both fields reach both outputs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _write_ledger(root, "authored", [
                _orow("2026-08-01T00:00:00+00:00", "tests-handoff", "authored",
                      author="inline", exit=0),
                _orow("2026-08-01T00:01:00+00:00", "test-defect", "authored",
                      task="1.1", detail="x", exit=None),
            ])
            doc = json.loads(_run_gates(root, "stats", "--outcomes", "--all", "--json").stdout)
            (c,) = doc["changes"]
            self.assertEqual((c["authorship"], c["test_defects"]), ("inline", 1))
            table = _run_gates(root, "stats", "--outcomes", "--all").stdout
            self.assertRegex(table, r"authorship:\s+inline")
            self.assertRegex(table, r"test defects:\s+1")

    def test_plain_stats_is_unchanged_by_the_new_rows(self):
        """Without `--outcomes` the document keeps its exact shape: the new
        event rows only ever appear as event counts, as every event did."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _seed_outcomes(root)
            r = _run_gates(root, "stats", "--all", "--json")
            doc = json.loads(r.stdout)
            self.assertEqual(set(doc), {"idle_gap_ms", "changes", "totals"})


if __name__ == "__main__":
    unittest.main()
