"""A rebased change at `gates merge` step 1 (`taint-preclear`, design D1/D3,
issue #132).

Rebasing gives every branch commit a tree no `ci` ever saw. Before this
change, the green full `ci` a lane ran on its new head had no taint to
clear yet, so step 1's own audit tainted the rebased commits and refused,
and a second full `ci` was needed. Now that head `ci` vouches for its
ancestors: step 1 records them `vouched` and proceeds. A head that passed
only a scoped `ci` vouches for nothing, so the rebased commits still taint.

Real git with a bare remote (`_merge_fixture`): a rebase onto a moved
target is a git-layer fact. `CLAUDECODE` is pinned by `clean_env`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, MergeRepo, combined, git

SCOPED_SURFACE = (
    "surfaces:\n"
    "  - name: docs\n"
    '    match: "docs/**"\n'
    "    gates:\n"
    '      ci: "true"\n'
)


def _rebased_lane(tmp, manifest_extra: str = "") -> tuple[MergeRepo, list[str]]:
    """Two gated task commits, then origin moves and the lane rebases onto
    it with plain git. Returns the repo and the rebased commits, oldest
    first."""
    repo = MergeRepo(Path(tmp), manifest_extra=manifest_extra)
    repo.start_change(lane=True)
    repo.task_commit("one.txt", "one\n", "task one")
    repo.task_commit("two.txt", "two\n", "task two")
    repo.advance_origin("other.txt", "another change\n", "another change lands")
    git(repo.lane, "fetch", "-q", "origin")
    git(repo.lane, "rebase", "-q", "origin/main")
    rebased = git(repo.lane, "rev-list", "--reverse", "origin/main..HEAD").split()
    assert len(rebased) == 2, rebased
    return repo, rebased


class RebasedBranchAtMergeStep1(unittest.TestCase):
    def test_a_full_head_ci_vouches_and_the_merge_goes_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, rebased = _rebased_lane(tmp)
            repo.prove_head()  # one full ci and the live-check on the new head

            r = repo.merge()

            out = combined(r)
            self.assertEqual(r.returncode, 0, out)
            self.assertNotIn("unresolved taint", out)
            rows = repo.rows_at(CHANGE)
            self.assertEqual([x for x in rows if x.get("gate") == "taint"], [], out)
            vouched = [x["sha"] for x in rows if x.get("gate") == "vouched"]
            self.assertIn(rebased[0], vouched, "the rebased first commit was vouched for")
            self.assertNotIn(rebased[-1], vouched, "the head has its own green ci row")

    def test_a_scoped_head_ci_vouches_for_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, rebased = _rebased_lane(tmp, SCOPED_SURFACE)
            # The new head is a task whose ci ran scoped to `docs`, and no
            # unscoped ci ever ran on it.
            repo.task_commit("docs/note.md", "a note\n", "task three")
            ci_rows = [x for x in repo.rows_at(CHANGE) if x.get("gate") == "ci"]
            self.assertEqual(ci_rows[-1].get("scope"), "docs", "fixture: the head ci ran scoped")
            repo.prove_head(ci=False)

            r = repo.merge()

            out = combined(r)
            self.assertEqual(r.returncode, 1, out)
            self.assertIn("unresolved taint", out)
            self.assertIn(rebased[0][:12], out)
            rows = repo.rows_at(CHANGE)
            tainted = [x["sha"] for x in rows if x.get("gate") == "taint"]
            self.assertEqual(tainted, rebased)
            self.assertEqual([x for x in rows if x.get("gate") == "vouched"], [])


if __name__ == "__main__":
    unittest.main()
