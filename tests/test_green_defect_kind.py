"""The `green` test-defect kind (change `unblock-authored-lock`, design D5;
issue #56 tasks 3.1 and 5.1).

Placed tests that pass before any implementation had no truthful record:
the implementer could only file a `setup` or `assertion` defect, both of
which claim the tests are wrong, and spend a cap meant for something else.
The regressions: `green` refused as a kind; a `green` defect spending the
`setup` or `assertion` cap; a second `green` for a task accepted instead of
refused with the halt it names; and `green` missing from the reports that
count defects by kind.

Real git in throwaway repositories, driving the shim as the loop does and
reading the ledger back.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
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
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env())


def _rows(root):
    p = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _defects(root):
    return [r for r in _rows(root) if r["gate"] == "test-defect"]


def _repo(tmp):
    root = Path(tmp)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    change_dir = root / "openspec" / "changes" / CHANGE
    change_dir.mkdir(parents=True)
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "checkout", "-q", "-b", CHANGE)
    held = root / ".gatedloop" / "authored" / CHANGE / "1.1" / "tests" / "test_data.py.authored"
    held.parent.mkdir(parents=True)
    held.write_text("def test_values():\n    assert values() == [1, 2]\n")
    r = _gates(root, "tests", "handoff", CHANGE)
    assert r.returncode == 0, r.stdout + r.stderr
    return root


def _defect(root, kind, detail, task="1.1"):
    return _gates(root, "tests", "defect", task, "--kind", kind, "--detail", detail)


GREEN = "its placed tests passed before any implementation"


class GreenDefectTest(unittest.TestCase):
    def test_a_green_defect_is_recorded_with_its_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)

            r = _defect(root, "green", GREEN)

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            (row,) = _defects(root)
            self.assertEqual((row["task"], row["kind"], row["detail"]), ("1.1", "green", GREEN))

    def test_a_green_defect_spends_neither_other_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            self.assertEqual(_defect(root, "green", GREEN).returncode, 0)

            setups = [_defect(root, "setup", f"fixture path {n}") for n in (1, 2, 3)]
            assertions = [_defect(root, "assertion", f"position {n}") for n in (1, 2)]

            for r in setups + assertions:
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(len(_defects(root)), 6)

    def test_a_second_green_defect_is_refused_naming_oracle_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            self.assertEqual(_defect(root, "green", GREEN).returncode, 0)

            r = _defect(root, "green", "still green after the author's answer")

            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn("gates halt record oracle-conflict", r.stderr)
            self.assertIn(GREEN, r.stderr)
            self.assertEqual(len(_defects(root)), 1)

    def test_the_green_cap_is_per_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            self.assertEqual(_defect(root, "green", GREEN).returncode, 0)

            r = _defect(root, "green", GREEN, task="1.2")

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_show_and_outcomes_count_green_by_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            self.assertEqual(_defect(root, "green", GREEN).returncode, 0)
            self.assertEqual(_defect(root, "setup", "fixture path").returncode, 0)

            show = json.loads(_gates(root, "tests", "show", CHANGE, "--json").stdout)
            table = _gates(root, "tests", "show", CHANGE).stdout
            outcomes = json.loads(_gates(
                root, "stats", "--outcomes", "--change", CHANGE, "--json").stdout)
            outcomes_table = _gates(root, "stats", "--outcomes", "--change", CHANGE).stdout

        self.assertEqual(show["tasks"]["1.1"]["defects_by_kind"],
                         {"assertion": 0, "setup": 1, "green": 1})
        self.assertRegex(table, r"green.*" + GREEN)
        (c,) = outcomes["changes"]
        self.assertEqual(c["test_defects_by_kind"], {"assertion": 0, "setup": 1, "green": 1})
        self.assertRegex(outcomes_table, r"test defects:\s+2 \(setup 1, assertion 0, green 1\)")


if __name__ == "__main__":
    unittest.main()
