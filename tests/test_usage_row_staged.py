"""A usage row recorded by a commit hook lands in that commit (openspec
change `usage-row-staged`, issue #140).

The git-layer `pre-commit` template records a `no-transcript` usage row on
every commit it allows (token-ledger D7). Recorded without `--stage`, the row
never reached the commit it describes, so every commit left the change's
ledger dirty and `gates merge` step 2 could not detach onto the target. Here
the shipped hook is installed into a real repo and fired by real commits, in
the three forms git builds its commit index differently for (design D1):
`git commit`, `git commit -a` and `git commit <paths>`.

The pathspec form updates the real index with the listed paths before the
hook runs, so the hook's own `git add` reaches the commit but not
`.git/index` (design Context). There the guarantee is that the working tree
matches the new head; the index entry is git's, and merge step 1 aligns it
for its own pathspec commit (D3, `test_merge_usage_row_staged`).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import env_without_gates  # noqa: E402
from _usage_fixture import (  # noqa: E402
    at, change_repo, git, run_gates, seed, task_start,
)

LEDGER_REL = ".gatedloop/runs/my-change.jsonl"


def _agent_env():
    return env_without_gates(CLAUDECODE="1")


class TheGitLayerStagesItsRow(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = change_repo(self._tmp.name)
        self.env = _agent_env()
        (self.root / "work.txt").write_text("before\n")
        seed(self.root, task_start(at(0), "1.1"))
        r = run_gates(self.root, "hook", "install", "--commit-only", env_=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # The baseline commit is not under test: the hook is bypassed so the
        # ledger and the adoption record start tracked and clean.
        git(self.root, "add", "-A", env_=self.env)
        git(self.root, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "baseline",
            env_=self.env)

    def tearDown(self):
        self._tmp.cleanup()

    def _green_ci_on_work(self):
        """Edit and stage the work, then earn a green `ci` on that tree."""
        (self.root / "work.txt").write_text("after\n")
        git(self.root, "add", "work.txt", env_=self.env)
        r = run_gates(self.root, "run", "ci", "--task", "1.1", env_=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def _commit(self, *args):
        r = subprocess.run(["git", "commit", "-q", "-m", "work", *args], cwd=self.root,
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def _head_usage_sources(self):
        text = git(self.root, "show", f"HEAD:{LEDGER_REL}", env_=self.env).stdout
        rows = [json.loads(x) for x in text.splitlines() if x.strip()]
        return [r.get("source") for r in rows if r.get("gate") == "usage"]

    def _status(self):
        return git(self.root, "status", "--porcelain", "--", LEDGER_REL, env_=self.env).stdout

    def _worktree_vs_head(self):
        return git(self.root, "diff", "HEAD", "--", LEDGER_REL, env_=self.env).stdout

    def test_a_plain_commit_holds_its_row_and_leaves_the_ledger_clean(self):
        self._green_ci_on_work()
        self._commit()
        self.assertEqual(self._head_usage_sources(), ["no-transcript"])
        self.assertEqual(self._status(), "")

    def test_a_commit_all_holds_its_row_and_leaves_the_ledger_clean(self):
        self._green_ci_on_work()
        # `-a` builds the commit from a temporary index of every tracked
        # change: unstage the work so `-a` is what picks it up.
        git(self.root, "reset", "-q", "--", "work.txt", env_=self.env)
        self._commit("-a")
        self.assertEqual(self._head_usage_sources(), ["no-transcript"])
        self.assertEqual(self._status(), "")
        self.assertEqual(git(self.root, "show", "HEAD:work.txt", env_=self.env).stdout, "after\n")

    def test_a_pathspec_commit_holds_its_row_and_the_tree_matches_the_head(self):
        self._green_ci_on_work()
        self._commit("--", "work.txt")
        self.assertEqual(self._head_usage_sources(), ["no-transcript"])
        self.assertEqual(self._worktree_vs_head(), "",
                         "the hook's row is in the working tree but not the commit")

    def test_the_next_commit_after_a_pathspec_commit_keeps_every_row(self):
        # The pathspec form leaves `.git/index` behind the head for the
        # ledger; the next commit's hook re-stages the ledger from the
        # working tree, so no row is reverted and that commit leaves it clean.
        self._green_ci_on_work()
        self._commit("--", "work.txt")
        (self.root / "work.txt").write_text("again\n")
        git(self.root, "add", "work.txt", env_=self.env)
        r = run_gates(self.root, "run", "ci", "--task", "1.1", env_=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self._commit()
        self.assertEqual(self._head_usage_sources(), ["no-transcript", "no-transcript"])
        self.assertEqual(self._status(), "")


if __name__ == "__main__":
    unittest.main()
