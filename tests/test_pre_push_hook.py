"""The git `pre-push` template, end to end through `git push` to a local
bare remote (change `git-layer-enforcement`, design D3).

The hook reads git's `<local ref> <local sha> <remote ref> <remote sha>`
lines and gates only an update of the merge target, inside an agent
session. The regressions caught here: a raw merge of the target pushed from
an agent session (the gap the change closes), `gates merge`'s own push
refused by the hook, a feature-branch push gated, and a human's push gated.

Real `git push` with the template installed as the primary checkout's
pre-push hook: git feeding the hook its stdin and refusing the push on its
exit code is the boundary under test, and nothing short of a real push to a
real remote exercises it.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from _hook_fixture import PUSH_TEMPLATE, default_hook, write_hook
from _merge_fixture import CHANGE, REPO, MergeRepo, combined, git


class PrePushHookTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = MergeRepo(Path(self._tmp.name))
        write_hook(default_hook(self.repo.primary, "pre-push"), PUSH_TEMPLATE.read_text())

    def push(self, *refspec, **env) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "push", "-q", "origin", *refspec], cwd=self.repo.primary,
            capture_output=True, text=True, timeout=300,
            env=self.repo.env(CLAUDE_PLUGIN_ROOT=str(REPO), **env),
        )

    def raw_merge(self) -> str:
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        git(self.repo.primary, "checkout", "-q", "main")
        git(self.repo.primary, "merge", "-q", "--no-ff", "-m", "raw merge", CHANGE)
        return git(self.repo.primary, "rev-parse", "HEAD")

    def test_an_agent_pushing_a_raw_merge_of_the_target_is_refused(self):
        # Scenario "A raw merge pushed without proof", at the git layer.
        before = self.repo.origin_main()
        self.raw_merge()

        r = self.push("main")

        self.assertNotEqual(r.returncode, 0, combined(r))
        self.assertIn("gates merge", combined(r))
        self.assertEqual(self.repo.origin_main(), before, "the target moved")

    def test_a_human_push_of_the_same_merge_is_untouched(self):
        # Scenario "A human push".
        sha = self.raw_merge()

        r = self.push("main", CLAUDECODE=None)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(self.repo.origin_main(), sha)

    def test_an_agent_pushing_a_change_branch_is_untouched(self):
        # Scenario "A feature branch push".
        self.repo.start_change(lane=False)
        sha = self.repo.task_commit("feature.txt", "the thing\n", "add the thing")

        r = self.push(CHANGE)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(git(self.repo.bare, "rev-parse", f"refs/heads/{CHANGE}"), sha)

    def test_gates_merge_pushes_through_the_hook(self):
        # Scenario "The shim's own merge push": the hook finds the merge row
        # for what `gates merge` pushes and lets it through.
        before = self.repo.origin_main()
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        self.repo.prove_head()

        r = self.repo.merge(CLAUDE_PLUGIN_ROOT=str(REPO))

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertNotEqual(self.repo.origin_main(), before)


if __name__ == "__main__":
    unittest.main()
