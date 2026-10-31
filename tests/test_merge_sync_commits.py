"""A sync into a change branch may not create its own merge commit
(loop-hardening D3, #108).

The regression: a lane brought main in with a plain `git merge origin/main`.
The merge hook passed it as not-integrating, and git runs no pre-commit hook
for the merge commit that follows, so that commit was one no gate saw. The
reflog audit tainted the change, and the taint only surfaced at `gates
merge` step 1. Now the hook passes a sync only when it creates no commit:

- `--no-commit`, `--squash`, `--ff-only` and `--abort` never commit;
- a bare merge passes when it is a fast-forward or already up to date;
- `--no-ff`, `--continue` and any other bare merge commit, and are denied
  with the route: `git merge --no-commit <ref>`, then `gates run ci`, then
  `git commit`;
- a merge whose ref could not be parsed is denied unless a flag says it
  never commits.

Real git: a bare remote and a clone (the merge target is `origin/main`),
and the real `hooks/gate-merge.sh` driven with a PreToolUse payload. No gate
marker exists anywhere, so a pass is the not-integrating sync path.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from test_merge_switch_scope import _clone_with_a_change, _git, _run_hook

ROUTE = "git merge --no-commit origin/main"


class ACommittingSyncIsDenied(unittest.TestCase):
    """`my-change` has a commit of its own and `origin/main` moved on, so a
    bare merge would create a merge commit."""

    def _diverged(self, tmp: str) -> Path:
        root = _clone_with_a_change(Path(tmp))
        _git(root, "checkout", "-q", "my-change")
        return root

    def test_a_bare_merge_of_main_is_denied_with_the_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._diverged(tmp)
            r = _run_hook(root, "git merge origin/main")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("creates a commit no gate saw", r.stderr)
            self.assertIn(ROUTE, r.stderr)
            self.assertIn("gates run ci", r.stderr)
            self.assertIn("my-change", r.stderr)

    def test_no_ff_and_continue_are_denied(self):
        for command in ("git merge --no-ff origin/main", "git merge --continue"):
            with self.subTest(command), tempfile.TemporaryDirectory() as tmp:
                root = self._diverged(tmp)
                r = _run_hook(root, command)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn("creates a commit no gate saw", r.stderr)

    def test_an_unparsable_ref_without_a_non_committing_flag_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._diverged(tmp)
            r = _run_hook(root, "git merge origin/main main")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("creates a commit no gate saw", r.stderr)

    def test_a_switch_then_bare_merge_is_denied_naming_the_landing_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            r = _run_hook(root, "git checkout my-change && git merge origin/main")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("change branch 'my-change'", r.stderr)


class ASyncThatCreatesNoCommitPasses(unittest.TestCase):
    def test_non_committing_flags_pass(self):
        for command in ("git merge --no-commit origin/main", "git merge --squash origin/main",
                        "git merge --ff-only origin/main", "git merge --abort",
                        "git merge --no-commit origin/main main"):
            with self.subTest(command), tempfile.TemporaryDirectory() as tmp:
                root = _clone_with_a_change(Path(tmp))
                _git(root, "checkout", "-q", "my-change")
                r = _run_hook(root, command)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_pure_fast_forward_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            base = _git(root, "rev-parse", "origin/main~1")
            _git(root, "checkout", "-q", "-b", "fresh-change", base)
            r = _run_hook(root, "git merge origin/main")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_already_up_to_date_merge_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            base = _git(root, "rev-parse", "origin/main~1")
            _git(root, "checkout", "-q", "my-change")
            r = _run_hook(root, f"git merge {base}")
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
