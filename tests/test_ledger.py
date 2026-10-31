"""Ledger tests for the `gates` shim (design D7/D8, tasks 1b.1-1b.6).

Stdlib only, per `zero-dep-shim`. Builds throwaway git repos under a temp
directory, exercises `gates run` / `gates ledger record-merge` as
subprocesses (black-box, matching how the loop actually calls them), and
checks the durable `.gatedloop/runs/<change>.jsonl` ledger — deliberately
distinct from the ephemeral `.git/gatedloop/markers/` marker tested in
test_markers.py.

Run with:  python3 -m unittest discover -s tests
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

LEDGER_FIELDS = {
    "ts", "gate", "exit", "duration_ms", "change", "task", "tree",
    "attempt", "approved_by", "sha",
    # fix-marker-mechanics design D7: the skip verdict on a resolved-empty
    # live-check row; `None` on every other row.
    "verdict",
    # gate-preconditions design D3: three additive fields for the
    # precondition-failure row kind; `None` on every other row.
    "outcome", "precondition", "precondition_exit",
    # scale-gate-cost design D2: "full" or a surface name on scoped ci/unit
    # rows; `None` on every other row.
    "scope",
    # escalation-outcomes design D2/D5: `cause`/`detail` on halt and
    # intervention rows (`None` elsewhere); `session` on every row, set by
    # the writer from the CLAUDECODE session marker.
    "cause", "detail", "session",
    # acceptance-gate design D2: who accepted the increment, on `acceptance`
    # rows only; `None` on every other row.
    "accepted_by",
    # split-test-author design D4: the handoff's author and blobs, on
    # authoring rows only; `None` on every other row.
    "author", "tests", "base", "no_behaviour",
    # retry-budget design D3: the four-field lesson, on `attempt-note` rows
    # only; `None` on every other row.
    "note",
    # retry-budget design D4: whether a fresh restart remains, on `stalled`
    # halt rows only; `None` on every other row.
    "restart_available",
    # authored-test-kinds design D1: the declared characterization tasks,
    # on authoring rows only; `None` on every other row.
    "characterization",
    # authored-test-kinds design D3: a test defect's kind, on
    # `test-defect` rows only; `None` on every other row.
    "kind",
    # token-ledger design D1: usage rows only.
    "tokens", "window", "messages", "source",
    "v",
}

NO_LIVE_CHECK_ANYWHERE = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _read_ledger(root, change):
    p = root / ".gatedloop" / "runs" / f"{change}.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


class TestLedgerRowShape(unittest.TestCase):
    """Task 1b.1: the row shape is fixed and every row carries every field
    (unused ones are `None`, never omitted — an omitted field can't be
    reconstructed later)."""

    def test_row_carries_every_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)

            result = _run_gates(root, "run", "ci", "--task", "1.1")
            self.assertEqual(result.returncode, 0, result.stderr)

            rows = _read_ledger(root, "my-change")
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0].keys()), LEDGER_FIELDS)
            self.assertEqual(rows[0]["gate"], "ci")
            self.assertEqual(rows[0]["exit"], 0)
            self.assertEqual(rows[0]["change"], "my-change")
            self.assertEqual(rows[0]["task"], "1.1")
            self.assertEqual(rows[0]["attempt"], 1)
            self.assertIsNotNone(rows[0]["tree"])


class TestLedgerKeyedOnChangeAndTask(unittest.TestCase):
    """Task 1b.3: rows key on (change, task), and the change defaults to the
    current branch (the workflow's own "one branch per change" invariant) —
    never on a commit SHA, which a squash-merge orphans."""

    def test_change_defaults_to_current_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            _git(root, "checkout", "-b", "add-feature")
            (root / "openspec" / "changes" / "add-feature").mkdir(parents=True, exist_ok=True)

            _run_gates(root, "run", "ci")
            rows = _read_ledger(root, "add-feature")
            self.assertEqual(rows[0]["change"], "add-feature")

    def test_no_ledger_row_on_main(self):
        """`main`/`master` is never a change; nothing to key a row on, so
        no row is written rather than one with a nonsensical change name."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")

            _run_gates(root, "run", "ci")
            self.assertFalse((root / ".gatedloop" / "runs").exists())

    def test_explicit_change_overrides_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            _git(root, "checkout", "-b", "some-branch")

            _run_gates(root, "run", "ci", "--change", "explicit-name")
            self.assertEqual(_read_ledger(root, "explicit-name")[0]["change"], "explicit-name")
            self.assertEqual(_read_ledger(root, "some-branch"), [])


class TestLedgerSurvivesSquashMerge(unittest.TestCase):
    """Task 1b.6: rows survive a squash-merge intact, and no row references
    a SHA absent from `main` after the squash (design D8's whole point —
    specloop PR 1 (the private archive) demonstrated branch commits stop being ancestors of
    `main`, but the ledger file's final state is carried by the squash
    commit regardless)."""

    def test_rows_survive_and_merge_row_sha_is_on_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)

            _run_gates(root, "run", "ci", "--task", "1.1")
            (root / "a.txt").write_text("a\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 1.1")

            _run_gates(root, "run", "ci", "--task", "1.2")
            (root / "b.txt").write_text("b\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 1.2")

            _git(root, "checkout", "main")
            _git(root, "merge", "--squash", "my-change")
            _git(root, "commit", "-m", "squash merge my-change")

            merge_result = _run_gates(root, "ledger", "record-merge", "my-change")
            self.assertEqual(merge_result.returncode, 0, merge_result.stderr)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "record merge ledger row")

            rows = _read_ledger(root, "my-change")
            self.assertEqual(len(rows), 3)
            self.assertEqual([r["gate"] for r in rows], ["ci", "ci", "merge"])
            merge_row = rows[-1]
            self.assertIsNotNone(merge_row["sha"])

            # The squash SHA the merge row names is an ancestor of (in fact
            # equal to, minus the ledger-commit-itself) main's current tip —
            # i.e. it did not dangle.
            log = subprocess.run(
                ["git", "log", "--format=%H", "main"],
                cwd=root, capture_output=True, text=True, check=True,
            ).stdout.splitlines()
            self.assertIn(merge_row["sha"], log)


class TestLedgerRowVerdictField(unittest.TestCase):
    """Task 2.4: `LEDGER_ROW_FIELDS` carries `verdict` -- `None` on every
    ordinary gate row, `"skip"` on the one a resolved-empty `live-check`
    appends (design D2/D7's union rule with `scale-gate-cost`'s `scope`:
    orthogonal keys, absent-means-default, so neither writer breaks the
    other's reader)."""

    def test_ordinary_gate_row_carries_verdict_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)

            result = _run_gates(root, "run", "ci", "--task", "1.1")
            self.assertEqual(result.returncode, 0, result.stderr)

            rows = _read_ledger(root, "my-change")
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0].keys()), LEDGER_FIELDS)
            self.assertIsNone(rows[0]["verdict"])

    def test_skip_run_appends_row_with_verdict_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(NO_LIVE_CHECK_ANYWHERE)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)

            result = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)

            rows = _read_ledger(root, "my-change")
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0].keys()), LEDGER_FIELDS)
            self.assertEqual(rows[0]["gate"], "live-check")
            self.assertEqual(rows[0]["verdict"], "skip")


def _load_shim():
    """`bin/gates` has no `.py` suffix, so it is loaded by path."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("gates_shim_ledger", str(GATES_SHIM))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class TestSessionAndEscalationFields(unittest.TestCase):
    """escalation-outcomes design D2/D5 part 1: the fixed shape ends with
    `cause`, `detail`, `session`; the one writer fills the first two as `None`
    when absent and sets `session` itself from the `CLAUDECODE` marker, so no
    row kind can omit it. `os.environ` is patched and restored — the ledger
    writer and the git-layer hook both read it."""

    @classmethod
    def setUpClass(cls):
        cls.gates = _load_shim()

    def test_fields_carry_cause_detail_session_after_scope(self):
        fields = self.gates.LEDGER_ROW_FIELDS
        i = fields.index("scope")
        self.assertEqual(fields[i:i + 4], ("scope", "cause", "detail", "session"))

    def _write_row(self, root, env_patch, clear=()):
        from unittest import mock
        with mock.patch.dict("os.environ", env_patch):
            import os
            for k in clear:
                os.environ.pop(k, None)
            self.gates._append_ledger_row(root, {
                "ts": "2026-09-01T00:00:00+00:00", "gate": "ci", "exit": 0,
                "change": "my-change", "task": "1.1",
            })
        return _read_ledger(root, "my-change")[-1]

    def test_absent_cause_and_detail_are_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self._write_row(Path(tmp), {"CLAUDECODE": "1"})
            self.assertIn("cause", row)
            self.assertIn("detail", row)
            self.assertIsNone(row["cause"])
            self.assertIsNone(row["detail"])

    def test_session_agent_when_marker_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self._write_row(Path(tmp), {"CLAUDECODE": "1"})
            self.assertEqual(row["session"], "agent")

    def test_session_human_when_marker_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = self._write_row(Path(tmp), {}, clear=("CLAUDECODE",))
            self.assertEqual(row["session"], "human")

    def test_session_is_set_by_writer_not_caller(self):
        """A caller-supplied `session` never overrides the writer's own
        decision — the field is the writer's, so no row kind can forge it."""
        from unittest import mock
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.dict("os.environ", {}):
                os.environ.pop("CLAUDECODE", None)
                self.gates._append_ledger_row(root, {
                    "ts": "2026-09-01T00:00:00+00:00", "gate": "review",
                    "exit": 0, "change": "my-change", "session": "agent",
                })
            self.assertEqual(_read_ledger(root, "my-change")[-1]["session"], "human")

    def test_environment_restored(self):
        import os
        before = os.environ.get("CLAUDECODE")
        with tempfile.TemporaryDirectory() as tmp:
            self._write_row(Path(tmp), {}, clear=("CLAUDECODE",))
        self.assertEqual(os.environ.get("CLAUDECODE"), before)


class TestMergeRowTreeIsNormalized(unittest.TestCase):
    """acceptance-gate D7: the merge row records the ledger-normalized tree,
    the same hash an acceptance row pins, so the outcomes view can join the
    two."""

    def test_merge_row_tree_is_the_normalized_head_tree(self):
        gates = _load_shim()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST)
            runs = root / ".gatedloop" / "runs"
            runs.mkdir(parents=True)
            (runs / "my-change.jsonl").write_text('{"gate": "ci"}\n')
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init with a ledger")
            r = _run_gates(root, "ledger", "record-merge", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=root,
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            merge_row = _read_ledger(root, "my-change")[-1]
            self.assertEqual(merge_row["gate"], "merge")
            self.assertEqual(merge_row["tree"], gates._normalize_tree(root, head))
            self.assertNotEqual(merge_row["tree"], head)


class TestAcceptanceRowShape(unittest.TestCase):
    """acceptance-gate design D2: the acceptance record is a ledger row. The
    fixed shape gains `accepted_by`, appended after `session` (the union
    rule), and `acceptance` is an event, never a gate outcome."""

    @classmethod
    def setUpClass(cls):
        cls.gates = _load_shim()

    def test_accepted_by_directly_follows_session(self):
        fields = self.gates.LEDGER_ROW_FIELDS
        i = fields.index("session")
        self.assertEqual(fields[i:i + 2], ("session", "accepted_by"))

    def test_acceptance_is_a_non_gate_event(self):
        self.assertIn("acceptance", self.gates.NON_GATE_EVENTS)

    def test_stats_ignore_acceptance_rows_for_gate_arithmetic(self):
        rows = [
            {"ts": "2026-09-01T00:00:00+00:00", "gate": "ci", "exit": 0,
             "duration_ms": 1000, "task": "1.1"},
            {"ts": "2026-09-01T00:01:00+00:00", "gate": "acceptance", "exit": None,
             "duration_ms": 0, "verdict": "reject", "cause": "weak-spec"},
            {"ts": "2026-09-01T00:02:00+00:00", "gate": "acceptance", "exit": None,
             "duration_ms": 0, "verdict": "accept"},
        ]
        out = self.gates.stats_from_rows(rows, 30 * 60 * 1000)
        self.assertEqual(set(out["gates"]), {"ci"})
        self.assertEqual(out["gates"]["ci"]["runs"], 1)
        self.assertEqual(out["gates"]["ci"]["failed"], 0)
        self.assertEqual(out["events"], {"acceptance": 2})

    def test_other_rows_carry_accepted_by_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.gates._append_ledger_row(root, {
                "ts": "2026-09-01T00:00:00+00:00", "gate": "ci", "exit": 0,
                "change": "my-change",
            })
            row = _read_ledger(root, "my-change")[-1]
            self.assertIn("accepted_by", row)
            self.assertIsNone(row["accepted_by"])


if __name__ == "__main__":
    unittest.main()
