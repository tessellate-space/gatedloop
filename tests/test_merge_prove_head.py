"""`gates merge` steps 0 and 1: preconditions, then prove the head (design
D2 of `merge-step`).

Step 1 commits the branch's trailing ledger rows, then runs the merge
hook's incoming-tree checks as functions against the NAMED change's ledger
and `<change>^{tree}` -- never the current branch. PR specloop PR 100 found the hook's
taint check resolving the change from the current branch, which during a
merge is `main`, so the check never fired; the taint test here runs from
`main` for exactly that reason. Each refusal must leave the target and the
primary checkout untouched.

These run real git in temporary repositories with a bare remote: what is
under test is which tree and which ledger the checks read across worktrees,
which only a real repository can show (the layer boundary).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

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

from _merge_fixture import (
    CHANGE, GATES_SHIM, LEDGER_REL, SCENARIO_TITLE, FakeTime, HeldLock, MergeRepo,
    combined, git,
)

_loader = importlib.machinery.SourceFileLoader("gates_shim_merge_prove_head", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class ProveHeadTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _repo(self, lane: bool, manifest_extra: str = "") -> MergeRepo:
        repo = MergeRepo(self.tmp, manifest_extra=manifest_extra)
        repo.start_change(lane=lane)
        repo.task_commit("feature.txt", "the thing\n", "add the thing")
        return repo

    def _assert_untouched(self, repo: MergeRepo, origin_before: str, head_before: tuple):
        self.assertEqual(repo.origin_main(), origin_before, "the remote target moved")
        branch, sha, _status = repo.head_state()
        self.assertEqual((branch, sha), head_before[:2], "the primary checkout moved")

    def test_an_uncommitted_live_check_row_is_committed_on_the_branch(self):
        repo = self._repo(lane=False)
        repo.prove_head()
        self.assertIn(LEDGER_REL, git(repo.primary, "status", "--porcelain"))

        r = repo.merge()

        self.assertNotIn("would be overwritten", combined(r))
        self.assertTrue(
            any(row.get("gate") == "live-check" for row in repo.rows_at(CHANGE)),
            f"the live-check row never reached the branch: {combined(r)}",
        )
        self.assertEqual(repo.files_in_commit(CHANGE), [LEDGER_REL],
                         "the trailing-row commit is not ledger-only")

    def test_a_missing_live_check_marker_refuses_at_step_1(self):
        repo = self._repo(lane=True)
        repo.prove_head(live_check=False)
        origin_before, head_before = repo.origin_main(), repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("live-check", combined(r))
        self._assert_untouched(repo, origin_before, head_before)

    def test_an_unresolved_taint_on_the_named_change_refuses_from_main(self):
        repo = self._repo(lane=True)
        repo.prove_head()
        head = git(repo.lane, "rev-parse", "HEAD")
        repo.append_lane_row({
            "ts": "2026-10-01T00:00:00+00:00", "gate": "taint", "exit": 1,
            "change": CHANGE, "task": None, "tree": git(repo.lane, "rev-parse", "HEAD^{tree}"),
            "sha": head,
        })
        self.assertEqual(git(repo.primary, "branch", "--show-current"), "main")
        origin_before, head_before = repo.origin_main(), repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("taint", combined(r))
        self._assert_untouched(repo, origin_before, head_before)
        # The merge hook's own check reads the same fixed function: asked
        # about the incoming ref from `main`, it sees the taint too.
        hook_check = repo.gates("taint", "check", "--ref", CHANGE)
        self.assertEqual(hook_check.returncode, 1, combined(hook_check))

    def test_a_declared_verify_with_no_green_run_refuses_at_step_1(self):
        repo = self._repo(lane=True, manifest_extra='  verify: "true"\n')
        repo.prove_head(verify=False)
        origin_before, head_before = repo.origin_main(), repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("verify", combined(r))
        self._assert_untouched(repo, origin_before, head_before)

    def test_a_missing_acceptance_under_a_declared_policy_refuses_at_step_1(self):
        repo = self._repo(lane=False, manifest_extra="approval:\n  acceptance: self\n")
        repo.prove_head()
        origin_before = repo.origin_main()

        r = repo.merge()

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("acceptance", combined(r))
        self.assertEqual(repo.origin_main(), origin_before)
        self.assertEqual(git(repo.primary, "branch", "--show-current"), CHANGE)

    def test_coverage_of_every_scenario_is_printed(self):
        repo = self._repo(lane=True)
        repo.prove_head()

        r = repo.merge()

        self.assertIn(f"check by hand — {SCENARIO_TITLE}", combined(r))

    def test_a_busy_merge_lock_exits_75_before_any_step(self):
        repo = self._repo(lane=True)
        repo.prove_head()
        origin_before, head_before = repo.origin_main(), repo.head_state()
        held = HeldLock(repo.primary / ".git", "merge", os.getpid())
        m = gates._mini_yaml(repo.manifest + "concurrency:\n  max-wait-seconds: 5\n")
        m["__root__"] = str(repo.primary)
        fake = FakeTime()
        err = io.StringIO()
        try:
            with mock.patch.object(gates.time, "monotonic", fake.clock), \
                    mock.patch.object(gates.time, "time", fake.wall), \
                    mock.patch.object(gates.time, "sleep", fake.sleep), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = gates.cmd_merge(m, repo.primary, argparse.Namespace(change=CHANGE))
        finally:
            held.release()

        self.assertEqual(rc, gates.PRECONDITION_EXIT_CODE)
        self.assertIn("gatedloop: lock busy", err.getvalue())
        self._assert_untouched(repo, origin_before, head_before)


if __name__ == "__main__":
    unittest.main()
