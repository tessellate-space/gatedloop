"""`gates tests defect <task> --kind setup|assertion` (authored-test-kinds
design D3): the kind is required, each kind has its own cap, each cap names
its own halt cause, and rows written before kinds existed count as
`assertion`.

Stdlib only, per `zero-dep-shim`. Builds throwaway git repos under a temp
directory and drives the shim as a subprocess, then reads the ledger back.

Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

CHANGE = "demo-change"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "false"\n'


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


def _rows(root):
    p = _ledger(root)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _defects(root):
    return [r for r in _rows(root) if r["gate"] == "test-defect"]


def _repo(tmp):
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
    held = root / ".gatedloop" / "authored" / CHANGE / "1.1" / "tests" / "test_calc.py.authored"
    held.parent.mkdir(parents=True)
    held.write_text("def test_add():\n    assert add(2, 3) == 5\n")
    result = _run_gates(root, "tests", "handoff", CHANGE)
    assert result.returncode == 0, result.stderr
    return root


def _defect(root, kind, detail, task="1.1"):
    args = ["tests", "defect", task, "--detail", detail]
    if kind is not None:
        args += ["--kind", kind]
    return _run_gates(root, *args)


class TestTheKindIsRequired(unittest.TestCase):
    """Regression guarded: a defect recorded with no kind, which the caps
    can only guess at — the point of the kind is which cap it spends."""

    def test_records_the_kind(self):
        for kind in ("setup", "assertion"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp)
                result = _defect(root, kind, "fixture path is wrong")
                self.assertEqual(result.returncode, 0, result.stderr)
                (row,) = _defects(root)
                self.assertEqual((row["task"], row["kind"], row["detail"]),
                                 ("1.1", kind, "fixture path is wrong"))

    def test_refuses_a_missing_or_unknown_kind_and_writes_nothing(self):
        for kind in (None, "flaky"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp)
                result = _defect(root, kind, "something")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("--kind", result.stderr)
                self.assertEqual(_defects(root), [])


class TestSeparateCaps(unittest.TestCase):
    """Regressions guarded: fixture mistakes spending the behaviour cap
    (issue #42), a setup cap that never stops, and either cap halting
    with the other's cause."""

    def test_setup_defects_do_not_spend_the_assertion_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            for n in (1, 2):
                self.assertEqual(_defect(root, "setup", f"s{n}").returncode, 0)

            result = _defect(root, "assertion", "asserts the wrong total")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(_defects(root)), 3)

    def test_third_assertion_defect_is_refused_naming_oracle_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            for n in (1, 2):
                self.assertEqual(_defect(root, "assertion", f"position {n}").returncode, 0)

            result = _defect(root, "assertion", "position 3")

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("oracle-conflict", result.stderr)
            self.assertIn("position 1", result.stderr)
            self.assertIn("position 2", result.stderr)
            self.assertEqual(len(_defects(root)), 2)

    def test_fourth_setup_defect_is_refused_naming_weak_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            for n in (1, 2, 3):
                self.assertEqual(_defect(root, "setup", f"s{n}").returncode, 0)

            result = _defect(root, "setup", "s4")

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("weak-spec", result.stderr)
            self.assertNotIn("oracle-conflict", result.stderr)
            self.assertEqual(len(_defects(root)), 3)

    def test_caps_are_per_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            for n in (1, 2):
                self.assertEqual(_defect(root, "assertion", f"a{n}").returncode, 0)

            result = _defect(root, "assertion", "other task", task="1.2")

            self.assertEqual(result.returncode, 0, result.stderr)


class TestLegacyRowsCountAsAssertion(unittest.TestCase):
    """Design D3: a row written before kinds existed reads as `assertion`,
    the conservative reading. Regression guarded: an upgrade mid-change
    resetting a task's behaviour cap to zero."""

    def _legacy(self, root, n):
        with _ledger(root).open("a") as f:
            for i in range(n):
                f.write(json.dumps({
                    "ts": f"2026-09-01T00:0{i}:00+00:00", "gate": "test-defect",
                    "exit": None, "duration_ms": 0, "change": CHANGE, "task": "1.1",
                    "detail": f"legacy {i}",
                }) + "\n")

    def test_two_kindless_rows_spend_the_assertion_cap_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            self._legacy(root, 2)

            refused = _defect(root, "assertion", "a third position")
            accepted = _defect(root, "setup", "fixture path")

            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertIn("oracle-conflict", refused.stderr)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)


if __name__ == "__main__":
    unittest.main()
