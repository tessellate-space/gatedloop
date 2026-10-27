"""Per-task tree baseline tests (baseline finding 0.4).

The most serious finding of the 2026-08-17 unattended run: it reported that
"a background watcher/orchestrator in this environment is actively editing
files" and disowned three uncommitted changes. No such watcher existed — the
edits were its own, and they were correct. An agent that cannot tell its own
writes from another party's will also mis-reason about what is safe to
commit, revert, or overwrite.

The remedy the finding asks for is to record the tree hash at task start, so
"did I change this file?" is answerable from **data** rather than memory. It
lands on the existing ledger row (design D7/D8: one durable store, keyed on
`(change, task)`, written only by the shim) as a `task-start` event, and
`gates task changed` reads that baseline back.

Two properties are load-bearing here and are asserted explicitly:

- **Untracked files count.** The disowned edits were uncommitted; a bare
  `git diff <tree>` never mentions an untracked file, so an answer built on
  it would have confirmed the agent's wrong conclusion.
- **No baseline is not "nothing changed."** With no `task-start` row the
  question is unanswerable, and saying so loudly is the whole point —
  silently printing an empty answer would recreate the finding.

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
    "cause", "detail", "session", "accepted_by",
    # split-test-author design D4: authoring rows only; `None` elsewhere.
    "author", "tests", "base", "no_behaviour", "note", "restart_available",
    # authored-test-kinds design D1/D3: authoring and defect rows only.
    "characterization", "kind",
    # token-ledger design D1: usage rows only.
    "tokens", "window", "messages", "source",
}


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    )


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


def _index_tree(root):
    return _git(root, "write-tree").stdout.strip()


def _repo(tmp, *, branch="my-change"):
    """A throwaway repo with one committed file on `main`, optionally with a
    change branch checked out."""
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    (root / "tracked.txt").write_text("original\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    if branch:
        _git(root, "checkout", "-b", branch)
        (root / "openspec" / "changes" / branch).mkdir(parents=True, exist_ok=True)
    return root


class TestTaskStartIsRecorded(unittest.TestCase):
    def test_start_appends_a_full_shape_row_naming_the_tree(self):
        """Same store, same ten-field shape as every other row (task 1b.1) —
        the baseline is a ledger event, not a new mechanism."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)

            result = _run_gates(root, "task", "start", "0.4")
            self.assertEqual(result.returncode, 0, result.stderr)

            rows = _read_ledger(root, "my-change")
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0].keys()), LEDGER_FIELDS)
            self.assertEqual(rows[0]["gate"], "task-start")
            self.assertEqual(rows[0]["exit"], 0)
            self.assertEqual(rows[0]["change"], "my-change")
            self.assertEqual(rows[0]["task"], "0.4")
            self.assertEqual(rows[0]["tree"], _index_tree(root))
            self.assertIsNone(rows[0]["sha"])

    def test_start_is_keyed_on_change_and_task(self):
        """Design D8: (change, task), never a SHA a squash orphans."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, branch="add-feature")

            _run_gates(root, "task", "start", "3.1", "--attempt", "2")
            row = _read_ledger(root, "add-feature")[0]
            self.assertEqual(row["change"], "add-feature")
            self.assertEqual(row["task"], "3.1")
            self.assertEqual(row["attempt"], 2)

    def test_start_refuses_when_no_change_can_be_keyed_on(self):
        """`fail-loud-gates`: a baseline that cannot be keyed is refused, not
        written under a guessed key."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, branch=None)  # still on main

            result = _run_gates(root, "task", "start", "0.4")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("change", result.stderr.lower())
            self.assertFalse((root / ".gatedloop").exists())


class TestChangedSinceTaskStart(unittest.TestCase):
    def test_nothing_changed_prints_nothing_and_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "0.4")

            result = _run_gates(root, "task", "changed")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    def test_a_modified_tracked_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "0.4")

            (root / "tracked.txt").write_text("edited\n")

            result = _run_gates(root, "task", "changed")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("tracked.txt", result.stdout)

    def test_a_new_untracked_file_is_reported(self):
        """The finding's actual shape: the disowned edits were uncommitted.
        `git diff <tree>` alone never names an untracked file, so an answer
        built only on it would have agreed with the wrong conclusion."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "0.4")

            (root / "brand-new.txt").write_text("mine\n")

            result = _run_gates(root, "task", "changed")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("brand-new.txt", result.stdout)

    def test_a_staged_change_is_reported(self):
        """Staging is not a way to lose provenance."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "0.4")

            (root / "staged.txt").write_text("mine\n")
            _git(root, "add", "-A")

            result = _run_gates(root, "task", "changed")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("staged.txt", result.stdout)

    def test_no_baseline_is_refused_not_answered_empty(self):
        """`fail-loud-gates`, and the finding itself: "I have no record" must
        never render as "nothing changed"."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            (root / "tracked.txt").write_text("edited\n")

            result = _run_gates(root, "task", "changed")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("task start", result.stderr)

    def test_the_latest_baseline_for_the_task_wins(self):
        """A task restarted after a commit must be measured from the restart,
        not from the first attempt."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "0.4")

            (root / "tracked.txt").write_text("edited\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 0.4 first attempt")

            _run_gates(root, "task", "start", "0.4", "--attempt", "2")

            result = _run_gates(root, "task", "changed")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "")

    def test_an_explicit_task_selects_that_tasks_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "1.1")

            (root / "from-1-1.txt").write_text("x\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 1.1")

            _run_gates(root, "task", "start", "1.2")

            # Measured from 1.2 nothing has changed; measured from 1.1 the
            # committed file has.
            self.assertEqual(_run_gates(root, "task", "changed").stdout.strip(), "")
            older = _run_gates(root, "task", "changed", "--task", "1.1")
            self.assertEqual(older.returncode, 0, older.stderr)
            self.assertIn("from-1-1.txt", older.stdout)

    def test_an_unknown_task_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "task", "start", "0.4")

            result = _run_gates(root, "task", "changed", "--task", "9.9")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("9.9", result.stderr)


if __name__ == "__main__":
    unittest.main()
