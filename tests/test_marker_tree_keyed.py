"""Tree-keyed gate markers (design D2 of `worktree-native-loop`, task 2.1).

A gate's recorded green evidence used to be a single slot (`<gate>.json`)
that each new run overwrote -- a lane alternating between trees (a
serialized merge lane: pre-merge head, post-ledger-row tree, next branch's
head) invalidated its own still-valid evidence every time it recorded a
newer one. Markers are now keyed by tree, `markers/<gate>/<tree>.json`, with
a bounded number of recent trees retained per gate (LRU, pruned oldest-first
by recorded timestamp) -- so two trees can both stay green, and only actual
eviction (past the retention bound) requires a re-run.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

_loader = importlib.machinery.SourceFileLoader("gates_shim_marker_tree_keyed", str(GATES_SHIM))
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


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _markers_gate_dir(root: Path, gate: str) -> Path:
    return root / ".git" / "gatedloop" / "markers" / gate


def _legacy_marker_path(root: Path, gate: str) -> Path:
    return root / ".git" / "gatedloop" / "markers" / f"{gate}.json"


class TestTwoTreesStayGreen(unittest.TestCase):
    def test_recording_a_second_tree_does_not_invalidate_the_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "add manifest")
            tree_a = _git(root, "write-tree")

            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)

            (root / "b.txt").write_text("b\n")
            _git(root, "add", "-A")
            tree_b = _git(root, "write-tree")
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)

            # tree_a's marker must still satisfy a check -- recording tree_b
            # must not have overwritten it.
            check_a = _run_gates(root, "gate-marker", "check", "ci", tree_a)
            self.assertEqual(check_a.returncode, 0, check_a.stderr)
            check_b = _run_gates(root, "gate-marker", "check", "ci", tree_b)
            self.assertEqual(check_b.returncode, 0, check_b.stderr)


class TestEviction(unittest.TestCase):
    def test_ninth_tree_evicts_the_oldest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "add manifest")

            trees = []
            for i in range(9):
                (root / f"f{i}.txt").write_text(f"{i}\n")
                _git(root, "add", "-A")
                tree = _git(root, "write-tree")
                trees.append(tree)
                r = _run_gates(root, "run", "ci")
                self.assertEqual(r.returncode, 0, r.stderr)

            gate_dir = _markers_gate_dir(root, "ci")
            self.assertEqual(len(list(gate_dir.glob("*.json"))), 8)

            # The oldest (first) tree was evicted -- its check now fails,
            # naming a re-run, not a hard error.
            oldest = _run_gates(root, "gate-marker", "check", "ci", trees[0])
            self.assertNotEqual(oldest.returncode, 0)
            self.assertIn("Run `gates run", oldest.stderr)

            # The most recent 8 all still check out.
            for tree in trees[1:]:
                r = _run_gates(root, "gate-marker", "check", "ci", tree)
                self.assertEqual(r.returncode, 0, r.stderr)

            # One green re-run on the evicted tree restores it -- rebuild the
            # index to exactly `trees[0]` (only f0.txt staged) rather than
            # manually reverse the loop's file writes.
            _git(root, "read-tree", trees[0])
            _git(root, "checkout-index", "-a", "-f")
            for i in range(1, 9):
                (root / f"f{i}.txt").unlink(missing_ok=True)
            restored_tree = _git(root, "write-tree")
            self.assertEqual(restored_tree, trees[0])
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = _run_gates(root, "gate-marker", "check", "ci", trees[0])
            self.assertEqual(r.returncode, 0, r.stderr)


class TestLegacySingleSlotIgnored(unittest.TestCase):
    def test_legacy_marker_file_is_ignored_by_a_fresh_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "add manifest")
            tree = _git(root, "write-tree")

            legacy = _legacy_marker_path(root, "ci")
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(json.dumps({"gate": "ci", "tree": tree, "ts": "2020-01-01T00:00:00+00:00"}))

            # The legacy single-slot file existing must NOT satisfy a check
            # under the new tree-keyed layout.
            r = _run_gates(root, "gate-marker", "check", "ci", tree)
            self.assertNotEqual(r.returncode, 0)

    def test_a_fresh_write_cleans_up_the_legacy_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "add manifest")

            legacy = _legacy_marker_path(root, "ci")
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(json.dumps({"gate": "ci", "tree": "deadbeef", "ts": "2020-01-01T00:00:00+00:00"}))
            self.assertTrue(legacy.exists())

            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(legacy.exists(), "the legacy single-slot file should be cleaned up on a fresh write")


class TestGateMarkerClearClearsBothLayouts(unittest.TestCase):
    def test_clear_removes_legacy_file_and_tree_keyed_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "add manifest")

            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            gate_dir = _markers_gate_dir(root, "ci")
            self.assertTrue(any(gate_dir.glob("*.json")))

            legacy = _legacy_marker_path(root, "ci")
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(json.dumps({"gate": "ci", "tree": "deadbeef", "ts": "2020-01-01T00:00:00+00:00"}))

            r = _run_gates(root, "gate-marker", "clear", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(legacy.exists())
            self.assertFalse(gate_dir.exists())


if __name__ == "__main__":
    unittest.main()
