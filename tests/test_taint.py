"""Tests for the taint-blocks-merge / cheap-to-clear behavior (enforce-at-the-
effect §5, design D7).

Stdlib only. Exercises the shim oracle the merge gate reads (`gates taint check`)
and the resolution path (`gates run ci` on a clean head appends a taint-clear
row), in throwaway git repos with a real ledger.

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

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _rows(root, change):
    p = root / ".gatedloop" / "runs" / f"{change}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _gates(rows):
    return [r["gate"] for r in rows]


def _tainted_repo(tmp, *, manifest=MANIFEST):
    """A change branch with one ungated commit, audited into a taint."""
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", "my-change")
    (root / "b.txt").write_text("b\n")
    _git(root, "add", "b.txt")
    _git(root, "commit", "-m", "ungated bypass")  # no `gates run ci`
    assert _run_gates(root, "audit", "--change", "my-change").returncode == 1
    return root


class TestTaintBlocksMerge(unittest.TestCase):
    def test_tainted_change_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _tainted_repo(tmp)
            r = _run_gates(root, "taint", "check", "--change", "my-change")
            self.assertEqual(r.returncode, 1, "an unresolved taint must block")
            self.assertIn("unresolved taint", r.stderr)


class TestGreenCiOnHeadClears(unittest.TestCase):
    def test_clear_appends_resolution_and_keeps_incident(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _tainted_repo(tmp)
            # Working tree is clean, so `git write-tree` == HEAD tree: a green ci
            # here is "on the branch head" and clears the taint.
            r = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)

            after = _run_gates(root, "taint", "check", "--change", "my-change")
            self.assertEqual(after.returncode, 0, "green ci on the head clears the taint")

            gates = _gates(_rows(root, "my-change"))
            self.assertIn("taint", gates, "the incident row stays in history")
            self.assertIn("taint-clear", gates, "a resolution row is appended")
            # Append-only: the incident precedes its resolution, both retained.
            self.assertLess(gates.index("taint"), gates.index("taint-clear"))

    def test_ci_not_on_head_does_not_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _tainted_repo(tmp)
            # Stage an uncommitted change so write-tree != HEAD tree: this green
            # ci is NOT on the head and must not clear the taint.
            (root / "c.txt").write_text("c\n")
            _git(root, "add", "c.txt")
            r = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            still = _run_gates(root, "taint", "check", "--change", "my-change")
            self.assertEqual(still.returncode, 1, "a non-head green ci must not clear the taint")
            self.assertNotIn("taint-clear", _gates(_rows(root, "my-change")))


class TestPreconditionFailureNeverClearsTaint(unittest.TestCase):
    """gate-preconditions design D3: a precondition-failure row's `exit` is
    the reserved 75, never 0, so it structurally can never satisfy
    `_maybe_resolve_taint`'s join on a green `ci` row -- verified here on a
    real tainted repo rather than argued from the code alone."""

    PRECONDITION_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: {run: "true", requires: "false"}\n'

    def test_ci_with_a_failing_precondition_does_not_clear_the_taint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _tainted_repo(tmp, manifest=self.PRECONDITION_MANIFEST)
            r = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(r.returncode, 75, r.stderr)

            still = _run_gates(root, "taint", "check", "--change", "my-change")
            self.assertEqual(
                still.returncode, 1,
                "a precondition-failed ci run on the head must not clear the taint",
            )
            gates = _gates(_rows(root, "my-change"))
            self.assertNotIn("taint-clear", gates)


if __name__ == "__main__":
    unittest.main()
