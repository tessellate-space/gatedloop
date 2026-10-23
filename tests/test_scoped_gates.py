"""Scoped commit oracles (`scale-gate-cost`, design D1): `surfaces[]` MAY
declare per-surface overrides for the `ci`/`unit` gates. `gates run
ci`/`unit` selects the scoped command only when the staged (`ci`) or
working-tree (`unit`) diff's hot set is exactly one NON-catch-all surface
that declares the override; every other case (no hot surface, multiple hot
surfaces, an undeclared override, an unreadable diff) falls back to the
globally declared gate -- the err-full direction pinned by design.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
MERGE_HOOK = REPO / "hooks" / "gate-merge.sh"

# Loaded by path, like test_selection.py / test_manifest.py -- `bin/gates`
# has no `.py` suffix.
_loader = importlib.machinery.SourceFileLoader("gates_shim_scoped", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path, manifest: str) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


MANIFEST_ONE_SCOPED_SURFACE = """\
gatesVersion: 1
gates:
  ci: "echo GLOBAL-CI"
  unit: "echo GLOBAL-UNIT"
surfaces:
  - name: frontend
    match: "frontend/**"
    gates:
      ci: "echo SCOPED-CI"
      unit: "echo SCOPED-UNIT"
  - name: backend
    match: "backend/**"
  - name: everything
    match: "**"
"""

MANIFEST_TWO_SCOPED_SURFACES = """\
gatesVersion: 1
gates:
  ci: "echo GLOBAL-CI"
surfaces:
  - name: frontend
    match: "frontend/**"
    gates:
      ci: "echo SCOPED-FRONTEND"
  - name: backend
    match: "backend/**"
    gates:
      ci: "echo SCOPED-BACKEND"
"""


# ---------- 1.1: the pure selection function -------------------------------
#
# `_select_scoped_gate(m, gate, changed)` is exercised directly with explicit
# changed-file lists -- deterministic and fast, independent of any real git
# diff. The "no staged diff" scenario is covered separately (end to end)
# below, since it is specifically about what `gates run ci` sees with
# nothing staged, not about the pure function's own logic.

class TestScopedGateSelection(unittest.TestCase):
    def _manifest(self, text):
        return gates._parse_yaml_text(text)

    def test_single_hot_surface_with_override_selects_scoped(self):
        m = self._manifest(MANIFEST_ONE_SCOPED_SURFACE)
        cmd, scope = gates._select_scoped_gate(m, "ci", ["frontend/app.js"])
        self.assertEqual(cmd, "echo SCOPED-CI")
        self.assertEqual(scope, "frontend")

    def test_catchall_surface_is_ignored_still_selects_scoped(self):
        # frontend/app.js is hot for BOTH "frontend" (scoped) and
        # "everything" (match: "**", a catch-all) -- the catch-all must be
        # excluded from the one-surface count, so this still scopes.
        m = self._manifest(MANIFEST_ONE_SCOPED_SURFACE)
        cmd, scope = gates._select_scoped_gate(m, "ci", ["frontend/app.js"])
        self.assertEqual(cmd, "echo SCOPED-CI")
        self.assertEqual(scope, "frontend")

    def test_two_non_catchall_hot_surfaces_falls_back_to_global(self):
        m = self._manifest(MANIFEST_TWO_SCOPED_SURFACES)
        cmd, scope = gates._select_scoped_gate(
            m, "ci", ["frontend/app.js", "backend/main.py"],
        )
        self.assertEqual(cmd, "echo GLOBAL-CI")
        self.assertEqual(scope, "full")

    def test_hot_surface_without_override_falls_back_to_global(self):
        m = self._manifest(MANIFEST_ONE_SCOPED_SURFACE)
        cmd, scope = gates._select_scoped_gate(m, "ci", ["backend/main.py"])
        self.assertEqual(cmd, "echo GLOBAL-CI")
        self.assertEqual(scope, "full")

    def test_unmatched_changed_file_falls_back_to_global(self):
        m = self._manifest(MANIFEST_ONE_SCOPED_SURFACE)
        cmd, scope = gates._select_scoped_gate(m, "ci", ["README.md"])
        # "everything" (match: "**") IS hot here, but it's a catch-all and
        # declares no override -- and it's the only non-empty hot surface --
        # so this exercises "unmatched" as "no non-catch-all hot surface".
        self.assertEqual(cmd, "echo GLOBAL-CI")
        self.assertEqual(scope, "full")

    def test_empty_changed_set_falls_back_to_global(self):
        m = self._manifest(MANIFEST_ONE_SCOPED_SURFACE)
        cmd, scope = gates._select_scoped_gate(m, "ci", [])
        self.assertEqual(cmd, "echo GLOBAL-CI")
        self.assertEqual(scope, "full")

    def test_none_changed_set_falls_back_to_global(self):
        """An unreadable diff (`_staged_diff_paths` returns `None`) must be
        indistinguishable from an empty one -- the safe, full-gate
        direction, never treated as "nothing changed, skip"."""
        m = self._manifest(MANIFEST_ONE_SCOPED_SURFACE)
        cmd, scope = gates._select_scoped_gate(m, "ci", None)
        self.assertEqual(cmd, "echo GLOBAL-CI")
        self.assertEqual(scope, "full")


# ---------- 1.2: schema validation ------------------------------------------

class TestScopedGateValidation(unittest.TestCase):
    def test_override_naming_undeclared_gate_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: frontend
    match: "frontend/**"
    gates:
      verify: "just verify-frontend"
"""
            _init_repo(root, manifest)
            r = _run_gates(root, "validate")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("verify", r.stdout + r.stderr)

    def test_unit_override_with_no_global_unit_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: frontend
    match: "frontend/**"
    gates:
      unit: "just unit-frontend"
"""
            _init_repo(root, manifest)
            r = _run_gates(root, "validate")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("unit", r.stdout + r.stderr)

    def test_valid_scoped_manifest_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)
            r = _run_gates(root, "validate")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


# ---------- 1.3: `gates run ci`/`unit` wiring end to end --------------------

class TestScopedGateRunEndToEnd(unittest.TestCase):
    def test_scoped_ci_runs_when_only_frontend_is_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)
            (root / "frontend").mkdir()
            (root / "frontend" / "app.js").write_text("x\n")
            _git(root, "add", "frontend/app.js")

            r = _run_gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stderr)
            # Quiet-on-green (design D3): the command's own output is
            # captured to the log file, not printed -- only the "why"
            # announcement (task 1.3) and the summary line appear directly.
            self.assertIn("frontend", r.stdout + r.stderr)
            self.assertNotIn("GLOBAL-CI", r.stdout + r.stderr)
            logs = list((root / ".gatedloop" / "out").glob("ci-*.log"))
            self.assertEqual(len(logs), 1)
            self.assertIn("SCOPED-CI", logs[0].read_text())

    def test_global_ci_runs_when_nothing_is_staged(self):
        """After all tasks are committed the staged diff is empty, so
        selection falls back to the full gate -- the mechanism behind
        design's "full ci is always the last word" (D2/2.2)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)

            r = _run_gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stderr)
            logs = list((root / ".gatedloop" / "out").glob("ci-*.log"))
            self.assertEqual(len(logs), 1)
            self.assertIn("GLOBAL-CI", logs[0].read_text())

    def test_scoped_unit_runs_when_working_tree_touches_one_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)
            (root / "frontend").mkdir()
            (root / "frontend" / "app.js").write_text("x\n")
            # Deliberately NOT staged -- task 5c/5e run `unit` before
            # staging, on the working tree, not the index.

            r = _run_gates(root, "run", "unit")

            self.assertEqual(r.returncode, 0, r.stderr)
            logs = list((root / ".gatedloop" / "out").glob("unit-*.log"))
            self.assertEqual(len(logs), 1)
            self.assertIn("SCOPED-UNIT", logs[0].read_text())


# ---------- 2.1/2.3: scope recorded on the marker and the ledger row -------

class TestScopeRecordedOnMarkerAndLedger(unittest.TestCase):
    def _marker(self, root: Path, gate: str) -> dict:
        # Markers are tree-keyed (`worktree-native-loop` D2): one file per
        # recorded tree under the gate's own directory. A single `gates run`
        # in a fresh repo leaves exactly one.
        files = list((root / ".git" / "gatedloop" / "markers" / gate).glob("*.json"))
        self.assertEqual(len(files), 1, files)
        return json.loads(files[0].read_text())

    def _ledger_rows(self, root: Path, change: str) -> list:
        p = root / ".gatedloop" / "runs" / f"{change}.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

    def test_ci_marker_records_scoped_surface_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)
            (root / "frontend").mkdir()
            (root / "frontend" / "app.js").write_text("x\n")
            _git(root, "add", "frontend/app.js")

            r = _run_gates(root, "run", "ci", "--change", "c")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self._marker(root, "ci")["scope"], "frontend")
            rows = self._ledger_rows(root, "c")
            self.assertEqual(rows[-1]["gate"], "ci")
            self.assertEqual(rows[-1]["scope"], "frontend")

    def test_ci_marker_records_full_scope_when_nothing_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)

            r = _run_gates(root, "run", "ci", "--change", "c")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self._marker(root, "ci")["scope"], "full")
            rows = self._ledger_rows(root, "c")
            self.assertEqual(rows[-1]["scope"], "full")


# ---------- 2.1: check-commit accepts a fresh SCOPED marker -----------------

class TestCheckCommitAcceptsScopedMarker(unittest.TestCase):
    def test_scoped_marker_satisfies_check_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)
            (root / "frontend").mkdir()
            (root / "frontend" / "app.js").write_text("x\n")
            _git(root, "add", "frontend/app.js")
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)

            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            check = _run_gates(root, "discipline", "check-commit", tree)

            self.assertEqual(check.returncode, 0, check.stderr)


# ---------- 2.2: the completion/merge requirement — full scope only --------

class TestCompletionRequiresFullScope(unittest.TestCase):
    def test_gate_marker_check_refuses_a_scoped_only_marker_when_full_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)
            (root / "frontend").mkdir()
            (root / "frontend" / "app.js").write_text("x\n")
            _git(root, "add", "frontend/app.js")
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()

            check = _run_gates(root, "gate-marker", "check", "ci", tree, "--require-scope", "full")

            self.assertNotEqual(check.returncode, 0)
            self.assertIn("full", check.stderr)

    def test_gate_marker_check_passes_a_full_marker_when_full_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)
            # Nothing staged -- selection falls back to "full" (D2: this is
            # the mechanism behind "full ci is always the last word").
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()

            check = _run_gates(root, "gate-marker", "check", "ci", tree, "--require-scope", "full")

            self.assertEqual(check.returncode, 0, check.stderr)

    def test_gate_marker_check_without_require_scope_is_unchanged(self):
        """Backward compatible: omitting `--require-scope` behaves exactly
        as before -- any fresh marker for the tree passes, scope or not."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_ONE_SCOPED_SURFACE)
            (root / "frontend").mkdir()
            (root / "frontend" / "app.js").write_text("x\n")
            _git(root, "add", "frontend/app.js")
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()

            check = _run_gates(root, "gate-marker", "check", "ci", tree)

            self.assertEqual(check.returncode, 0, check.stderr)


def _run_hook(hook: Path, root: Path, command: str):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(root)})
    return subprocess.run(
        ["bash", str(hook)], input=payload, cwd=str(root), env=env, capture_output=True, text=True,
    )


LIVE_CHECK_AND_SCOPED_CI_MANIFEST = """\
gatesVersion: 1
gates:
  ci: "echo GLOBAL-CI"
surfaces:
  - name: frontend
    match: "frontend/**"
    gates:
      ci: "echo SCOPED-CI"
  - name: all
    match: "**"
    live-check: "true"
"""


class TestMergeHookRequiresFullScopeCi(unittest.TestCase):
    """End to end through the real `hooks/gate-merge.sh` (design D2/2.2/2.3):
    a scoped-only `ci` marker on the branch head satisfies a commit but is
    refused at the merge; an unscoped ('full') one is accepted."""

    def test_merge_denied_with_only_a_scoped_ci_marker_on_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, LIVE_CHECK_AND_SCOPED_CI_MANIFEST)
            _git(root, "branch", "feature")
            (root / "frontend").mkdir()
            (root / "frontend" / "app.js").write_text("x\n")
            _git(root, "add", "frontend/app.js")
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            _git(root, "commit", "-m", "scoped task commit")
            r = _run_gates(root, "run", "live-check", "--all")
            self.assertEqual(r.returncode, 0, r.stderr)

            result = _run_hook(MERGE_HOOK, root, "git merge feature")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ci", result.stderr)

    def test_merge_allowed_once_ci_is_reverified_unscoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, LIVE_CHECK_AND_SCOPED_CI_MANIFEST)
            _git(root, "branch", "feature")
            (root / "frontend").mkdir()
            (root / "frontend" / "app.js").write_text("x\n")
            _git(root, "add", "frontend/app.js")
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            _git(root, "commit", "-m", "scoped task commit")
            # Change completion: nothing staged -> selection falls back to
            # "full" (D1), re-verifying the head with the real, global gate.
            r = _run_gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = _run_gates(root, "run", "live-check", "--all")
            self.assertEqual(r.returncode, 0, r.stderr)

            result = _run_hook(MERGE_HOOK, root, "git merge feature")

            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
