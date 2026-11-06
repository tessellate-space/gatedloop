"""`gates tests check` refuses held tests staged off a change branch
(openspec change `plan-preflight`, design D8; task 2.1).

The holding area is committed only on its change's branch, in the authoring
commit. Off one (a `plan/*` branch, the merge target, any branch naming no
active change), `gates tests check` used to say "nothing to check" and
pass. It now refuses a staged path under `.gatedloop/authored/`, naming
each one, and both commit hooks (which already run it) deny the commit.
Every other verdict is unchanged.

Stdlib only, per `zero-dep-shim`. Real git repositories and a linked
worktree, the shim and both hooks driven as subprocesses. Run with:
python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import (CHANGE, PreflightRepo, git, git_hook,  # noqa: E402
                                tool_denied, tool_hook, write)

HELD = f".gatedloop/authored/{CHANGE}/1.1/tests/test_widget.py.authored"
LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"


class HeldOffChangeBranchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.r = PreflightRepo(self.tmp / "work")

    def tearDown(self):
        self._tmp.cleanup()

    def stage_held(self, root: Path):
        write(root, HELD, "def test_widget():\n    assert False\n")
        git(root, "add", "-f", HELD)

    def assert_refused(self, root: Path):
        out = self.r.gates("tests", "check", cwd=root)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn(HELD, out.stdout + out.stderr)
        self.assertTrue(tool_denied(tool_hook(root)))
        self.assertNotEqual(git_hook(root).returncode, 0)

    def test_held_file_staged_with_the_plan_on_the_plan_branch(self):
        self.r.edit(f"{self.r.rel_dir}/tasks.md", "Add the widget", "Add the small widget")
        git(self.r.root, "add", self.r.rel_dir)
        self.stage_held(self.r.root)
        self.assert_refused(self.r.root)

    def test_held_file_staged_on_main_in_a_linked_worktree(self):
        wt = self.tmp / "wt-main"
        git(self.r.root, "worktree", "add", str(wt), "main")
        self.stage_held(wt)
        self.assert_refused(wt)

    def test_plan_only_commit_with_its_ledger_is_still_allowed(self):
        self.r.edit(f"{self.r.rel_dir}/tasks.md", "Add the widget", "Add the small widget")
        write(self.r.root, LEDGER, json.dumps({"gate": "plan-round", "change": CHANGE}) + "\n")
        git(self.r.root, "add", self.r.rel_dir, LEDGER)
        out = self.r.gates("tests", "check")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        tool = tool_hook(self.r.root)
        self.assertFalse(tool_denied(tool), tool.stdout + tool.stderr)
        hook = git_hook(self.r.root)
        self.assertEqual(hook.returncode, 0, hook.stdout + hook.stderr)

    def test_a_staged_deletion_of_a_held_file_is_not_refused(self):
        write(self.r.root, HELD, "x\n")
        git(self.r.root, "add", "-f", HELD)
        git(self.r.root, "commit", "-m", "stray held file", "--no-verify")
        git(self.r.root, "rm", "--cached", "-q", HELD)
        self.assertEqual(self.r.gates("tests", "check").returncode, 0)

    def test_authoring_commit_on_the_change_branch_keeps_todays_verdict(self):
        git(self.r.root, "checkout", "-b", CHANGE)
        self.stage_held(self.r.root)
        out = self.r.gates("tests", "check")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn(f"no handoff recorded for '{CHANGE}'", out.stdout)


if __name__ == "__main__":
    unittest.main()
