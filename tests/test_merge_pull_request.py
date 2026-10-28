"""`gates merge <change>` under `integration.mode: pull-request` (design D2 of
`merge-pull-request`).

In pull-request mode the merge is the forge's: `gates merge` proves the head
as in local mode, pushes the branch, publishes the head's markers as
statuses, opens or updates the PR with the acceptance brief as its body, and
enables squash auto-merge only when nothing the declared process names stands
in the way. The regressions: auto-merge enabled although `requireApproval`
is true or a declared acceptance is missing (a merge no human allowed), an
unproven head pushed or turned into a PR, statuses missing from the head so
required checks never pass, a second run opening a duplicate PR, and the
command integrating locally behind the forge's back.

Real git with a bare remote (the push is a remote-side fact, and the target
must stay where it was), and the fake forge from `_forge_fixture` for
everything `gh` does.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _forge_fixture import Forge, NO_CI
from _merge_fixture import CHANGE, PROPOSAL_TITLE, SCENARIO_TITLE, MergeRepo, combined, git


def _manifest(require_approval: bool, acceptance: str | None = None) -> str:
    text = (
        "integration:\n  mode: pull-request\n"
        f"  requireApproval: {'true' if require_approval else 'false'}\n"
    )
    if acceptance:
        text += f"approval:\n  acceptance: {acceptance}\n"
    return text


class PullRequestMergeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _ready(self, tmp: Path, manifest_extra: str, live_check: bool = True,
               accept: bool = False) -> tuple:
        repo = MergeRepo(tmp, manifest_extra=manifest_extra)
        forge = Forge(tmp / "forge.json").install(repo.bin)
        repo.start_change(lane=True)
        repo.task_commit("feature.txt", "the thing\n", "add the thing")
        repo.prove_head(live_check=live_check)
        if accept:
            r = repo.gates("acceptance", "attest", CHANGE, "--local", cwd=repo.lane)
            self.assertEqual(r.returncode, 0, combined(r))
        return repo, forge

    def _remote_branch(self, repo: MergeRepo) -> str | None:
        out = git(repo.bare, "rev-parse", "--verify", "--quiet", f"refs/heads/{CHANGE}", check=False)
        return out or None

    def test_auto_merge_only_when_the_declared_process_allows_it(self):
        cases = (
            ("no approval, no acceptance policy", _manifest(False), False, True),
            ("approval required", _manifest(True), False, False),
            ("acceptance declared, not accepted", _manifest(False, "self"), False, False),
            ("acceptance declared and accepted", _manifest(False, "self"), True, True),
        )
        for name, extra, accept, auto in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                repo, forge = self._ready(Path(tmp), extra, accept=accept)
                origin_main = repo.origin_main()

                r = repo.merge(**NO_CI)

                self.assertEqual(r.returncode, 0, combined(r))
                head = git(repo.primary, "rev-parse", f"refs/heads/{CHANGE}")
                self.assertEqual(self._remote_branch(repo), head, "the branch head was not pushed")
                for gate in ("live-check", "ci"):
                    status = forge.latest_status(head, f"gatedloop/{gate}")
                    self.assertTrue(status and status["state"] == "success",
                                    f"no gatedloop/{gate} success on the pushed head: {status}")
                prs = forge.prs()
                self.assertEqual(len(prs), 1, prs)
                pr = prs[0]
                self.assertEqual((pr["head"], pr["base"]), (CHANGE, "main"))
                self.assertEqual(pr["title"], f"{CHANGE}: {PROPOSAL_TITLE}")
                self.assertIn(SCENARIO_TITLE, pr["body"])
                self.assertEqual(pr["auto_merge"], "squash" if auto else None)
                if not auto:
                    self.assertIn(pr["url"], r.stdout)
                self.assertEqual(repo.origin_main(), origin_main,
                                 "the target moved: pull-request mode integrated locally")

    def test_step_4_under_self_names_the_forge_merge_as_the_acceptance(self):
        # merged-acceptance D4: with no acceptance recorded, `self` is
        # satisfied by the owner's merge in the forge, which `gates
        # record-merged` records; only `review` is genuinely unsatisfied.
        # Auto-merge stays off in both.
        for policy, names_record_merged in (("self", True), ("review", False)):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as tmp:
                repo, forge = self._ready(Path(tmp), _manifest(False, policy))

                r = repo.merge(**NO_CI)

                self.assertEqual(r.returncode, 0, combined(r))
                self.assertIsNone(forge.prs()[0]["auto_merge"])
                self.assertIn(forge.prs()[0]["url"], r.stdout)
                if names_record_merged:
                    self.assertIn("gates record-merged", r.stdout)
                    self.assertNotIn("is not satisfied", r.stdout)
                else:
                    self.assertIn("is not satisfied", r.stdout)
                    self.assertNotIn("record-merged", r.stdout)

    def test_a_second_run_updates_the_open_pull_request(self):
        repo, forge = self._ready(self.tmp, _manifest(True))
        first = repo.merge(**NO_CI)
        self.assertEqual(first.returncode, 0, combined(first))

        r = repo.merge(**NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(len(forge.prs()), 1, forge.prs())
        self.assertIn(SCENARIO_TITLE, forge.prs()[0]["body"])

    def test_an_unproven_head_pushes_nothing_and_opens_no_pull_request(self):
        repo, forge = self._ready(self.tmp, _manifest(False), live_check=False)

        r = repo.merge(**NO_CI)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("live-check", combined(r))
        self.assertIsNone(self._remote_branch(repo))
        self.assertEqual(forge.prs(), [])
        head = git(repo.primary, "rev-parse", f"refs/heads/{CHANGE}")
        self.assertEqual(forge.statuses(head), [])


if __name__ == "__main__":
    unittest.main()
