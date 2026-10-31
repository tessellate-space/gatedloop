"""Every ledger row carries its row version `v` (stability-contract D1).

The regressions: a row kind appended without `v`, so a newer reader cannot
tell a version-1 row from one written by a plugin it does not know; and a
caller-supplied `v` reaching the file, so a row could claim a version its
writer does not write. The shim sets `v` itself, the way it sets `session`.

Real git and the real shim, through `_merge_fixture`'s environment. Stdlib
only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import GATES_SHIM, clean_env, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_row_version", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "demo"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'

# One command per row kind a loop writes in the ordinary course of a task.
ROW_COMMANDS = (
    ("ci", ["run", "ci", "--task", "1.1"]),
    ("unit", ["run", "unit", "--task", "1.1", "--attempt", "1"]),
    ("task-start", ["task", "start", "1.1"]),
    ("review", ["review", "record", "clean", "--task", "1.1"]),
    ("halt", ["halt", "record", "weak-spec", "--detail", "which field?"]),
    ("intervention", ["intervention", "record", "ask", "--task", "1.1"]),
    ("attempt-note", ["attempt", "note", "1.1", "--hypothesis", "h", "--changed", "c",
                      "--oracle", "o", "--next", "n"]),
)


def _repo(tmp: Path) -> Path:
    root = tmp / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    tasks = root / "openspec" / "changes" / CHANGE / "tasks.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text("## 1. Do it\n\n- [ ] 1.1 Do the thing\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    git(root, "checkout", "-q", "-b", CHANGE)
    return root


def _rows(root: Path) -> list[dict]:
    p = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


class EveryRowKindCarriesVTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_each_row_kind_a_task_writes_carries_v_1(self):
        for gate, args in ROW_COMMANDS:
            r = subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=self.root,
                               capture_output=True, text=True, env=clean_env())
            self.assertEqual(r.returncode, 0, f"{args}: {r.stdout}{r.stderr}")
        rows = _rows(self.root)
        self.assertEqual([r["gate"] for r in rows], [g for g, _ in ROW_COMMANDS])
        for row in rows:
            self.assertEqual(row.get("v"), 1, f"{row['gate']} row: {row}")

    def test_a_caller_supplied_v_is_overwritten(self):
        gates._append_ledger_row(self.root, {"change": CHANGE, "gate": "ci", "exit": 0, "v": 99})
        gates._append_ledger_row(self.root, {"change": CHANGE, "gate": "ci", "exit": 0, "v": None})
        self.assertEqual([r.get("v") for r in _rows(self.root)], [1, 1])


if __name__ == "__main__":
    unittest.main()
