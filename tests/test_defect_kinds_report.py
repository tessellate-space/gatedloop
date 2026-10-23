"""`gates tests show` and `gates stats --outcomes` report test defects by
kind (authored-test-kinds design D3, "mislabelling is visible"), and show
names a characterization task's declaration (design D1).

Stdlib only, per `zero-dep-shim`. Builds throwaway git repos under a temp
directory and drives the shim as a subprocess.

Run with:  python3 -m unittest discover -s tests
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

_loader = importlib.machinery.SourceFileLoader("gates_shim_defect_report", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "demo-change"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "false"\n'
REASON = "pins the report's current output"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=_env(),
    )


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True, env=_env(),
    )


def _ledger(root):
    return root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"


def _repo(tmp):
    """1.1 is a characterization task, 1.2 an ordinary one; handed off."""
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    change_dir = root / "openspec" / "changes" / CHANGE
    change_dir.mkdir(parents=True)
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    held = root / ".gatedloop" / "authored" / CHANGE
    for task, path in (("1.1", "tests/test_report.py"), ("1.2", "tests/test_calc.py")):
        p = held / task / f"{path}.authored"
        p.parent.mkdir(parents=True)
        p.write_text("def test_it():\n    assert True\n")
    (held / "1.1" / "CHARACTERIZATION").write_text(REASON + "\n")
    result = _run_gates(root, "tests", "handoff", CHANGE)
    assert result.returncode == 0, result.stderr
    return root


def _defect(root, task, kind, detail):
    result = _run_gates(root, "tests", "defect", task, "--kind", kind, "--detail", detail)
    assert result.returncode == 0, result.stderr


def _legacy_defect(root, task, detail):
    with _ledger(root).open("a") as f:
        f.write(json.dumps({
            "ts": "2026-09-01T00:00:00+00:00", "gate": "test-defect", "exit": None,
            "duration_ms": 0, "change": CHANGE, "task": task, "detail": detail,
        }) + "\n")


def _seeded(tmp):
    root = _repo(tmp)
    _defect(root, "1.2", "setup", "imports a module that moved")
    _defect(root, "1.2", "setup", "fixture path is stale")
    _legacy_defect(root, "1.2", "expects the old total")
    return root


class TestShowReportsDefectsByKind(unittest.TestCase):
    """Regressions guarded: a defect's kind invisible to whoever reads the
    authoring state, so a mislabelled defect goes unseen; a kindless legacy
    row shown as anything but `assertion`; and a characterization task
    shown as an ordinary one."""

    def test_json_counts_and_lists_each_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _seeded(tmp)
            result = _run_gates(root, "tests", "show", CHANGE, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        t = doc["tasks"]["1.2"]
        self.assertEqual(t["defects"], 3)
        self.assertEqual(t["defects_by_kind"], {"assertion": 1, "setup": 2})
        self.assertEqual(t["defect_log"], [
            {"kind": "setup", "detail": "imports a module that moved"},
            {"kind": "setup", "detail": "fixture path is stale"},
            {"kind": "assertion", "detail": "expects the old total"},
        ])
        self.assertIsNone(t["characterization"])
        self.assertEqual(doc["tasks"]["1.1"]["characterization"], REASON)
        self.assertEqual(doc["tasks"]["1.1"]["defects_by_kind"], {"assertion": 0, "setup": 0})

    def test_table_names_each_defect_with_its_kind_and_the_declaration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _seeded(tmp)
            result = _run_gates(root, "tests", "show", CHANGE)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertRegex(out, r"setup.*imports a module that moved")
        self.assertRegex(out, r"setup.*fixture path is stale")
        self.assertRegex(out, r"assertion.*expects the old total")
        self.assertRegex(out, r"1\.1.*characterization")
        self.assertIn(REASON, out)


class TestStatsReportsDefectsByKind(unittest.TestCase):
    """Regression guarded: `gates stats --outcomes` folding both kinds into
    one number, so a change whose author kept writing unrunnable tests reads
    the same as one whose author kept disagreeing about behaviour."""

    def test_outcomes_json_and_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _seeded(tmp)
            doc = json.loads(_run_gates(
                root, "stats", "--outcomes", "--change", CHANGE, "--json").stdout)
            table = _run_gates(root, "stats", "--outcomes", "--change", CHANGE).stdout
        (c,) = doc["changes"]
        self.assertEqual(c["test_defects"], 3)
        self.assertEqual(c["test_defects_by_kind"], {"assertion": 1, "setup": 2})
        self.assertRegex(table, r"test defects:\s+3 \(setup 2, assertion 1\)")

    def test_pure_counter_reads_kindless_rows_as_assertion(self):
        rows = [
            {"ts": "2026-09-01T00:00:00+00:00", "gate": "test-defect", "exit": None,
             "change": CHANGE, "task": "1.1", "detail": "old"},
            {"ts": "2026-09-01T00:01:00+00:00", "gate": "test-defect", "exit": None,
             "change": CHANGE, "task": "1.1", "detail": "new", "kind": "setup"},
        ]
        out = gates.outcomes_from_rows(rows)
        self.assertEqual(out["test_defects_by_kind"], {"assertion": 1, "setup": 1})


if __name__ == "__main__":
    unittest.main()
