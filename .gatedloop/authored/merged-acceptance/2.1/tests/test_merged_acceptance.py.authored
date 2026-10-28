"""The owner's forge merge recorded as the acceptance (change
`merged-acceptance`, design D1, D2).

Under `approval.acceptance: self` in pull-request mode, a solo owner cannot
approve their own PR, so `--pr` never applies, and `--local` would have to be
run by hand before the merge. `gates acceptance attest <change> --merged <pr>`
reads the forge's record of the merged implementation PR instead: the
merger's login marked `(merged #<pr>)`, the merge time, and the
ledger-normalized tree of the PR's merge commit -- the tree the change's
merge row records, so `gates stats --outcomes` joins the two.

The regressions: the identity or time taken from git config or the clock
instead of the forge; the tree pinned from the change branch's head or the
checkout's HEAD instead of the merge commit (the outcomes join then misses);
a review-policy or undeclared-policy acceptance written from a merge; a PR
that is open, merged elsewhere, from another branch, or whose merge commit is
off the target writing a row anyway or not naming what was unmet; and a
re-run writing a second row for the same tree.

`gates record-merged <sha>` (design D3) writes that same row under `self`,
before the merge row and in the same local commit, so a solo pull-request
project ends a change with a complete ledger. Its regressions: no accept row
(the change reads `merged`, never `accepted`), a second accept row beside
one the owner already recorded, an accept row under the review policy or
none, and a merge committed without its acceptance when the forge refuses.

Real git with a bare remote (the target is a remote ref), the fake forge from
`_forge_fixture`, and `_merge_fixture`'s repository.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _forge_fixture import NO_CI, PR_MODE, Forge
from _merge_fixture import (
    CHANGE, LEDGER_REL, PROPOSAL_TITLE, MergeRepo, combined, git, rows_from_text,
)

MERGED_AT = "2026-10-20T09:30:00Z"


def merged_change(tmp: Path, policy: str | None = "self", moved_target: bool = False,
                  accept_locally: bool = False, pr_record: bool = True,
                  number: int = 42) -> tuple:
    """Change `add-thing` carried through the loop in a lane, then
    squash-merged onto `main` the way the forge does it, as PR #`number` from
    head `add-thing`, merged by `alice`. The primary is on `main` at that
    squash, as a CI checkout would be.

    `moved_target`: another commit landed on `main` first, so the merge
    commit's tree is not the branch head's. `accept_locally`: the owner ran
    `--local` on the branch before the merge. `pr_record`: whether the forge
    can answer `gh pr view <number>`."""
    # A manifest declaring `approval` must name the plan policy as well.
    extra = ("approval:\n  plan: self\n" + (f"  acceptance: {policy}\n" if policy else "")
             + PR_MODE)
    repo = MergeRepo(tmp, manifest_extra=extra)
    forge = Forge(tmp / "forge.json").install(repo.bin)
    repo.start_change(lane=True)
    repo.task_commit("feature.txt", "the thing\n", "add the thing")
    repo.prove_head()
    if accept_locally:
        r = repo.gates("acceptance", "attest", CHANGE, "--local", cwd=repo.lane, **NO_CI)
        if r.returncode != 0:
            raise AssertionError(f"fixture --local acceptance failed: {combined(r)}")
    git(repo.lane, "add", "-A")
    git(repo.lane, "commit", "-q", "-m", "record trailing ledger rows")
    if moved_target:
        repo.advance_origin("other.txt", "another change\n", "another change lands first")
        git(repo.primary, "pull", "-q", "--ff-only", "origin", "main")
    git(repo.primary, "merge", "--squash", CHANGE)
    git(repo.primary, "commit", "-q", "-m", f"{CHANGE}: {PROPOSAL_TITLE} (#{number})")
    squash = git(repo.primary, "rev-parse", "HEAD")
    git(repo.primary, "push", "-q", "origin", "HEAD:main")
    repo.push_log.write_text("")
    if pr_record:
        forge.add_pr(number, CHANGE, base="main", merged_by="alice", merged_at=MERGED_AT,
                     merge_commit=squash)
    forge.add_merged_pull(number, CHANGE, squash)
    return repo, forge, squash


def ledger_rows(repo: MergeRepo) -> list:
    """The change's ledger as it stands in the primary's working tree."""
    p = repo.primary / LEDGER_REL
    return rows_from_text(p.read_text()) if p.exists() else []


def acceptance_rows(rows: list) -> list:
    return [r for r in rows if r.get("gate") == "acceptance"]


def state(repo: MergeRepo) -> tuple:
    """Everything a refusal must leave as it was."""
    p = repo.primary / LEDGER_REL
    return (
        git(repo.primary, "rev-parse", "HEAD"),
        git(repo.primary, "status", "--porcelain", "--untracked-files=all"),
        p.read_text() if p.exists() else "",
    )


def outcome(repo: MergeRepo) -> str:
    r = repo.gates("stats", "--outcomes", "--change", CHANGE, "--json", **NO_CI)
    if r.returncode != 0:
        raise AssertionError(f"stats --outcomes failed: {combined(r)}")
    return json.loads(r.stdout)["changes"][0]["terminal"]


class AttestMergedAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_merged_pr_under_self_accepts_the_merge_commits_tree(self):
        # The target moved before the merge, and the checkout moved after it,
        # so the branch head, the merge commit and HEAD hold three different
        # trees: only the merge commit's joins the merge row.
        repo, _forge, squash = merged_change(self.tmp, moved_target=True)
        (repo.primary / "notes.txt").write_text("after the merge\n")
        git(repo.primary, "add", "notes.txt")
        git(repo.primary, "commit", "-q", "-m", "a later commit on main")
        git(repo.primary, "push", "-q", "origin", "HEAD:main")

        r = repo.gates("acceptance", "attest", CHANGE, "--merged", "42", **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        accepts = acceptance_rows(ledger_rows(repo))
        self.assertEqual(len(accepts), 1, accepts)
        row = accepts[0]
        self.assertEqual(row.get("verdict"), "accept")
        self.assertEqual(row.get("accepted_by"), "alice (merged #42)")
        self.assertEqual(row.get("ts"), MERGED_AT)

        recorded = repo.gates("ledger", "record-merge", CHANGE, "--sha", squash, **NO_CI)
        self.assertEqual(recorded.returncode, 0, combined(recorded))
        merges = [x for x in ledger_rows(repo) if x.get("gate") == "merge"]
        self.assertEqual(row.get("tree"), merges[-1].get("tree"),
                         "the accept row does not pin the merge commit's tree")
        self.assertEqual(outcome(repo), "accepted")

    def test_a_second_run_for_the_same_tree_writes_nothing(self):
        repo, _forge, _squash = merged_change(self.tmp)
        first = repo.gates("acceptance", "attest", CHANGE, "--merged", "42", **NO_CI)
        self.assertEqual(first.returncode, 0, combined(first))
        before = state(repo)

        r = repo.gates("acceptance", "attest", CHANGE, "--merged", "42", **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(state(repo), before, "a re-run wrote something")
        self.assertEqual(len(acceptance_rows(ledger_rows(repo))), 1)

    def test_every_unmet_condition_refuses_writes_nothing_and_names_itself(self):
        def review_policy(tmp):
            repo, _forge, _squash = merged_change(tmp, policy="review")
            return repo, "42", ("--pr",)

        def no_policy(tmp):
            repo, _forge, _squash = merged_change(tmp, policy=None)
            return repo, "42", ("approval.acceptance",)

        def open_pr(tmp):
            repo, forge, _squash = merged_change(tmp)
            forge.add_pr(43, CHANGE, state="OPEN")
            return repo, "43", ("OPEN",)

        def other_base(tmp):
            repo, forge, squash = merged_change(tmp)
            forge.add_pr(44, CHANGE, base="release", merge_commit=squash)
            return repo, "44", ("release", "main")

        def other_head_branch(tmp):
            repo, forge, squash = merged_change(tmp)
            forge.add_pr(45, "other-thing", merge_commit=squash)
            return repo, "45", ("other-thing",)

        def merge_commit_off_target(tmp):
            repo, forge, _squash = merged_change(tmp)
            git(repo.primary, "checkout", "-q", "-b", "side")
            (repo.primary / "side.txt").write_text("only on a side branch\n")
            git(repo.primary, "add", "side.txt")
            git(repo.primary, "commit", "-q", "-m", "a commit main never received")
            side = git(repo.primary, "rev-parse", "HEAD")
            git(repo.primary, "checkout", "-q", "main")
            forge.add_pr(46, CHANGE, merge_commit=side)
            return repo, "46", (side[:12],)

        def gh_unauthenticated(tmp):
            repo, forge, _squash = merged_change(tmp)
            forge.set_unauthenticated()
            return repo, "42", ("not authenticated",)

        for arrange in (review_policy, no_policy, open_pr, other_base, other_head_branch,
                        merge_commit_off_target, gh_unauthenticated):
            with self.subTest(arrange.__name__), tempfile.TemporaryDirectory() as tmp:
                repo, number, named = arrange(Path(tmp))
                before = state(repo)

                r = repo.gates("acceptance", "attest", CHANGE, "--merged", number, **NO_CI)

                self.assertEqual(r.returncode, 1, combined(r))
                for word in named:
                    self.assertIn(word, combined(r))
                self.assertEqual(state(repo), before, "a refusal wrote something")
                self.assertEqual(acceptance_rows(ledger_rows(repo)), [])



class RecordMergedAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_under_self_the_merge_is_recorded_as_the_acceptance_in_the_same_commit(self):
        repo, _forge, squash = merged_change(self.tmp)

        r = repo.gates("record-merged", squash, **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(git(repo.primary, "rev-parse", "HEAD~1"), squash, "not exactly one commit")
        self.assertEqual(git(repo.primary, "status", "--porcelain"), "")
        rows = repo.rows_at("HEAD")
        accepts = acceptance_rows(rows)
        self.assertEqual(len(accepts), 1, accepts)
        self.assertEqual(accepts[0].get("accepted_by"), "alice (merged #42)")
        merges = [x for x in rows if x.get("gate") == "merge"]
        self.assertEqual([x.get("sha") for x in merges], [squash])
        self.assertLess(rows.index(accepts[0]), rows.index(merges[0]),
                        "the accept row does not precede the merge row")
        self.assertEqual(accepts[0].get("tree"), merges[0].get("tree"))
        self.assertEqual(outcome(repo), "accepted")

    def test_an_acceptance_already_recorded_for_the_tree_is_not_written_again(self):
        repo, _forge, squash = merged_change(self.tmp, accept_locally=True)

        r = repo.gates("record-merged", squash, **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        accepts = acceptance_rows(repo.rows_at("HEAD"))
        self.assertEqual(len(accepts), 1, accepts)
        self.assertNotIn("(merged #42)", accepts[0].get("accepted_by") or "")
        self.assertEqual(outcome(repo), "accepted")

    def test_without_the_self_policy_no_acceptance_is_written(self):
        for policy in ("review", None):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as tmp:
                repo, _forge, squash = merged_change(Path(tmp), policy=policy)

                r = repo.gates("record-merged", squash, **NO_CI)

                self.assertEqual(r.returncode, 0, combined(r))
                rows = repo.rows_at("HEAD")
                self.assertEqual(acceptance_rows(rows), [])
                self.assertEqual([x.get("sha") for x in rows if x.get("gate") == "merge"], [squash])
                self.assertEqual(outcome(repo), "merged")

    def test_a_forge_refusal_commits_nothing(self):
        repo, _forge, squash = merged_change(self.tmp, pr_record=False)

        r = repo.gates("record-merged", squash, **NO_CI)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertEqual(git(repo.primary, "rev-parse", "HEAD"), squash)
        self.assertEqual(git(repo.primary, "status", "--porcelain"), "")
        self.assertEqual([x for x in ledger_rows(repo) if x.get("gate") == "merge"], [])
        self.assertEqual(acceptance_rows(ledger_rows(repo)), [])


if __name__ == "__main__":
    unittest.main()
