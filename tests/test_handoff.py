"""`gates handoff <change> [--json]` (design D5 of `planner-handoff`).

A planner session tells the one orchestrator that a plan is ready. The
message is only a doorbell, so the command that prints it must refuse
unless the plan is approved on the merge target and unchanged since, using
the same check `check-implement` runs. The regressions: a payload printed
for a plan that is only on a planner's branch or was edited after approval,
a payload missing a field the receiver acts on (above all the command it
re-runs to verify), the plain form dropping fields, and the command writing
or committing anything.

Real git with a bare remote and the fake forge, through `_plan_fixture`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _plan_fixture import MERGED_AT, PLAN, PLAN_DIR, PlanRepo, combined, git, payload


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _approved_on_main(self, epic=None) -> PlanRepo:
        plan = PlanRepo(self.tmp)
        plan.merge_plan_pr(42, merger="alice", epic=epic)
        r = plan.gates("approval", "attest", PLAN, "--merged", "42")
        self.assertEqual(r.returncode, 0, combined(r))
        plan.commit_on_main(f"attest approval: {PLAN} (merged #42)")
        plan.push_main()
        return plan

    def test_an_approved_plan_on_the_target_prints_the_full_payload_and_writes_nothing(self):
        plan = self._approved_on_main(epic="add-thing")
        keys = plan.approval("HEAD")
        before = plan.state()

        r = plan.gates("handoff", PLAN, "--json")

        self.assertEqual(r.returncode, 0, combined(r))
        got = payload(r)
        self.assertEqual(got["handoff"], 1)
        self.assertEqual(got["change"], PLAN)
        self.assertEqual(got["schema"], "spec-driven")
        self.assertTrue(got["target"].endswith("main"), got["target"])
        self.assertEqual(got["target_head"], plan.repo.origin_main())
        self.assertEqual(got["approval"], {"by": "alice (merged #42)", "at": MERGED_AT, "sha": keys["sha"]})
        self.assertEqual(got["epic"], "add-thing")
        self.assertEqual(got["tasks"], {"done": 1, "total": 3})
        self.assertEqual(got["verify"], f"gates approval check {PLAN}")
        self.assertEqual(plan.state(), before, "handoff wrote something")
        self.assertEqual(git(plan.primary, "rev-parse", "HEAD"), plan.repo.origin_main())

    def test_a_plan_with_no_epic_hands_off_a_null_epic(self):
        plan = self._approved_on_main()

        r = plan.gates("handoff", PLAN, "--json")

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIsNone(payload(r)["epic"])

    def test_the_plain_form_prints_the_same_fields_as_lines(self):
        plan = self._approved_on_main()

        r = plan.gates("handoff", PLAN)

        self.assertEqual(r.returncode, 0, combined(r))
        with self.assertRaises(ValueError):
            json.loads(r.stdout)
        lines = r.stdout.splitlines()
        self.assertIn(f"change: {PLAN}", lines)
        self.assertIn(f"target_head: {plan.repo.origin_main()}", lines)
        self.assertIn(f"verify: gates approval check {PLAN}", lines)
        for field in ("schema", "target", "approval", "epic", "tasks"):
            self.assertTrue(any(line.startswith(f"{field}:") for line in lines), (field, lines))

    def test_a_plan_only_on_a_planners_branch_is_refused_without_a_payload(self):
        plan = PlanRepo(self.tmp)
        git(plan.primary, "checkout", "-q", "-b", f"plan/{PLAN}")
        plan.write_plan(approval={
            "x-gatedloop-approved-by": "alice",
            "x-gatedloop-approved-at": MERGED_AT,
            "x-gatedloop-approved-sha": "0" * 64,
        })
        plan.commit_on_main(f"propose: {PLAN}")
        before = plan.state()

        r = plan.gates("handoff", PLAN, "--json")

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertEqual(r.stdout.strip(), "", "a refused handoff printed a payload")
        self.assertIn("not present", r.stderr)
        self.assertEqual(plan.state(), before)

    def test_a_plan_edited_after_approval_is_refused_without_a_payload(self):
        plan = self._approved_on_main()
        (plan.primary / PLAN_DIR / "design.md").write_text("# Design\n\nChanged after approval.\n")
        plan.commit_on_main("edit the design after approval")
        plan.push_main()

        r = plan.gates("handoff", PLAN, "--json")

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertEqual(r.stdout.strip(), "", "a refused handoff printed a payload")
        self.assertIn("does not match", r.stderr)


if __name__ == "__main__":
    unittest.main()
