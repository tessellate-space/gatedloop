"""Tests for recorded skip verdicts on `gates run live-check` (design D2,
`fix-marker-mechanics`, issues #9/#37.1/#40.2).

A resolved-empty live-check (no hot surface, hot surfaces with no
`live-check`, or no surface anywhere declaring one) must write a marker
carrying `verdict: "skip"` and the same evidence the skip message prints, plus
a ledger row recording the same verdict — so a docs-only diff (or a project
declaring no live-check at all) is not permanently unmergeable, while a
declared probe that runs red still writes nothing.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path, manifest: str) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _marker(root: Path, gate: str) -> dict | None:
    # Tree-keyed layout (design D2, worktree-native-loop): one file per
    # recorded tree under the gate's directory. These tests write exactly
    # one marker per gate, so the sole file (if any) is the one to read.
    d = root / ".git" / "gatedloop" / "markers" / gate
    files = sorted(d.glob("*.json")) if d.exists() else []
    if not files:
        return None
    return json.loads(files[-1].read_text())


NO_LIVE_CHECK_ANYWHERE = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

CODE_ONLY_SURFACE = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: code
    match: "src/**"
    live-check: "true"
"""


class TestResolvedEmptyLiveCheckRecordsSkip(unittest.TestCase):
    def test_docs_only_change_writes_skip_marker_with_printed_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_ONLY_SURFACE)

            r = _run_gates(
                root, "run", "live-check", "--changed", "README.md", "--change", "my-change",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("skipping", r.stdout + r.stderr)

            marker = _marker(root, "live-check")
            self.assertIsNotNone(marker, "expected a live-check marker to be written")
            self.assertEqual(marker.get("verdict"), "skip")
            evidence = marker.get("evidence")
            self.assertIsNotNone(evidence)
            self.assertEqual(evidence.get("baseline"), "override")
            self.assertEqual(evidence.get("files_considered"), 1)

    def test_no_live_check_declared_anywhere_writes_skip_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, NO_LIVE_CHECK_ANYWHERE)

            r = _run_gates(
                root, "run", "live-check", "--all", "--change", "my-change",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            marker = _marker(root, "live-check")
            self.assertIsNotNone(marker)
            self.assertEqual(marker.get("verdict"), "skip")

    def test_declared_probe_that_fails_still_writes_no_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: code
    match: "src/**"
    live-check: "false"
"""
            _init_repo(root, manifest)
            r = _run_gates(
                root, "run", "live-check", "--changed", "src/a.py", "--change", "my-change",
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIsNone(_marker(root, "live-check"))


class TestCheckMarkerAcceptsMatchingSkip(unittest.TestCase):
    """Task 2.2: `gate-marker check` treats a tree-matching skip marker as
    satisfied, naming the verdict and evidence; a missing marker still
    denies; a mismatched-tree skip still denies."""

    def test_tree_matching_skip_marker_satisfies_and_names_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_ONLY_SURFACE)
            r = _run_gates(
                root, "run", "live-check", "--changed", "README.md", "--change", "my-change",
            )
            self.assertEqual(r.returncode, 0, r.stderr)

            head_tree = _git(root, "rev-parse", "HEAD^{tree}")
            check = _run_gates(root, "gate-marker", "check", "live-check", head_tree)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertIn("skip", check.stdout.lower())
            self.assertIn("baseline", check.stdout.lower())

    def test_missing_marker_still_denies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_ONLY_SURFACE)
            head_tree = _git(root, "rev-parse", "HEAD^{tree}")
            check = _run_gates(root, "gate-marker", "check", "live-check", head_tree)
            self.assertNotEqual(check.returncode, 0)

    def test_mismatched_tree_skip_still_denies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_ONLY_SURFACE)
            r = _run_gates(
                root, "run", "live-check", "--changed", "README.md", "--change", "my-change",
            )
            self.assertEqual(r.returncode, 0, r.stderr)

            (root / "b.txt").write_text("b\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "a real edit after the skip marker")
            new_tree = _git(root, "rev-parse", "HEAD^{tree}")

            check = _run_gates(root, "gate-marker", "check", "live-check", new_tree)
            self.assertNotEqual(check.returncode, 0)


class TestIssue27UndeclaredGateRegression(unittest.TestCase):
    """Task 2.3: issue #9's exact shape -- a manifest declaring `live-check`
    on no surface at all must not permanently deny every merge. A declared
    probe that runs red is the opposite case and must keep writing nothing."""

    def test_undeclared_anywhere_skip_marker_round_trips_through_gate_marker_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, NO_LIVE_CHECK_ANYWHERE)

            r = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)

            head_tree = _git(root, "rev-parse", "HEAD^{tree}")
            check = _run_gates(root, "gate-marker", "check", "live-check", head_tree)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertIn("skip", check.stdout.lower())

    def test_declared_probe_ran_red_still_writes_no_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: code
    match: "src/**"
    live-check: "false"
"""
            _init_repo(root, manifest)
            r = _run_gates(
                root, "run", "live-check", "--changed", "src/a.py", "--change", "my-change",
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIsNone(_marker(root, "live-check"))

            head_tree = _git(root, "rev-parse", "HEAD^{tree}")
            check = _run_gates(root, "gate-marker", "check", "live-check", head_tree)
            self.assertNotEqual(check.returncode, 0)


if __name__ == "__main__":
    unittest.main()
