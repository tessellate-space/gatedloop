"""The shim names the commit gate in effect (openspec change `ci-at`, design
D7; the loop-enforcement delta's "The shim names the commit gate in effect"
requirement).

The prompts never read `.gates.yaml`: they run the gate `gates task start`
and `gates tests handoff` name. The regressions: no line, the wrong gate for
the mode, the line leaking onto stdout (which callers parse), and a refused
handoff printing a gate as though it had succeeded.

Real git in a throwaway repository. Stdlib only, per `zero-dep-shim`.
Run with: python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

CHANGE = "demo-change"
BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
READY = BASE + "loop:\n  ci-at: ready\n"
CI_LINE = "gatedloop: commit gate: gates run ci"
UNIT_LINE = "gatedloop: commit gate: gates run unit"
READY_NOTE = "the full ci runs before gates ledger record-ready"


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
                          capture_output=True, text=True, env=_env(), timeout=120)


class _Repo(unittest.TestCase):
    MANIFEST = BASE

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(self.MANIFEST)
        d = self.root / "openspec" / "changes" / CHANGE
        d.mkdir(parents=True)
        (d / "tasks.md").write_text("## 1. Work\n\n- [ ] 1.1 do it\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "init")
        _git(self.root, "checkout", "-q", "-b", CHANGE)

    def tearDown(self):
        self._tmp.cleanup()

    def _hold_a_test(self):
        held = self.root / ".gatedloop" / "authored" / CHANGE / "1.1" / "tests" / "test_a.py.authored"
        held.parent.mkdir(parents=True)
        held.write_text("def test_a():\n    assert False\n")


class TestUnderTask(_Repo):
    MANIFEST = BASE
    LINE = CI_LINE
    OTHER = UNIT_LINE

    def test_task_start_names_the_gate_on_stderr_only(self):
        r = _gates(self.root, "task", "start", "1.1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(self.LINE, r.stderr)
        self.assertNotIn(self.OTHER, r.stderr)
        self.assertNotIn("commit gate", r.stdout)
        self.assertTrue(r.stdout.startswith("gatedloop: recorded the task-start tree for task 1.1"))

    def test_a_successful_handoff_names_the_gate_on_stderr_only(self):
        self._hold_a_test()
        r = _gates(self.root, "tests", "handoff", CHANGE, "--inline")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(self.LINE, r.stderr)
        self.assertNotIn("commit gate", r.stdout)
        self.assertTrue(r.stdout.startswith("gatedloop: recorded the inline handoff"))

    def test_a_refused_handoff_prints_no_gate(self):
        r = _gates(self.root, "tests", "handoff", CHANGE)  # nothing held
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("commit gate", r.stdout + r.stderr)


class TestUnderReady(TestUnderTask):
    MANIFEST = READY
    LINE = UNIT_LINE
    OTHER = CI_LINE

    def test_the_line_carries_the_ready_note(self):
        r = _gates(self.root, "task", "start", "1.1")
        self.assertIn(READY_NOTE, r.stderr)
        self.assertIn("loop.ci-at: ready", r.stderr)


if __name__ == "__main__":
    unittest.main()
