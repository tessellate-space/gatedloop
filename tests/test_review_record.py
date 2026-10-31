"""Convention-review recording tests (baseline finding 0.3).

The 2026-08-17 unattended run claimed every commit was "convention-clean"
and left **no artifact** backing that claim, so it could be neither
confirmed nor refuted. The remedy has to live where gate satisfaction is
already recorded (design D7/D8: the ledger row and the marker are written
at the same moment by the shim, and nowhere else in the system can see
every outcome), not in a new mechanism.

What is asserted here is *falsifiability*, not a verdict oracle: the review
itself stays an LLM judgement, but a recorded review is pinned to the exact
tree it judged, so a clean claim covering a tree nobody reviewed is now
detectable after the fact.

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
    "v",
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
    """A throwaway repo with a manifest committed on `main`, optionally with
    a change branch checked out."""
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    if branch:
        _git(root, "checkout", "-b", branch)
        (root / "openspec" / "changes" / branch).mkdir(parents=True, exist_ok=True)
    return root


class TestReviewIsRecorded(unittest.TestCase):
    def test_clean_review_appends_a_full_shape_row(self):
        """The review lands in the SAME store as gate satisfaction, with the
        same ten-field row shape (task 1b.1: a field omitted here cannot be
        reconstructed later)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)

            result = _run_gates(root, "review", "record", "clean", "--task", "1.2")
            self.assertEqual(result.returncode, 0, result.stderr)

            rows = _read_ledger(root, "my-change")
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0].keys()), LEDGER_FIELDS)
            self.assertEqual(rows[0]["gate"], "review")
            self.assertEqual(rows[0]["exit"], 0)
            self.assertEqual(rows[0]["change"], "my-change")
            self.assertEqual(rows[0]["task"], "1.2")
            self.assertEqual(rows[0]["tree"], _index_tree(root))

    def test_findings_verdict_is_recorded_as_a_nonzero_exit(self):
        """The verdict is the exit code, exactly as for a gate — so "review
        ran and found things" is distinguishable from "review ran clean",
        rather than both collapsing into "review ran"."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)

            result = _run_gates(root, "review", "record", "findings", "--task", "1.2")
            self.assertEqual(result.returncode, 0, result.stderr)

            rows = _read_ledger(root, "my-change")
            self.assertEqual(rows[0]["gate"], "review")
            self.assertEqual(rows[0]["exit"], 1)

    def test_row_is_keyed_on_change_and_task_not_a_sha(self):
        """Design D8: (change, task), never a commit SHA a squash orphans."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, branch="add-feature")

            _run_gates(root, "review", "record", "clean", "--task", "3.1", "--attempt", "2")
            row = _read_ledger(root, "add-feature")[0]
            self.assertEqual(row["change"], "add-feature")
            self.assertEqual(row["task"], "3.1")
            self.assertEqual(row["attempt"], 2)
            self.assertIsNone(row["sha"])


class TestReviewIsPinnedToTheTreeItJudged(unittest.TestCase):
    """A recorded review is only evidence about the tree it saw. The marker
    machinery already provides exactly that property for `ci` (design D1/D2:
    tree-hash based, so it cannot survive an edit); a clean review reuses it
    rather than inventing a second staleness rule."""

    def test_clean_review_marker_matches_the_reviewed_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            (root / "a.txt").write_text("a\n")
            _git(root, "add", "-A")

            self.assertEqual(_run_gates(root, "review", "record", "clean").returncode, 0)
            tree = _index_tree(root)

            check = _run_gates(root, "gate-marker", "check", "review", tree)
            self.assertEqual(check.returncode, 0, check.stderr)
            # Tree-keyed layout (design D2, worktree-native-loop): one file
            # per recorded tree under the gate's own directory.
            self.assertTrue(any((root / ".git" / "gatedloop" / "markers" / "review").glob("*.json")))

    def test_marker_does_not_survive_a_later_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _run_gates(root, "review", "record", "clean")

            (root / "b.txt").write_text("b\n")
            _git(root, "add", "-A")

            check = _run_gates(root, "gate-marker", "check", "review", _index_tree(root))
            self.assertNotEqual(check.returncode, 0)
            self.assertIn("stale", check.stderr)

    def test_findings_verdict_writes_no_marker(self):
        """An unclean review must never leave behind something readable as a
        satisfied review."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)

            _run_gates(root, "review", "record", "findings")
            review_dir = root / ".git" / "gatedloop" / "markers" / "review"
            self.assertFalse(any(review_dir.glob("*.json")) if review_dir.exists() else False)
            check = _run_gates(root, "gate-marker", "check", "review", _index_tree(root))
            self.assertNotEqual(check.returncode, 0)


class TestReviewRecordFailsLoud(unittest.TestCase):
    """`fail-loud-gates`: a review that cannot be recorded must say so and
    exit non-zero. Silently accepting it is precisely the unrecorded,
    unfalsifiable claim finding 0.3 is about."""

    def test_no_change_to_key_the_row_on_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, branch=None)  # still on main

            result = _run_gates(root, "review", "record", "clean")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("change", result.stderr.lower())
            self.assertFalse((root / ".gatedloop").exists())

    def test_an_unknown_verdict_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)

            result = _run_gates(root, "review", "record", "probably-fine")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(_read_ledger(root, "my-change"), [])


class TestAuthoredSetReviewIsDistinguishable(unittest.TestCase):
    """split-test-author design D7: the review over a change's authored tests
    is recorded with `--scope authored`. Regression guarded: that verdict
    being indistinguishable from a per-task review in the ledger."""

    def test_authored_scope_is_recorded_on_the_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            self.assertEqual(_run_gates(root, "review", "record", "findings",
                                        "--scope", "authored").returncode, 0)
            self.assertEqual(_run_gates(root, "review", "record", "clean",
                                        "--task", "1.1").returncode, 0)
            rows = _read_ledger(root, "my-change")
            self.assertEqual([(r["scope"], r["exit"]) for r in rows],
                             [("authored", 1), (None, 0)])

    def test_an_unknown_scope_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            result = _run_gates(root, "review", "record", "clean", "--scope", "everything")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(_read_ledger(root, "my-change"), [])


if __name__ == "__main__":
    unittest.main()
