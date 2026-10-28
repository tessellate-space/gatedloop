"""`gates record-merged <sha>` on a merged plan PR (design D3 of
`planner-handoff`).

Before this change a squash whose PR head was `plan/<change>` named no
active change and was skipped, so under `approval.plan: self` someone still
had to run `attest --local` and push one more commit after every plan
merge. Now the record job attests the plan from the merge and commits the
keys in its one local commit. The regressions: no commit, a second commit,
anything but the approval in it, a push, an approval written over an
approval that still matches the merged plan, a review-policy approval
written from a merge, and a `plan/` head naming no change doing anything at
all. Change `merged-acceptance` (design D5) adds one more: a merged plan
*amendment* skipped because the change already names an approver, leaving a
stale `approved_sha` that `check-implement` refuses until someone re-attests
by hand.

The change-PR path is unchanged and stays covered by `test_record_merged`.

Real git with a bare remote and the fake forge, through `_plan_fixture`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _plan_fixture import (
    MERGED_AT, PLAN, PLAN_DIR, PLAN_HEAD, PLAN_LEDGER, PLAN_YAML, PlanRepo, combined, git,
)


class RecordMergedPlanTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_self_policy_plan_pr_is_attested_in_one_local_commit(self):
        plan = PlanRepo(self.tmp)
        squash = plan.merge_plan_pr(42, merger="alice")

        r = plan.gates("record-merged", squash)

        self.assertEqual(r.returncode, 0, combined(r))
        head = git(plan.primary, "rev-parse", "HEAD")
        self.assertEqual(git(plan.primary, "rev-parse", "HEAD~1"), squash, "not exactly one commit")
        self.assertEqual(git(plan.primary, "log", "-1", "--format=%s"),
                         f"attest approval: {PLAN} (merged #42)")
        files = set(plan.repo.files_in_commit(head))
        self.assertIn(PLAN_YAML, files)
        self.assertLessEqual(files, {PLAN_YAML, PLAN_LEDGER})
        keys = plan.approval("HEAD")
        self.assertEqual(keys.get("by"), "alice (merged #42)")
        self.assertEqual(keys.get("sha"), plan.plan_sha_at(squash))
        self.assertEqual(git(plan.primary, "status", "--porcelain"), "")
        self.assertEqual(plan.repo.pushes(), 0, "record-merged pushed")
        self.assertEqual(plan.repo.origin_main(), squash)

    def test_the_review_policy_is_skipped_with_the_reason(self):
        plan = PlanRepo(self.tmp, policy="review")
        squash = plan.merge_plan_pr(42)
        before = plan.state()

        r = plan.gates("record-merged", squash)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIn("review", r.stdout)
        self.assertEqual(plan.state(), before)

    def test_an_approval_that_still_matches_the_merged_plan_is_skipped(self):
        plan = PlanRepo(self.tmp)
        squash = plan.merge_plan_pr(42, merger="alice")
        first = plan.gates("record-merged", squash)
        self.assertEqual(first.returncode, 0, combined(first))
        before = plan.state()

        r = plan.gates("record-merged", squash)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIn("already approved", r.stdout)
        self.assertIn("alice (merged #42)", r.stdout)
        self.assertEqual(plan.state(), before)

    def test_a_merged_plan_amendment_is_re_attested_from_its_merge(self):
        plan = PlanRepo(self.tmp)
        first = plan.gates("record-merged", plan.merge_plan_pr(42, merger="alice"))
        self.assertEqual(first.returncode, 0, combined(first))
        plan.push_main()
        (plan.primary / PLAN_DIR / "design.md").write_text("# Design\n\n## Decisions\n\nD1. Do it better.\n")
        amended = plan.commit_on_main(f"amend: {PLAN} (#76)")
        plan.push_main()
        plan.forge.add_pr(76, PLAN_HEAD, base="main", merged_by="bob", merged_at=MERGED_AT,
                          merge_commit=amended)
        plan.forge.add_merged_pull(76, PLAN_HEAD, amended)
        stale = plan.gates("discipline", "check-implement", PLAN)
        self.assertNotEqual(stale.returncode, 0, "the amendment left the approval matching")

        r = plan.gates("record-merged", amended)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(git(plan.primary, "rev-parse", "HEAD~1"), amended, "not exactly one commit")
        self.assertEqual(git(plan.primary, "log", "-1", "--format=%s"),
                         f"attest approval: {PLAN} (merged #76)")
        keys = plan.approval("HEAD")
        self.assertEqual(keys.get("by"), "bob (merged #76)")
        self.assertEqual(keys.get("sha"), plan.plan_sha_at(amended))
        self.assertEqual(git(plan.primary, "status", "--porcelain"), "")
        self.assertEqual(plan.repo.pushes(), 0, "record-merged pushed")
        plan.push_main()
        check = plan.gates("discipline", "check-implement", PLAN)
        self.assertEqual(check.returncode, 0, combined(check))

    def test_a_plan_head_naming_no_active_change_records_nothing(self):
        plan = PlanRepo(self.tmp)
        (plan.primary / "notes.txt").write_text("unrelated\n")
        sha = plan.commit_on_main("unrelated")
        plan.push_main()
        plan.forge.add_merged_pull(50, "plan/nothing-here", sha)
        before = plan.state()

        r = plan.gates("record-merged", sha)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIn("nothing-here", r.stdout)
        self.assertEqual(plan.state(), before)
        self.assertEqual(plan.repo.pushes(), 0)


if __name__ == "__main__":
    unittest.main()
