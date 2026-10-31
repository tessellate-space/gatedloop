"""The union's scope is recorded and announced (err-full-scoping D2, D3).

A multi-surface `unit` run names every surface whose command ran, joined with
`+` in run order and `full` for the global component, in its announcement and
in one ledger row, so the attempt budget reads the invocation as one run. A
multi-surface `ci` still runs the global `ci` and records `full`.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_union_scope", str(GATES_SHIM))
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


def _write(root: Path, rel: str, text: str = "x\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _manifest(e2e_override: bool) -> str:
    e2e = '    gates:\n      unit: "echo E2E"\n      ci: "echo E2E-CI"\n' if e2e_override else ""
    return (
        "gatesVersion: 1\n"
        "gates:\n"
        '  ci: "echo GLOBAL-CI"\n'
        '  unit: "echo GLOBAL"\n'
        "surfaces:\n"
        "  - name: frontend\n"
        '    match: "frontend/**"\n'
        "    gates:\n"
        '      unit: "echo FRONTEND; exit 1"\n'
        '      ci: "echo FRONTEND-CI"\n'
        "  - name: e2e\n"
        '    match: "e2e/**"\n'
        f"{e2e}"
        "  - name: all\n"
        '    match: "**"\n'
    )


class TestUnionScope(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def init(self, manifest: str) -> None:
        _git(self.root, "init", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(manifest)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-m", "init")
        _write(self.root, "frontend/app.test.js")
        _write(self.root, "e2e/steps.js")

    def rows(self) -> list[dict]:
        p = self.root / ".gatedloop" / "runs" / "c.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]

    def test_scope_names_both_surfaces(self):
        self.init(_manifest(e2e_override=True))

        r = _run_gates(self.root, "run", "unit", "--change", "c", "--task", "1.1")

        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gatedloop: unit[frontend+e2e] — ", r.stderr)
        unit_rows = [x for x in self.rows() if x["gate"] == "unit"]
        self.assertEqual(len(unit_rows), 1, unit_rows)
        self.assertEqual(unit_rows[0]["scope"], "frontend+e2e")

    def test_global_component_is_named_full(self):
        self.init(_manifest(e2e_override=False))

        r = _run_gates(self.root, "run", "unit", "--change", "c", "--task", "1.1")

        self.assertNotEqual(r.returncode, 0)
        self.assertIn("gatedloop: unit[frontend+full] — ", r.stderr)
        self.assertEqual([x["scope"] for x in self.rows() if x["gate"] == "unit"],
                         ["frontend+full"])

    def test_budget_reads_the_invocation_as_one_run(self):
        self.init(_manifest(e2e_override=True))

        _run_gates(self.root, "run", "unit", "--change", "c", "--task", "1.1")

        # One red row: the task's red run, and no failed attempt yet.
        self.assertEqual(gates._attempt_state(self.rows(), "1.1"), (True, 0))

    def test_multi_surface_ci_records_full(self):
        self.init(_manifest(e2e_override=True))
        _git(self.root, "add", "frontend/app.test.js", "e2e/steps.js")

        r = _run_gates(self.root, "run", "ci", "--change", "c")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gatedloop: ci[full] — ", r.stderr)
        self.assertEqual([x["scope"] for x in self.rows() if x["gate"] == "ci"], ["full"])


if __name__ == "__main__":
    unittest.main()
