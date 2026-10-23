"""Tests for ledger-normalized marker trees (design D1, `fix-marker-mechanics`).

A gate marker's tree hash — both the one recorded and the one compared
against — must exclude `.gatedloop/runs/**` (the durable ledger), so a gate's
own ledger row appended after the marker was written can never stale it.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

# `bin/gates` has no `.py` suffix, so it is loaded by path (matches
# test_selection.py) to call `_normalize_tree` in-process.
_loader = importlib.machinery.SourceFileLoader("gates_shim_marker_norm", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "a.txt").write_text("a\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _write_tree(root: Path) -> str:
    return _git(root, "write-tree")


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


class TestNormalizeTree(unittest.TestCase):
    def test_ledger_only_delta_normalizes_to_same_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            base_tree = _write_tree(root)

            runs_dir = root / ".gatedloop" / "runs"
            runs_dir.mkdir(parents=True)
            (runs_dir / "my-change.jsonl").write_text('{"gate":"ci"}\n')
            _git(root, "add", "-A")
            ledger_tree = _write_tree(root)

            self.assertNotEqual(base_tree, ledger_tree, "sanity: trees do differ raw")
            self.assertEqual(
                gates._normalize_tree(root, base_tree),
                gates._normalize_tree(root, ledger_tree),
            )

    def test_non_ledger_delta_still_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            base_tree = _write_tree(root)

            (root / "b.txt").write_text("b\n")
            _git(root, "add", "-A")
            other_tree = _write_tree(root)

            self.assertNotEqual(
                gates._normalize_tree(root, base_tree),
                gates._normalize_tree(root, other_tree),
            )

    def test_plumbing_failure_returns_input_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            bogus = "0" * 40
            self.assertEqual(gates._normalize_tree(root, bogus), bogus)


class TestMarkerWriteCheckAreNormalized(unittest.TestCase):
    """Wiring (task 1.2): `_write_marker` records a normalized tree and
    `_check_marker_and_report` normalizes the tree it compares against, so a
    staged ledger row can never stale the marker, but any other edit still
    does."""

    def _repo(self, tmp) -> Path:
        root = Path(tmp)
        _init_repo(root)
        (root / ".gates.yaml").write_text(MANIFEST)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "gates manifest")
        return root

    def test_staging_own_ledger_row_after_marker_write_still_checks_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            r = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)

            ledger = root / ".gatedloop" / "runs" / "my-change.jsonl"
            self.assertTrue(ledger.exists())
            _git(root, "add", "-A")  # stage the ci run's own ledger row
            tree = _write_tree(root)

            check = _run_gates(root, "gate-marker", "check", "ci", tree)
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_any_other_edit_still_checks_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._repo(tmp)
            r = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)

            (root / "c.txt").write_text("c\n")
            _git(root, "add", "-A")
            tree = _write_tree(root)

            check = _run_gates(root, "gate-marker", "check", "ci", tree)
            self.assertNotEqual(check.returncode, 0)
            self.assertIn("stale", check.stderr)


def _clean_state(root: Path):
    """`(real-index tree, working-tree dirtiness)` — used to assert a
    normalization call has no working-tree or real-index effect (design D1
    risk note: `-f` must stay scoped to the scratch index)."""
    return (_write_tree(root), _git(root, "status", "--porcelain"))


class TestCheckoutIndependence(unittest.TestCase):
    """Task 1.1 / design D3: the #21 field scenario, verbatim. A change
    branch's head tree carries a ledger entry that has since diverged on
    `main`. Normalizing that *same* `branch_tree` must yield the same hash
    whether `plan/x` or `main` is checked out at call time -- on unmodified
    `main`, the unforced `git rm --cached` is refused by git's working-tree
    safety check whenever the scratch entry differs from the current
    checkout's HEAD/working file, so the `main`-checked-out call comes back
    unstripped: checkout-dependent."""

    def _ground_truth_stripped(self, root: Path, tree: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["GIT_INDEX_FILE"] = str(Path(tmp) / "index")
            subprocess.run(
                ["git", "read-tree", tree],
                cwd=root, env=env, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "rm", "--cached", "-r", "-f", "-q", "--ignore-unmatch", ".gatedloop/runs"],
                cwd=root, env=env, check=True, capture_output=True, text=True,
            )
            out = subprocess.run(
                ["git", "write-tree"], cwd=root, env=env, check=True, capture_output=True, text=True,
            )
            return out.stdout.strip()

    def test_same_tree_normalizes_identically_from_any_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)

            runs_dir = root / ".gatedloop" / "runs"
            runs_dir.mkdir(parents=True)
            (runs_dir / "other-change.jsonl").write_text('{"row": 1}\n')
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "ledger row 1")

            _git(root, "checkout", "-b", "plan/x")
            (root / "b.txt").write_text("b\n")
            (runs_dir / "other-change.jsonl").write_text('{"row": 1}\n{"row": 2}\n')
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "plan/x adds b.txt and its own ledger row")
            branch_tree = _git(root, "rev-parse", "HEAD^{tree}")

            before_branch = _clean_state(root)
            from_branch = gates._normalize_tree(root, branch_tree)
            after_branch = _clean_state(root)
            self.assertEqual(
                before_branch, after_branch,
                "normalizing from the branch must not touch the real index or working tree",
            )

            _git(root, "checkout", "main")
            (runs_dir / "other-change.jsonl").write_text('{"row": 1}\n{"row": 99}\n')
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "ledger diverges on main")

            before_main = _clean_state(root)
            from_main = gates._normalize_tree(root, branch_tree)
            after_main = _clean_state(root)
            self.assertEqual(
                before_main, after_main,
                "normalizing from main must not touch the real index or working tree",
            )

            stripped = self._ground_truth_stripped(root, branch_tree)

            self.assertEqual(
                from_branch, stripped,
                "normalizing branch_tree with plan/x checked out must match the "
                "ground-truth forced strip",
            )
            self.assertEqual(
                from_main, stripped,
                "normalizing branch_tree with main checked out (after main's own "
                "ledger diverged) must still match the ground-truth forced strip "
                "-- the normalization must not depend on the current checkout",
            )
            self.assertEqual(
                from_branch, from_main,
                "the same tree must normalize to the same hash regardless of "
                "which branch is checked out -- checkout dependence",
            )


class TestStripFailureReported(unittest.TestCase):
    """Task 1.2 / design D2: a failed strip step keeps the STRICT fail-closed
    contract (return `tree` unchanged) but stops being silent -- one stderr
    line names the step and quotes git."""

    def test_strip_failure_is_reported_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            tree = _write_tree(root)

            real_run = subprocess.run

            def fake_run(cmd, *args, **kwargs):
                if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "rm":
                    return subprocess.CompletedProcess(
                        cmd, 1, stdout="",
                        stderr="fatal: staged content differs from both the file and the HEAD\n",
                    )
                return real_run(cmd, *args, **kwargs)

            stderr_buf = io.StringIO()
            with mock.patch.object(gates.subprocess, "run", side_effect=fake_run), \
                    contextlib.redirect_stderr(stderr_buf):
                result = gates._normalize_tree(root, tree)

            self.assertEqual(
                result, tree,
                "STRICT contract: a strip failure returns the input tree unchanged",
            )
            self.assertIn(
                "ledger normalization failed", stderr_buf.getvalue(),
                "a strip failure must be reported on stderr, not swallowed silently",
            )


class TestIssue28Regression(unittest.TestCase):
    """Task 1.3: reproduces issue #10's exact sequence -- green `ci`, then
    stage the task's files + `tasks.md` flip + the run's own ledger row all
    together, then check the marker one last time before commit."""

    def test_green_ci_then_stage_task_files_and_own_ledger_row_still_checks_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".gates.yaml").write_text(MANIFEST)
            (root / "openspec" / "changes" / "my-change").mkdir(parents=True)
            tasks_path = root / "openspec" / "changes" / "my-change" / "tasks.md"
            tasks_path.write_text("- [ ] 1.1 do the thing\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "scaffold")
            _git(root, "checkout", "-b", "my-change")

            # The task's own implementation file, staged before `gates run ci`.
            (root / "impl.txt").write_text("implementation\n")
            _git(root, "add", "impl.txt")

            r = _run_gates(root, "run", "ci", "--change", "my-change", "--task", "1.1")
            self.assertEqual(r.returncode, 0, r.stderr)

            # Flip the task's checkbox and stage it alongside the run's own
            # ledger row -- issue #10's exact sequence.
            tasks_path.write_text("- [x] 1.1 do the thing\n")
            _git(root, "add", "-A")
            tree = _write_tree(root)

            check = _run_gates(root, "gate-marker", "check", "ci", tree)
            self.assertNotEqual(
                check.returncode, 0,
                "sanity: the tasks.md flip is a real edit outside .gatedloop/runs/** "
                "and must still stale the marker recorded before it",
            )

            # Re-running `ci` over the now-fully-staged tree (task files +
            # flip + the first run's ledger row) records a fresh marker; then
            # staging that second run's own ledger row must still check fresh.
            r2 = _run_gates(root, "run", "ci", "--change", "my-change", "--task", "1.1")
            self.assertEqual(r2.returncode, 0, r2.stderr)
            _git(root, "add", "-A")
            final_tree = _write_tree(root)
            final_check = _run_gates(root, "gate-marker", "check", "ci", final_tree)
            self.assertEqual(final_check.returncode, 0, final_check.stderr)


if __name__ == "__main__":
    unittest.main()
