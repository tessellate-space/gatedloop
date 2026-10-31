"""Tests for `gates acceptance check <tree>` (acceptance-gate design D4):
the policy-aware, O(1)-class ledger read the merge gate calls.

Undeclared policy -> exit 0, "not required". Declared -> the LATEST
`acceptance` row (file order) whose tree equals the normalized `<tree>`
decides: `accept` exits 0, `reject` exits 1 naming the cause, no row exits 1
naming the remedy (`gates acceptance brief`, `gates acceptance attest`).

Stdlib only, per `zero-dep-shim`. Run with:
    python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _approved_plan import write_approved_plan

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

BASE = """\
gatesVersion: 1
gates:
  ci: "true"
"""
MANIFEST_SELF = BASE + "approval:\n  plan: self\n  acceptance: self\n"
MANIFEST_NONE = BASE + "approval:\n  plan: self\n"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True, env=dict(os.environ),
    )


def _make_branch_repo(root: Path, manifest: str) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    # An acceptance is refused for a plan that is not the approved one
    # (loop-hardening D2), so the plan lands on main with its approval.
    write_approved_plan(root, "my-change")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", "my-change")
    (root / "feature.txt").write_text("the increment\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "task work")


def _head_tree(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD^{tree}")


class TestNoPolicy(unittest.TestCase):
    def test_undeclared_policy_passes_stating_not_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_NONE)
            r = _run_gates(root, "acceptance", "check", _head_tree(root))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("not required", r.stdout)


class TestDeclaredPolicy(unittest.TestCase):
    def test_no_rows_denies_naming_brief_and_attest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)
            r = _run_gates(root, "acceptance", "check", _head_tree(root))
            self.assertEqual(r.returncode, 1)
            self.assertIn("gates acceptance brief", r.stderr)
            self.assertIn("gates acceptance attest", r.stderr)

    def test_accept_matches_the_head_tree_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)
            a = _run_gates(root, "acceptance", "attest", "my-change", "--local")
            self.assertEqual(a.returncode, 0, a.stderr)

            ok = _run_gates(root, "acceptance", "check", _head_tree(root))
            self.assertEqual(ok.returncode, 0, ok.stderr)

            other = _git(root, "rev-parse", "main^{tree}")
            no = _run_gates(root, "acceptance", "check", other)
            self.assertEqual(no.returncode, 1)

    def test_accepted_then_edited_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)
            self.assertEqual(
                _run_gates(root, "acceptance", "attest", "my-change", "--local").returncode, 0,
            )
            (root / "feature.txt").write_text("edited after acceptance\n")
            _git(root, "add", "feature.txt")
            _git(root, "commit", "-m", "edit")
            r = _run_gates(root, "acceptance", "check", _head_tree(root))
            self.assertEqual(r.returncode, 1)

    def test_latest_verdict_for_the_tree_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)
            tree = _head_tree(root)
            self.assertEqual(
                _run_gates(root, "acceptance", "attest", "my-change", "--local").returncode, 0,
            )
            rej = _run_gates(
                root, "acceptance", "reject", "my-change",
                "--cause", "weak-spec", "--detail", "the owner meant something else",
            )
            self.assertEqual(rej.returncode, 0, rej.stderr)

            denied = _run_gates(root, "acceptance", "check", tree)
            self.assertEqual(denied.returncode, 1)
            self.assertIn("weak-spec", denied.stderr)

            self.assertEqual(
                _run_gates(root, "acceptance", "attest", "my-change", "--local").returncode, 0,
            )
            allowed = _run_gates(root, "acceptance", "check", tree)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_committing_the_ledger_row_keeps_the_acceptance(self):
        """The row lives under `.gatedloop/runs/**`, which normalization
        strips -- committing it changes the raw head tree, not the pin."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)
            self.assertEqual(
                _run_gates(root, "acceptance", "attest", "my-change", "--local").returncode, 0,
            )
            before = _head_tree(root)
            _git(root, "add", ".gatedloop/runs/my-change.jsonl")
            _git(root, "commit", "-m", "record acceptance")
            self.assertNotEqual(_head_tree(root), before)
            r = _run_gates(root, "acceptance", "check", _head_tree(root))
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_committed_row_is_read_from_the_incoming_tree_on_main(self):
        """At squash-merge time `main` is checked out and its working tree
        holds no ledger for the change; the committed row travels inside
        the incoming tree itself, so the check reads it from there."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)
            self.assertEqual(
                _run_gates(root, "acceptance", "attest", "my-change", "--local").returncode, 0,
            )
            _git(root, "add", ".gatedloop/runs/my-change.jsonl")
            _git(root, "commit", "-m", "record acceptance")
            incoming = _head_tree(root)
            _git(root, "checkout", "main")
            self.assertFalse((root / ".gatedloop" / "runs" / "my-change.jsonl").exists())

            r = _run_gates(root, "acceptance", "check", incoming)
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
