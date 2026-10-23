"""Tests for `gates halt record` and `gates intervention record`
(escalation-outcomes design D1, D2, D4).

Stdlib only, per `zero-dep-shim`. Builds throwaway git repos under a temp
directory and drives the shim as a subprocess (black-box, matching how the
loop and the hooks call it), then reads the durable
`.gatedloop/runs/<change>.jsonl` ledger back.

Run with:  python3 -m unittest discover -s tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

CAUSES = ("missing-oracle", "weak-spec", "oracle-conflict", "stalled",
          "environment", "other")


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    )


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _rows(root, change="my-change"):
    p = root / ".gatedloop" / "runs" / f"{change}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _repo(tmp, branch="my-change"):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    if branch != "main":
        _git(root, "checkout", "-b", branch)
        (root / "openspec" / "changes" / branch).mkdir(parents=True, exist_ok=True)
    return root


def _head_tree(root):
    return _git(root, "rev-parse", "HEAD^{tree}").stdout.strip()


class TestHaltRecord(unittest.TestCase):
    def test_records_one_halt_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _run_gates(root, "halt", "record", "stalled", "--task", "2.3",
                           "--detail", "x")
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = _rows(root)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["gate"], "halt")
            self.assertEqual(row["task"], "2.3")
            self.assertEqual(row["cause"], "stalled")
            self.assertEqual(row["detail"], "x")
            self.assertIsNone(row["exit"])
            self.assertEqual(row["tree"], _head_tree(root))
            self.assertEqual(row["change"], "my-change")

    def test_every_cause_in_the_set_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            for cause in CAUSES:
                r = _run_gates(root, "halt", "record", cause, "--task", "1.1",
                               "--detail", "d")
                self.assertEqual(r.returncode, 0, (cause, r.stderr))
            self.assertEqual([x["cause"] for x in _rows(root)], list(CAUSES))

    def test_unknown_cause_refused_naming_the_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _run_gates(root, "halt", "record", "flaky", "--task", "2.3")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("flaky", r.stderr)
            for cause in CAUSES:
                self.assertIn(cause, r.stderr)
            self.assertEqual(_rows(root), [])

    def test_other_without_detail_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _run_gates(root, "halt", "record", "other", "--task", "2.3")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("other", r.stderr)
            self.assertIn("--detail", r.stderr)
            self.assertEqual(_rows(root), [])

    def test_other_with_blank_detail_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _run_gates(root, "halt", "record", "other", "--task", "2.3",
                           "--detail", "   ")
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(_rows(root), [])

    def test_off_a_change_branch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, branch="main")
            r = _run_gates(root, "halt", "record", "stalled", "--task", "2.3")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--change", r.stderr)
            self.assertFalse((root / ".gatedloop" / "runs").exists())

    def test_explicit_change_on_main_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, branch="main")
            r = _run_gates(root, "halt", "record", "weak-spec", "--task", "1.1",
                           "--change", "other-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_rows(root, "other-change")[0]["cause"], "weak-spec")


class TestInterventionRecord(unittest.TestCase):
    """Design D4: the hand-written fallback for a pause that did not go
    through the question tool, sharing the halt writer's validation."""

    def test_records_an_ask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _run_gates(root, "intervention", "record", "ask", "--task", "2.3",
                           "--detail", "which port?")
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = _rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["gate"], "intervention")
            self.assertEqual(rows[0]["cause"], "ask")
            self.assertEqual(rows[0]["detail"], "which port?")
            self.assertEqual(rows[0]["task"], "2.3")
            self.assertIsNone(rows[0]["exit"])

    def test_unknown_kind_refused_naming_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            r = _run_gates(root, "intervention", "record", "stalled", "--task", "2.3")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("stalled", r.stderr)
            self.assertIn("ask", r.stderr)
            self.assertIn("human-commit", r.stderr)
            self.assertEqual(_rows(root), [])

    def test_off_a_change_branch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, branch="main")
            r = _run_gates(root, "intervention", "record", "ask")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--change", r.stderr)


if __name__ == "__main__":
    unittest.main()
