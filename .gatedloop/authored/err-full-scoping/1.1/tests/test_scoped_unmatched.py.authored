"""An unmatched changed path errs full (err-full-scoping D1, #61).

`_select_scoped_gate` used to count only the hot non-catch-all surfaces, so a
diff holding one scoped surface's file plus a file no surface matches ran that
surface's scoped command. Any path matched by no non-catch-all surface now
selects the global gate, and the announcement names the first such path.

The loop's own state (`.gatedloop/`: the ledger, the holding area) is not a
project path and never counts as unmatched: every task commit stages its
ledger row, so counting it would end scoping for every commit.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_unmatched", str(GATES_SHIM))
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


def _write(root: Path, rel: str, text: str = "x\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _log(root: Path, gate: str) -> str:
    logs = list((root / ".gatedloop" / "out").glob(f"{gate}-*.log"))
    assert len(logs) == 1, logs
    return logs[0].read_text()


SCOPED_NO_CATCHALL = """\
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
"""

SCOPED_WITH_CATCHALL = SCOPED_NO_CATCHALL + """\
  - name: everything
    match: "**"
"""


class TestUnmatchedPathSelection(unittest.TestCase):
    def test_unmatched_path_beside_scoped_surface_selects_global(self):
        m = gates._parse_yaml_text(SCOPED_NO_CATCHALL)
        spec, scope = gates._select_scoped_gate(m, "ci", ["frontend/app.js", "scripts/build.sh"])
        self.assertEqual((spec, scope), ("echo GLOBAL-CI", "full"))

    def test_catchall_does_not_count_as_a_match(self):
        m = gates._parse_yaml_text(SCOPED_WITH_CATCHALL)
        spec, scope = gates._select_scoped_gate(m, "ci", ["frontend/app.js", "scripts/build.sh"])
        self.assertEqual((spec, scope), ("echo GLOBAL-CI", "full"))

    def test_unit_selection_errs_full_on_unmatched_path(self):
        m = gates._parse_yaml_text(SCOPED_WITH_CATCHALL)
        spec, scope = gates._select_scoped_gate(m, "unit", ["frontend/app.test.js", "Makefile"])
        self.assertEqual((spec, scope), ("echo GLOBAL-UNIT", "full"))

    def test_wholly_scoped_diff_still_scopes(self):
        m = gates._parse_yaml_text(SCOPED_WITH_CATCHALL)
        spec, scope = gates._select_scoped_gate(m, "ci", ["frontend/app.js", "frontend/b.js"])
        self.assertEqual((spec, scope), ("echo SCOPED-CI", "frontend"))

    def test_loop_state_is_not_an_unmatched_path(self):
        # Every task commit stages its ledger row beside its code.
        m = gates._parse_yaml_text(SCOPED_WITH_CATCHALL)
        spec, scope = gates._select_scoped_gate(
            m, "ci", ["frontend/app.js", ".gatedloop/runs/c.jsonl"],
        )
        self.assertEqual((spec, scope), ("echo SCOPED-CI", "frontend"))


class TestUnmatchedPathEndToEnd(unittest.TestCase):
    def test_staged_unmatched_file_runs_global_ci_and_names_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, SCOPED_NO_CATCHALL)
            _write(root, "frontend/app.js")
            _write(root, "scripts/build.sh")
            _write(root, "scripts/a.sh")
            _git(root, "add", "frontend/app.js", "scripts/build.sh", "scripts/a.sh")

            r = _run_gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("GLOBAL-CI", _log(root, "ci"))
            # The first unmatched path in sorted order.
            self.assertIn("ci[full] — scripts/a.sh matches no surface", r.stderr)

    def test_staged_unmatched_file_with_catchall_runs_global_ci(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, SCOPED_WITH_CATCHALL)
            _write(root, "frontend/app.js")
            _write(root, "README.md")
            _git(root, "add", "frontend/app.js", "README.md")

            r = _run_gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("GLOBAL-CI", _log(root, "ci"))
            self.assertIn("ci[full] — README.md matches no surface", r.stderr)

    def test_working_set_unmatched_file_runs_global_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, SCOPED_WITH_CATCHALL)
            _write(root, "frontend/app.test.js")
            _write(root, "Makefile")  # untracked, never staged

            r = _run_gates(root, "run", "unit")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("GLOBAL-UNIT", _log(root, "unit"))
            self.assertIn("unit[full] — Makefile matches no surface", r.stderr)

    def test_wholly_scoped_staged_diff_runs_scoped_ci(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, SCOPED_WITH_CATCHALL)
            _write(root, "frontend/app.js")
            _git(root, "add", "frontend/app.js")

            r = _run_gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("SCOPED-CI", _log(root, "ci"))
            self.assertNotIn("matches no surface", r.stderr)


if __name__ == "__main__":
    unittest.main()
