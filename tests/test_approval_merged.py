"""`gates approval attest <change> --merged <pr>` (design D1, D2, D4 of
`planner-handoff`).

Under `approval.plan: self` the act a solo maintainer performs is merging
the plan PR, and the forge records who did it and when. `--merged` writes
the approval keys from that record: the merger's login marked as a merge,
the merge time, and a sha the shim computes over the plan in the merge
commit. The regressions: the identity or time taken from local git config
or the clock instead of the forge, the sha computed from the working tree
(so an unmerged edit gets approved), a result `check-implement` does not
accept, a review-policy approval written from a merge, and any of D2's
refusals writing something anyway or not naming what was unmet.

Real git with a bare remote and the fake forge, through `_plan_fixture`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _forge_fixture import path_without
from _plan_fixture import MERGED_AT, PLAN, PLAN_DIR, PLAN_HEAD, PlanRepo, combined, git


class AttestMergedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_merged_plan_pr_under_self_writes_the_merge_as_the_approval(self):
        plan = PlanRepo(self.tmp)
        squash = plan.merge_plan_pr(42, merger="alice")

        r = plan.gates("approval", "attest", PLAN, "--merged", "42")

        self.assertEqual(r.returncode, 0, combined(r))
        keys = plan.approval()
        self.assertEqual(keys.get("by"), "alice (merged #42)")
        self.assertEqual(keys.get("at"), MERGED_AT)
        self.assertEqual(keys.get("sha"), plan.plan_sha_at(squash))
        rows = [row for row in plan.ledger_rows() if row.get("approved_by") == "alice (merged #42)"]
        self.assertEqual(len(rows), 1, plan.ledger_rows())
        self.assertEqual(rows[0].get("sha"), keys.get("sha"))

        plan.commit_on_main(f"attest approval: {PLAN} (merged #42)")
        plan.push_main()
        check = plan.gates("discipline", "check-implement", PLAN)
        self.assertEqual(check.returncode, 0, combined(check))

    def test_a_local_value_holding_a_comment_marker_reads_back_intact(self):
        # The same writer serves --local: an unquoted ` #` is a YAML comment
        # and a bare timestamp a datetime, so both must survive a YAML read.
        plan = PlanRepo(self.tmp)
        plan.merge_plan_pr(42)

        r = plan.gates("approval", "attest", PLAN, "--local", "--as", "ann (desk #3)")

        self.assertEqual(r.returncode, 0, combined(r))
        keys = plan.approval()
        self.assertEqual(keys.get("by"), "ann (desk #3)")
        self.assertIsInstance(keys.get("at"), str)
        self.assertRegex(keys.get("at"), r"^\d{4}-\d{2}-\d{2}T")

    def test_the_sha_pins_the_merge_commit_not_the_working_tree(self):
        plan = PlanRepo(self.tmp)
        squash = plan.merge_plan_pr(42)
        merged_sha = plan.plan_sha_at(squash)
        (plan.primary / PLAN_DIR / "design.md").write_text("# Design\n\nAn edit nobody merged.\n")

        r = plan.gates("approval", "attest", PLAN, "--merged", "42")

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(plan.approval().get("sha"), merged_sha)

    def test_the_review_policy_refuses_and_names_pr(self):
        plan = PlanRepo(self.tmp, policy="review")
        plan.merge_plan_pr(42)
        before = plan.state()

        r = plan.gates("approval", "attest", PLAN, "--merged", "42")

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("--pr", combined(r))
        self.assertEqual(plan.state(), before, "a refusal wrote something")

    def test_every_unmet_condition_refuses_writes_nothing_and_names_itself(self):
        def open_pr(plan):
            plan.merge_plan_pr(42)
            plan.forge.add_pr(43, PLAN_HEAD, state="OPEN")
            return "43", ("OPEN",)

        def other_base(plan):
            squash = plan.merge_plan_pr(42)
            plan.forge.add_pr(44, PLAN_HEAD, base="release", merge_commit=squash)
            return "44", ("release", "main")

        def merge_commit_off_target(plan):
            plan.merge_plan_pr(42)
            git(plan.primary, "checkout", "-q", "-b", "side")
            (plan.primary / PLAN_DIR / "design.md").write_text("# Design\n\nOnly on a side branch.\n")
            side = plan.commit_on_main("a commit main never received")
            git(plan.primary, "checkout", "-q", "main")
            plan.forge.add_pr(45, PLAN_HEAD, merge_commit=side)
            return "45", (side[:12],)

        def no_proposal_in_merge_commit(plan):
            plan.write_plan(proposal=False)
            without = plan.commit_on_main("plan without its proposal")
            plan.write_plan()
            plan.commit_on_main("the proposal, later")
            plan.push_main()
            plan.forge.add_pr(46, PLAN_HEAD, merge_commit=without)
            return "46", ("proposal.md",)

        def gh_missing(plan):
            plan.merge_plan_pr(42)
            (plan.repo.bin / "gh").unlink()
            plan.env = {"PATH": path_without(plan.tmp, keep=("git",), extra_dirs=(plan.repo.bin,))}
            return "42", ("gh",)

        def gh_unauthenticated(plan):
            plan.merge_plan_pr(42)
            plan.forge.set_unauthenticated()
            return "42", ("not authenticated",)

        for arrange in (open_pr, other_base, merge_commit_off_target,
                        no_proposal_in_merge_commit, gh_missing, gh_unauthenticated):
            with self.subTest(arrange.__name__), tempfile.TemporaryDirectory() as tmp:
                plan = PlanRepo(Path(tmp))
                plan.env = {}
                number, named = arrange(plan)
                before = plan.state()

                r = plan.gates("approval", "attest", PLAN, "--merged", number, **plan.env)

                self.assertEqual(r.returncode, 1, combined(r))
                for word in named:
                    self.assertIn(word, combined(r))
                self.assertEqual(plan.state(), before, "a refusal wrote something")
                self.assertEqual(plan.approval(), {})


if __name__ == "__main__":
    unittest.main()
