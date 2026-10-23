"""`gates merge` crash recovery (design Risks of `merge-step`).

A crash between the local commits and the push leaves the primary detached
on unpushed commits. Nothing was published; but a plain rerun would record
the detached HEAD as "where the primary was" and leave it detached after a
successful merge. The previous position is written under
`.git/gatedloop/merge-state`, and a rerun that finds a detached HEAD carrying
this change's unpublished merge row restores that position before starting.

The crash is real: the `confirm` gate's body kills the `gates merge`
process outright (its parent) on the first run, after steps 3 and 4 have
committed locally -- only a real process and repository show what a crash
leaves behind.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, MergeRepo, combined, git

# Unset CRASH_MERGE: `test -z` with no operand is true. Set: kill the shell's
# parent, which is the `gates merge` process running the confirm gate.
CRASHING_CONFIRM = '  confirm: "test -z $CRASH_MERGE || kill -9 $PPID"\n'


class CrashRecoveryTest(unittest.TestCase):
    def test_a_rerun_after_a_crash_restores_the_recorded_head_and_merges_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = MergeRepo(Path(tmp), manifest_extra=CRASHING_CONFIRM)
            repo.start_change(lane=True)
            repo.task_commit("feature.txt", "the thing\n", "add the thing")
            repo.prove_head()
            before = repo.origin_main()

            crashed = repo.merge(CRASH_MERGE="1")

            self.assertNotEqual(crashed.returncode, 0, combined(crashed))
            self.assertEqual(repo.origin_main(), before, "a crashed merge published something")
            self.assertEqual(git(repo.primary, "branch", "--show-current"), "",
                             "the crash did not leave the primary detached, so this tests nothing")

            r = repo.merge()

            self.assertEqual(r.returncode, 0, combined(r))
            subjects = [s for _sha, s, _b in repo.origin_log(before)]
            self.assertEqual(len([s for s in subjects if s.startswith(f"{CHANGE}: ")]), 1, subjects)
            branch, sha, status = repo.head_state()
            self.assertEqual((branch, sha, status), ("main", repo.origin_main(), ""))


if __name__ == "__main__":
    unittest.main()
