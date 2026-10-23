"""Approval keys are read in either spelling (openspec change
`openspec-1-14-compat`, design D2; loop-enforcement delta "gatedloop's change
metadata uses OpenSpec's tool-metadata prefix").

OpenSpec 1.14 fails `validate --strict` on unknown `.openspec.yaml` keys
except lowercase `x-…` ones, so 0.5.1 writes `x-gatedloop-approved-*`. Every
reader goes through one helper, `_approval_meta`, which prefers the new key
and falls back to the 0.5.0 spelling field by field — so a plan merged under
0.5.0 still opens the implementation gate.

Stdlib only, per `zero-dep-shim`. Every repository is a throwaway one.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_approval_meta", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

MANIFEST_SELF = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=_env())


def _run_gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def _repo(root: Path, change: str = "my-change") -> Path:
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST_SELF)
    change_dir = root / "openspec" / "changes" / change
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("plan\n")
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    return change_dir


def _sha(root: Path, change: str = "my-change") -> str:
    r = _run_gates(root, "approval", "sha", change)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


OLD = "approved_by: Old <o@example.com>\napproved_at: 2026-08-19T09:30:00+00:00\napproved_sha: {sha}\n"
NEW = ("x-gatedloop-approved-by: New <n@example.com>\n"
       "x-gatedloop-approved-at: 2026-10-20T09:30:00+00:00\nx-gatedloop-approved-sha: {sha}\n")


class TestApprovalMeta(unittest.TestCase):
    """The pure helper every reader goes through: new spelling first, the
    0.5.0 spelling as a field-by-field fallback."""

    def test_old_only(self):
        by, at, sha = gates._approval_meta(
            {"approved_by": "Old", "approved_at": "then", "approved_sha": "abc"})
        self.assertEqual((by, at, sha), ("Old", "then", "abc"))

    def test_new_only(self):
        by, at, sha = gates._approval_meta({
            "x-gatedloop-approved-by": "New", "x-gatedloop-approved-at": "now",
            "x-gatedloop-approved-sha": "def"})
        self.assertEqual((by, at, sha), ("New", "now", "def"))

    def test_both_new_wins(self):
        by, at, sha = gates._approval_meta({
            "approved_by": "Old", "approved_at": "then", "approved_sha": "abc",
            "x-gatedloop-approved-by": "New", "x-gatedloop-approved-at": "now",
            "x-gatedloop-approved-sha": "def"})
        self.assertEqual((by, at, sha), ("New", "now", "def"))

    def test_fallback_is_field_by_field(self):
        by, at, sha = gates._approval_meta(
            {"x-gatedloop-approved-by": "New", "approved_sha": "abc"})
        self.assertEqual((by, at, sha), ("New", None, "abc"))

    def test_neither(self):
        self.assertEqual(gates._approval_meta({"schema": "spec-driven"}), (None, None, None))


class TestReadApprovedBy(unittest.TestCase):
    """The working-tree read (it stamps every ledger row's `approved_by`)."""

    def _read(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "openspec" / "changes" / "c"
            d.mkdir(parents=True)
            (d / ".openspec.yaml").write_text("schema: spec-driven\n" + text)
            return gates._read_approved_by(root, "c")

    def test_old_only(self):
        self.assertEqual(self._read("approved_by: Old\n"), "Old")

    def test_new_only(self):
        self.assertEqual(self._read("x-gatedloop-approved-by: New\n"), "New")

    def test_both_new_wins(self):
        self.assertEqual(self._read("approved_by: Old\nx-gatedloop-approved-by: New\n"), "New")


class TestCheckImplementReadsEitherSpelling(unittest.TestCase):
    """Scenario "An approval written by 0.5.0": the D10 gate reads the merged
    `.openspec.yaml` with `git show` from the target and accepts either
    spelling, preferring the new one."""

    def _merged(self, keys: str):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        change_dir = _repo(root)
        sha = _sha(root)
        (change_dir / ".openspec.yaml").write_text(
            "schema: spec-driven\ncreated: 2026-08-19\n" + keys.replace("{sha}", sha))
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "plan, merged and approved")
        return root

    def test_a_merged_0_5_0_approval_still_opens_the_gate(self):
        root = self._merged(OLD)
        r = _run_gates(root, "discipline", "check-implement", "my-change")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Old <o@example.com>", r.stdout)

    def test_a_merged_new_spelling_approval_opens_the_gate(self):
        root = self._merged(NEW)
        r = _run_gates(root, "discipline", "check-implement", "my-change")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("New <n@example.com>", r.stdout)

    def test_both_spellings_the_new_one_is_checked(self):
        # The old sha is stale and the new one matches: the gate must judge
        # the new key, so it passes and names the new approver.
        root = self._merged(OLD.replace("{sha}", "0" * 64) + NEW)
        r = _run_gates(root, "discipline", "check-implement", "my-change")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("New <n@example.com>", r.stdout)

    def test_both_spellings_a_stale_new_sha_is_not_rescued_by_the_old(self):
        root = self._merged(OLD + NEW.replace("{sha}", "0" * 64))
        r = _run_gates(root, "discipline", "check-implement", "my-change")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not match", r.stderr)

    def test_approval_check_reads_the_old_spelling(self):
        root = self._merged(OLD)
        r = _run_gates(root, "approval", "check", "my-change")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_approval_check_reads_the_new_spelling(self):
        root = self._merged(NEW)
        r = _run_gates(root, "approval", "check", "my-change")
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
