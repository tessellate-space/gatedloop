"""The commit hook names a shared branch only when that is the verdict
(loop-hardening D7, #109).

The regression: `hooks/gate-commit.sh` printed "this branch is shared with
another worktree" after ANY failure of `gates discipline check-worktree`,
so a crash on a conflicted `.gates.yaml` was reported as a worktree problem.
The hook now passes the shim's own output through -- the holders when the
branch is shared, the one-line parse error when the manifest is broken --
and adds only where the commit was denied.

Real repositories and the real hook, driven with a PreToolUse payload.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_worktree_shared_branch import COMMIT_HOOK, _env, _git, _shared_branch

CONFLICTED = """\
gatesVersion: 1
gates:
<<<<<<< HEAD
  ci: "true"
=======
  ci: "false"
>>>>>>> other-branch
"""


def _commit_hook(root: Path) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_input": {"command": "git commit -m 'work'"}, "cwd": str(root)})
    return subprocess.run(["bash", str(COMMIT_HOOK)], input=payload, cwd=root,
                          env=_env(root), capture_output=True, text=True, timeout=120)


class TheCommitHookNamesTheRealCause(unittest.TestCase):
    def test_a_conflicted_manifest_denies_without_mentioning_another_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            (root / ".gates.yaml").write_text(CONFLICTED)
            (root / "work.txt").write_text("task\n")
            _git(root, "add", "work.txt")

            r = _commit_hook(root)

            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("merge-conflict markers", r.stderr)
            self.assertNotIn("another worktree", r.stderr)
            self.assertNotIn("shared", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("commit denied", r.stderr)

    def test_a_branch_in_two_worktrees_still_names_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary, lane = Path(tmp) / "primary", Path(tmp) / "lane"
            primary.mkdir()
            _shared_branch(primary, lane)

            r = _commit_hook(primary)

            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("my-change", r.stderr)
            self.assertIn(str(primary.resolve()), r.stderr)
            self.assertIn(str(lane.resolve()), r.stderr)


if __name__ == "__main__":
    unittest.main()
