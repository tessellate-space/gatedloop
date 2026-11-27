"""`gates merge` with the shipped git pre-commit hook installed in the lane
(openspec change `usage-row-staged`, design D3, issue #140).

Step 1 commits the branch's trailing ledger rows as a pathspec commit
(`git commit -- <ledger>`). That commit fires the git hook, which records a
`no-transcript` usage row and stages it -- into git's temporary index, so
the row reaches the commit but `.git/index` keeps the ledger's old entry.
Step 1 must leave the ledger clean anyway, or step 2 cannot detach onto the
target ("Your local changes ... would be overwritten by checkout").

Real git in temporary repositories with a bare remote, and the real hook
installed by `gates hook install`: the failure is git's own index handling,
which only a real repository shows.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _hook_fixture import gate_free_path
from _merge_fixture import CHANGE, LEDGER_REL, MergeRepo, combined, git, rows_from_text

STEP1_SUBJECT = f"record trailing ledger rows: {CHANGE}"


class _HookedMerge(unittest.TestCase):
    """A change carried through the loop with the git hook installed, its
    head proven and the proving runs' rows left for step 1. `LANE` puts the
    branch in a lane worktree (True) or in the primary checkout (False)."""

    LANE = True

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # The hook must resolve this checkout's shim through the path `gates
        # hook install` records, never a plugin root or a `gates` on PATH
        # from the host running the suite.
        patch = mock.patch.dict(os.environ, {"PATH": gate_free_path()})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)

        self.repo = MergeRepo(self.tmp)
        self.lane = self.repo.start_change(lane=self.LANE)
        r = self.repo.gates("hook", "install", "--commit-only", cwd=self.lane)
        self.assertEqual(r.returncode, 0, combined(r))
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        self.repo.prove_head()

    def tearDown(self):
        self._tmp.cleanup()


class MergeWithTheGitHookInstalled(_HookedMerge):
    """The branch in a lane worktree: step 2 detaches in the primary, so a
    dirty lane ledger never blocks it, but step 1 must still leave it clean."""

    LANE = True

    def _step1_commit(self) -> str:
        sha = git(self.lane, "log", "--format=%H", f"--grep={STEP1_SUBJECT}", "--fixed-strings",
                  "-n", "1", CHANGE)
        self.assertTrue(sha, "step 1 committed no trailing ledger rows")
        return sha

    def test_the_hook_leaves_trailing_rows_for_step_1_to_commit(self):
        # The fixture's state: the task commit held its own usage row, and
        # the proving runs' rows are what is left for step 1.
        self.assertIn(LEDGER_REL, git(self.lane, "status", "--porcelain"))
        head_rows = rows_from_text(git(self.lane, "show", f"HEAD:{LEDGER_REL}"))
        self.assertIn("no-transcript", [r.get("source") for r in head_rows])

    def test_the_merge_gets_past_step_2s_detach(self):
        r = self.repo.merge()

        out = combined(r)
        self.assertNotIn("would be overwritten", out)
        self.assertNotIn("stopped at step 2", out)
        self.assertNotIn("stopped at step 1", out)
        self.assertEqual(r.returncode, 0, out)

    def test_step_1s_commit_holds_the_hooks_row_and_the_ledger_is_clean(self):
        r = self.repo.merge()

        sha = self._step1_commit()
        self.assertEqual(self.repo.files_in_commit(sha, cwd=self.lane), [LEDGER_REL])
        before = rows_from_text(git(self.lane, "show", f"{sha}~1:{LEDGER_REL}"))
        after = rows_from_text(git(self.lane, "show", f"{sha}:{LEDGER_REL}"))
        added = after[len(before):]
        self.assertIn("no-transcript", [row.get("source") for row in added
                                        if row.get("gate") == "usage"],
                      f"the hook's usage row is not in step 1's commit: {combined(r)}")
        self.assertEqual(git(self.lane, "status", "--porcelain", "--", LEDGER_REL), "",
                         combined(r))


class MergeInTheCheckoutHoldingTheBranch(MergeWithTheGitHookInstalled):
    """The branch checked out where the merge runs (#140 as reported): step
    2 detaches in that same checkout, so a dirty ledger stops it."""

    LANE = False


class AHookThatLeavesRowsUnstagedHaltsAtStep1(_HookedMerge):
    """A copy of the earlier template appends its row without staging it:
    no reset can clean that, so step 1 halts and names the ledger instead of
    step 2 failing on checkout (design D3)."""

    LANE = False

    def test_the_merge_halts_at_step_1_naming_the_ledger(self):
        hook = Path(git(self.lane, "rev-parse", "--git-common-dir"))
        if not hook.is_absolute():
            hook = self.lane / hook
        hook = hook / "hooks" / "pre-commit"
        body = hook.read_text()
        self.assertIn("usage record --stage", body)
        hook.write_text(body.replace("usage record --stage", "usage record"))
        origin_before = self.repo.origin_main()

        r = self.repo.merge()

        out = combined(r)
        self.assertEqual(r.returncode, 1, out)
        self.assertIn("stopped at step 1", out)
        self.assertIn(LEDGER_REL, out)
        self.assertIn("gates hook install", out)
        self.assertNotIn("would be overwritten", out)
        self.assertEqual(self.repo.origin_main(), origin_before)


if __name__ == "__main__":
    unittest.main()
