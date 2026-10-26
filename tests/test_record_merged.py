"""`gates record-merged <sha>` (design D3 of `merge-pull-request`).

A merge in the forge's UI writes no ledger row, so before this command every
PR-merged change looked in progress forever. `record-merged` resolves the
change a squash commit came from through its PR's head branch, records the
merge row against that sha, archives the change, and commits both locally in
ONE commit -- ledger- and planning-grade, so it needs no `ci` marker (this
checkout never ran `ci`, which is the point: a CI job calling this after a
push has no marker either). It never pushes.

The regressions: a merge row naming the wrong sha or missing, the archive
split from the row or not made, a push nobody asked for, the follow-up PR
that lands this very commit triggering a second archive of something else,
an ordinary PR or a direct push treated as a change, a re-run recording a
second merge, and a sha the checkout does not contain being recorded anyway.

Real git with a bare remote (whether anything was pushed is a remote-side
fact), the fake forge from `_forge_fixture`, and `_merge_fixture`'s fake
`openspec archive`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import tempfile
import unittest
from pathlib import Path

from _forge_fixture import Forge, NO_CI, PR_MODE
from _merge_fixture import CHANGE, LEDGER_REL, PROPOSAL_TITLE, MergeRepo, combined, git


class RecordMergedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _merged_in_forge(self, tmp: Path) -> tuple:
        """A change carried through the loop in a lane, then squash-merged
        onto `main` the way the forge does it, as PR #7 from head `add-thing`.
        The primary is on `main` at that squash, as a CI checkout would be."""
        repo = MergeRepo(tmp, manifest_extra=PR_MODE)
        forge = Forge(tmp / "forge.json").install(repo.bin)
        repo.start_change(lane=True)
        repo.task_commit("feature.txt", "the thing\n", "add the thing")
        repo.prove_head()
        git(repo.lane, "add", "-A")
        git(repo.lane, "commit", "-q", "-m", "record trailing ledger rows")
        git(repo.primary, "merge", "--squash", CHANGE)
        git(repo.primary, "commit", "-q", "-m", f"{CHANGE}: {PROPOSAL_TITLE} (#7)")
        squash = git(repo.primary, "rev-parse", "HEAD")
        git(repo.primary, "push", "-q", "origin", "HEAD:main")
        repo.push_log.write_text("")
        forge.add_merged_pull(7, CHANGE, squash)
        return repo, forge, squash

    def _merge_rows(self, repo: MergeRepo, ref: str = "HEAD") -> list:
        return [r for r in repo.rows_at(ref) if r.get("gate") == "merge"]

    def test_a_change_pull_request_is_recorded_and_archived_in_one_local_commit(self):
        repo, _forge, squash = self._merged_in_forge(self.tmp)

        r = repo.gates("record-merged", squash, **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        head = git(repo.primary, "rev-parse", "HEAD")
        self.assertEqual(git(repo.primary, "rev-parse", "HEAD~1"), squash, "not exactly one commit")
        self.assertEqual(git(repo.primary, "log", "-1", "--format=%s"), f"archive change: {CHANGE}")
        files = repo.files_in_commit(head)
        self.assertIn(LEDGER_REL, files)
        self.assertIn("openspec/specs/cap/spec.md", files)
        self.assertTrue(any(p.startswith("openspec/changes/archive/") and f"-{CHANGE}/" in p for p in files), files)
        tree = git(repo.primary, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
        self.assertFalse(any(p.startswith(f"openspec/changes/{CHANGE}/") for p in tree))
        self.assertEqual([row.get("sha") for row in self._merge_rows(repo)], [squash])
        self.assertEqual(git(repo.primary, "status", "--porcelain"), "")
        self.assertEqual(repo.pushes(), 0, "record-merged pushed")
        self.assertEqual(repo.origin_main(), squash)
        outcomes = repo.gates("stats", "--outcomes", "--change", CHANGE, "--json")
        self.assertEqual(outcomes.returncode, 0, combined(outcomes))
        self.assertEqual(json.loads(outcomes.stdout)["changes"][0]["terminal"], "merged")

    def test_a_commit_from_no_active_change_records_nothing(self):
        cases = (
            ("a direct push, no pull request", None),
            ("an ordinary pull request", "fix-typo"),
            ("the follow-up pull request that lands a record", "gatedloop/record-merged-1a2b3c4"),
        )
        for name, head_ref in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                # The change is still active on main, so only the head branch
                # can tell these commits apart from a change's merge.
                repo, forge, _squash = self._merged_in_forge(Path(tmp))
                (repo.primary / "notes.txt").write_text("unrelated\n")
                git(repo.primary, "add", "notes.txt")
                git(repo.primary, "commit", "-q", "-m", "unrelated")
                sha = git(repo.primary, "rev-parse", "HEAD")
                if head_ref is not None:
                    forge.add_merged_pull(8, head_ref, sha)

                r = repo.gates("record-merged", sha, **NO_CI)

                self.assertEqual(r.returncode, 0, combined(r))
                self.assertTrue(r.stdout.strip(), "a skip must say why")
                self.assertEqual(git(repo.primary, "rev-parse", "HEAD"), sha)
                self.assertEqual(git(repo.primary, "status", "--porcelain"), "")
                self.assertEqual(self._merge_rows(repo), [])

    def test_a_second_run_does_nothing(self):
        repo, _forge, squash = self._merged_in_forge(self.tmp)
        first = repo.gates("record-merged", squash, **NO_CI)
        self.assertEqual(first.returncode, 0, combined(first))
        after_first = git(repo.primary, "rev-parse", "HEAD")

        r = repo.gates("record-merged", squash, **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(git(repo.primary, "rev-parse", "HEAD"), after_first)
        self.assertEqual(len(self._merge_rows(repo)), 1)

    def test_a_sha_the_checkout_does_not_contain_is_refused(self):
        repo, forge, _squash = self._merged_in_forge(self.tmp)
        elsewhere = git(repo.lane, "rev-parse", "HEAD")
        forge.add_merged_pull(9, CHANGE, elsewhere)
        before = git(repo.primary, "rev-parse", "HEAD")

        r = repo.gates("record-merged", elsewhere, **NO_CI)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertEqual(git(repo.primary, "rev-parse", "HEAD"), before)
        self.assertEqual(self._merge_rows(repo), [])


if __name__ == "__main__":
    unittest.main()
