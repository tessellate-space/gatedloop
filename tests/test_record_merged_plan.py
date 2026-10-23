"""`gates record-merged <sha>` on a merged plan PR (design D3 of
`planner-handoff`).

Before this change a squash whose PR head was `plan/<change>` named no
active change and was skipped, so under `approval.plan: self` someone still
had to run `attest --local` and push one more commit after every plan
merge. Now the record job attests the plan from the merge and commits the
keys in its one local commit. The regressions: no commit, a second commit,
anything but the approval in it, a push, an approval written over an
existing one, a review-policy approval written from a merge, and a `plan/`
head naming no change doing anything at all.

The change-PR path is unchanged and stays covered by `test_record_merged`.

Real git with a bare remote and the fake forge, through `_plan_fixture`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _plan_fixture import PLAN, PLAN_LEDGER, PLAN_YAML, PlanRepo, combined, git


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

    def test_a_plan_pr_it_must_not_attest_is_skipped_with_the_reason(self):
        approved = {
            "x-gatedloop-approved-by": "bob",
            "x-gatedloop-approved-at": "2026-10-19T08:00:00Z",
            "x-gatedloop-approved-sha": "0" * 64,
        }
        cases = (
            ("already approved", "self", approved, "already approved"),
            ("the review policy", "review", None, "review"),
        )
        for name, policy, approval, reason in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                plan = PlanRepo(Path(tmp), policy=policy)
                squash = plan.merge_plan_pr(42, approval=approval)
                before = plan.state()

                r = plan.gates("record-merged", squash)

                self.assertEqual(r.returncode, 0, combined(r))
                self.assertIn(reason, r.stdout)
                self.assertEqual(plan.state(), before)

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
