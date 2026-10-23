"""A merge step whose gate did not run is reported as not run (design D1 of
`merge-lane-friction`, issue #43).

Step 3 (`ci` on the merged tree) and step 5 (`confirm`) used to read every
non-zero exit as a red merged tree. Exit 75 means the gate never ran: its
serialized lock stayed busy past the bound, or a declared precondition
failed. The regressions these catch:

- a lock-busy or precondition 75 at step 3 reported as "the merged tree is
  what failed", or exiting 3 instead of 75, so a caller's retry-on-busy rule
  never applies;
- step 5's 75 exiting 5;
- the not-run path forgetting to restore the checkout, or publishing;
- a real red at step 3 swallowed by the new branch.

Real git with a bare remote (the merged tree only exists once git squashes),
as in the other merge tests. A busy lock is held by this test process on
its own handle (`HeldLock`) and the wait runs on an injected clock
(`FakeTime`, `gatedloop.test-quality` item 7), so those cases call
`cmd_merge` in process. The precondition and red cases need no wait and run
the shim as a subprocess.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _merge_fixture import CHANGE, GATES_SHIM, FakeTime, HeldLock, MergeRepo, combined

_loader = importlib.machinery.SourceFileLoader("gates_shim_merge_not_run", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

SERIALIZED_CI = (
    'gatesVersion: 1\ngates:\n  ci: "true"\n'
    "concurrency:\n  serialize:\n    - ci\n  max-wait-seconds: 5\n"
)
SERIALIZED_CONFIRM = (
    'gatesVersion: 1\ngates:\n  ci: "true"\n  confirm: "true"\n'
    "concurrency:\n  serialize:\n    - confirm\n  max-wait-seconds: 5\n"
)
# The flag file exists only in the primary checkout, untracked: the lane's
# own runs pass, and the merge's run in the primary does not.
CI_PRECONDITION = (
    'gatesVersion: 1\ngates:\n  ci:\n    run: "true"\n    requires: "test ! -f no-env.flag"\n'
)
CONFIRM_PRECONDITION = (
    'gatesVersion: 1\ngates:\n  ci: "true"\n'
    '  confirm:\n    run: "true"\n    requires: "test ! -f no-env.flag"\n'
)
RED_CI = 'gatesVersion: 1\ngates:\n  ci: "test ! -f red.flag"\n'


def _stop_line(text: str, step: int) -> str:
    line = next((x for x in text.splitlines() if f"stopped at step {step}" in x), None)
    if line is None:
        raise AssertionError(f"no 'stopped at step {step}' line in:\n{text}")
    return line


class MergeStepNotRunTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.held = None

    def tearDown(self):
        if self.held is not None:
            self.held.release()
        self._tmp.cleanup()

    def _ready(self, manifest: str) -> MergeRepo:
        repo = MergeRepo(self.tmp, manifest=manifest)
        repo.start_change(lane=True)
        repo.task_commit("one.txt", "1\n", "add the thing")
        repo.prove_head()
        return repo

    def _merge_in_process(self, repo: MergeRepo) -> tuple[int, str]:
        """`gates merge` in this process, on a fake clock, so a busy lock's
        wait reaches its bound without waiting."""
        m = gates._mini_yaml(repo.manifest)
        m["__root__"] = str(repo.primary)
        fake = FakeTime()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, repo.env(), clear=True), \
                mock.patch.object(gates.time, "monotonic", fake.clock), \
                mock.patch.object(gates.time, "time", fake.wall), \
                mock.patch.object(gates.time, "sleep", fake.sleep), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = gates.cmd_merge(m, repo.primary, argparse.Namespace(change=CHANGE))
        return rc, out.getvalue() + err.getvalue()

    def _assert_untouched(self, repo: MergeRepo, origin_before: str, head_before: tuple) -> None:
        self.assertEqual(repo.origin_main(), origin_before)
        self.assertEqual(repo.head_state(), head_before)
        self.assertEqual(repo.pushes(), 0)

    def test_a_busy_ci_lock_at_step_3_is_not_run_and_names_the_holder(self):
        repo = self._ready(SERIALIZED_CI)
        origin_before, head_before = repo.origin_main(), repo.head_state()
        holder_pid = os.getpid()
        self.held = HeldLock(repo.primary / ".git", "ci", holder_pid)

        rc, text = self._merge_in_process(repo)

        self.assertEqual(rc, gates.PRECONDITION_EXIT_CODE, text)
        line = _stop_line(text, 3)
        self.assertIn("did not run", line)
        self.assertIn(f"pid {holder_pid}", line)
        self._assert_untouched(repo, origin_before, head_before)

    def test_a_failed_precondition_at_step_3_is_not_run_and_names_it(self):
        repo = self._ready(CI_PRECONDITION)
        (repo.primary / "no-env.flag").write_text("")
        origin_before, head_before = repo.origin_main(), repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, gates.PRECONDITION_EXIT_CODE, combined(r))
        line = _stop_line(combined(r), 3)
        self.assertIn("did not run", line)
        self.assertIn("test ! -f no-env.flag", line)
        self._assert_untouched(repo, origin_before, head_before)

    def test_a_red_merged_tree_still_exits_3_as_a_failed_merged_tree(self):
        repo = self._ready(RED_CI)
        (repo.primary / "red.flag").write_text("")
        origin_before, head_before = repo.origin_main(), repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, 3, combined(r))
        self.assertIn("is what failed", _stop_line(combined(r), 3))
        self._assert_untouched(repo, origin_before, head_before)

    def test_a_busy_confirm_lock_at_step_5_is_not_run_and_names_the_holder(self):
        repo = self._ready(SERIALIZED_CONFIRM)
        origin_before = repo.origin_main()
        primary_before = repo.head_state()
        holder_pid = os.getpid()
        self.held = HeldLock(repo.primary / ".git", "confirm", holder_pid)

        rc, text = self._merge_in_process(repo)

        self.assertEqual(rc, gates.PRECONDITION_EXIT_CODE, text)
        line = _stop_line(text, 5)
        self.assertIn("did not run", line)
        self.assertIn(f"pid {holder_pid}", line)
        self._assert_untouched(repo, origin_before, primary_before)

    def test_a_failed_precondition_at_step_5_exits_75_not_5(self):
        repo = self._ready(CONFIRM_PRECONDITION)
        (repo.primary / "no-env.flag").write_text("")
        origin_before, head_before = repo.origin_main(), repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, gates.PRECONDITION_EXIT_CODE, combined(r))
        line = _stop_line(combined(r), 5)
        self.assertIn("did not run", line)
        self.assertIn("test ! -f no-env.flag", line)
        self._assert_untouched(repo, origin_before, head_before)


if __name__ == "__main__":
    unittest.main()
