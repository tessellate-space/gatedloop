"""Ledger-grade commit gate (design D5, `fix-marker-mechanics`).

With D1's ledger-blind tree normalization, a staged diff consisting solely
of `.gatedloop/runs/**` paths normalizes to the SAME tree as HEAD -- so
demanding a fresh `ci` marker over a delta the marker literally cannot see
demands proof about nothing. `discipline check-commit` gets a third rung
beside planning-grade: a non-empty, ledger-only staged diff is allowed with
an explicit printed verdict. An empty diff and any diff with even one
non-ledger path keep the unchanged, full `ci`-marker requirement.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _write_tree(root: Path) -> str:
    return subprocess.run(
        ["git", "write-tree"], cwd=root, capture_output=True, text=True,
    ).stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class TestLedgerOnlyDiffAllowed(unittest.TestCase):
    def test_ledger_only_staged_diff_allowed_with_no_ci_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)

            # A ledger row, appended by an earlier `gates run` and now staged
            # -- exactly the row a task commit stages alongside its files
            # (skills/tdd-apply/SKILL.md §5h) -- with NOTHING else staged.
            _run_gates(root, "run", "ci", "--task", "1.1")
            _git(root, "add", "-A")

            tree = _write_tree(root)
            r = _run_gates(root, "discipline", "check-commit", tree)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("ledger-grade", r.stdout + r.stderr)
            self.assertNotIn("ci' marker", r.stdout + r.stderr)

    def test_mixed_ledger_and_code_diff_still_requires_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)

            _run_gates(root, "run", "ci", "--task", "1.1")
            (root / "app.py").write_text("print('hi')\n")
            _git(root, "add", "-A")

            tree = _write_tree(root)
            r = _run_gates(root, "discipline", "check-commit", tree)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("ci' marker", r.stderr)

    def test_mixed_diff_allowed_once_ci_marker_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "my-change")
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True, exist_ok=True)

            (root / "app.py").write_text("print('hi')\n")
            _git(root, "add", "-A")
            r0 = _run_gates(root, "run", "ci", "--task", "1.1")
            self.assertEqual(r0.returncode, 0, r0.stderr)
            _git(root, "add", "-A")  # pick up the ledger row `run ci` just appended

            tree = _write_tree(root)
            r = _run_gates(root, "discipline", "check-commit", tree)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_empty_diff_still_requires_the_marker(self):
        """Zero evidence is never a free pass (unchanged from design D2):
        an empty staged diff (nothing new since the last commit, not even a
        ledger row) still falls through to the full `ci` marker
        requirement."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            tree = _write_tree(root)
            r = _run_gates(root, "discipline", "check-commit", tree)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("ci' marker", r.stderr)


if __name__ == "__main__":
    unittest.main()
