"""`gates merge` proves the plan approval before step 1's evidence
(loop-hardening D1, #101).

The regression: a change whose plan was amended after approval merged
anyway. Every ledger row carried the old approval, live-check, ci and
confirm all passed, and nothing compared the recorded `approved_sha` with
the plan being merged. Two places can drift, and step 1 now checks both: the
plan on the merge target (amended there and never re-attested), and the plan
on the branch head (edited by the branch itself). An untagged `tasks.md` is
outside the sha, so ticking or adding a task never needs re-approval.

Real git with a bare remote (the target is a remote-side fact) and, for
pull-request mode, the fake forge -- a status published before the refusal
is a forge-side fact.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _forge_fixture import NO_CI, PR_MODE, Forge
from _merge_fixture import CHANGE, MergeRepo, combined, git

PLAN = f"openspec/changes/{CHANGE}"


class MergeProvesThePlanApproval(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _ready(self, manifest_extra: str = "") -> MergeRepo:
        repo = MergeRepo(self.tmp, manifest_extra=manifest_extra)
        repo.start_change(lane=True)
        repo.task_commit("feature.txt", "the thing\n", "add the thing")
        return repo

    def _amend_target_plan(self, repo: MergeRepo) -> None:
        """Another integrator lands a design change on the target without
        re-attesting it, and the primary fetches it."""
        repo.advance_origin(f"{PLAN}/design.md", "# Design\n\nD1. Do it differently.\n",
                            "amend add-thing's design")
        git(repo.primary, "fetch", "-q", "origin")

    def test_a_plan_amended_on_the_target_without_re_attest_halts_step_1(self):
        repo = self._ready()
        repo.prove_head()
        self._amend_target_plan(repo)
        origin_main = repo.origin_main()

        r = repo.merge()

        self.assertEqual(r.returncode, 1, combined(r))
        out = combined(r)
        self.assertIn("step 1", out)
        self.assertIn("approved_sha does not match", out)
        self.assertIn(f"gates approval attest {CHANGE}", out)
        self.assertEqual(repo.origin_main(), origin_main, "the target moved")
        self.assertEqual(repo.pushes(), 0)

    def test_a_branch_editing_its_own_specs_halts_step_1(self):
        repo = self._ready()
        repo.task_commit(f"{PLAN}/specs/cap/spec.md",
                         "## ADDED Requirements\n\n### Requirement: Thing\n\n"
                         "The system SHALL work, and also fly.\n",
                         "widen the requirement")
        repo.prove_head()
        origin_main = repo.origin_main()

        r = repo.merge()

        self.assertEqual(r.returncode, 1, combined(r))
        out = combined(r)
        self.assertIn("step 1", out)
        self.assertIn("differs from the plan approved", out)
        self.assertEqual(repo.origin_main(), origin_main, "the target moved")
        self.assertEqual(repo.pushes(), 0)

    def test_an_untagged_tasks_md_change_needs_no_re_approval(self):
        repo = self._ready()
        repo.task_commit(f"{PLAN}/tasks.md",
                         "## 1. Do it\n\n- [x] 1.1 Add the thing\n- [x] 1.2 And its sibling\n",
                         "add and tick a task")
        repo.prove_head()

        r = repo.merge()

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertNotIn("not the approved one", combined(r))

    def test_pull_request_mode_halts_before_any_status_is_published(self):
        repo = self._ready(manifest_extra=PR_MODE)
        forge = Forge(self.tmp / "forge.json").install(repo.bin)
        repo.prove_head()
        self._amend_target_plan(repo)
        head = git(repo.primary, "rev-parse", f"refs/heads/{CHANGE}")

        r = repo.merge(**NO_CI)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("approved_sha does not match", combined(r))
        self.assertEqual(forge.statuses(head), [], "a status was published for an unapproved plan")
        self.assertEqual(forge.prs(), [])
        self.assertIsNone(
            git(repo.bare, "rev-parse", "--verify", "--quiet", f"refs/heads/{CHANGE}", check=False) or None,
            "the branch was pushed",
        )


if __name__ == "__main__":
    unittest.main()
