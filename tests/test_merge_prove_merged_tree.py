"""`gates merge` steps 3 and 4: prove the merged tree, then record it
(design D2 of `merge-step`).

An unscoped `ci` runs on the staged squash -- the tree neither the branch's
ci nor the target's ever saw. Red resets and restores, exit 3, nothing on
the target. Green commits the squash as "<change>: <proposal title>" with the
task subjects as its body, then `record-merge` names that commit's real sha
in a ledger-only commit on top. The regressions: a red merged tree still
committed or published, the primary left detached on a red, and a merge row
naming HEAD-at-record time (the ledger commit) instead of the squash.

Real git with a bare remote: the merged tree only exists once git has
squashed two diverged histories.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, LEDGER_REL, PROPOSAL_TITLE, MergeRepo, combined, git

# Green on either side alone, red once both files exist: only the merged
# tree fails.
RED_WHEN_MERGED = 'gatesVersion: 1\ngates:\n  ci: "test ! -f a.txt -o ! -f b.txt"\n'


class ProveMergedTreeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_red_merged_tree_is_not_committed_and_the_checkout_is_restored(self):
        repo = MergeRepo(self.tmp, manifest=RED_WHEN_MERGED)
        repo.start_change(lane=False)
        repo.task_commit("b.txt", "b\n", "add b")
        repo.prove_head()
        repo.advance_origin("a.txt", "a\n", "add a")
        git(repo.lane, "add", "-A")
        git(repo.lane, "commit", "-q", "-m", "trailing rows")
        origin_before = repo.origin_main()
        local_main_before = git(repo.primary, "rev-parse", "refs/heads/main")
        head_before = repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, 3, combined(r))
        self.assertEqual(repo.origin_main(), origin_before)
        self.assertEqual(git(repo.primary, "rev-parse", "refs/heads/main"), local_main_before)
        self.assertEqual(repo.head_state(), head_before)

    def test_a_green_squash_is_committed_and_the_merge_row_names_its_sha(self):
        repo = MergeRepo(self.tmp)
        repo.start_change(lane=True)
        repo.task_commit("one.txt", "1\n", "add the first part")
        repo.task_commit("two.txt", "2\n", "add the second part")
        repo.prove_head()

        r = repo.merge()

        out = git(repo.primary, "log", "--all", "--format=%H%x1f%s%x1f%b%x1e")
        squash = None
        for rec in out.split("\x1e"):
            parts = rec.strip("\n").split("\x1f")
            if len(parts) >= 3 and parts[1].startswith(f"{CHANGE}: "):
                squash = parts
                break
        self.assertIsNotNone(squash, f"no squash commit was made: {combined(r)}")
        sha, subject, body = squash[0].strip(), squash[1], squash[2]
        self.assertIn(PROPOSAL_TITLE, subject)
        self.assertIn("add the first part", body)
        self.assertIn("add the second part", body)

        children = [
            line.split()[0]
            for line in git(repo.primary, "rev-list", "--all", "--parents").splitlines()
            if len(line.split()) == 2 and line.split()[1] == sha
        ]
        self.assertEqual(len(children), 1, "expected exactly one commit on top of the squash")
        record = children[0]
        self.assertEqual(repo.files_in_commit(record), [LEDGER_REL])
        merge_rows = [row for row in repo.rows_at(record) if row.get("gate") == "merge"]
        self.assertEqual(len(merge_rows), 1)
        self.assertEqual(merge_rows[0].get("sha"), sha)


if __name__ == "__main__":
    unittest.main()
