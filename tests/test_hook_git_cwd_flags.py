"""`gates hook git-cwd` resolves git's `--git-dir` / `--work-tree` options
like their `GIT_DIR` / `GIT_WORK_TREE` forms (design D4 of
`cross-worktree-evidence`, task 3.1).

`git --git-dir=<x>/.git --work-tree=<x> commit` used to resolve the session
directory, so the commit gate judged a repository the command never touched.
The rules, as D4 states them: the work tree wins; a `--git-dir` ending in
`.git` resolves to its parent; a `-C` anywhere on the command applies first
and the relative paths resolve against it; a `--git-dir` with neither falls
through to the next signal (a preceding `cd`, then the hook cwd).

Pure resolution, no git invoked: the directories need only exist.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from _lane_fixture import resolve_git_cwd


class TestGitDirAndWorkTreeFlags(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name).resolve()
        self.session = tmp / "session"
        self.repo = tmp / "repo"
        self.other = tmp / "other"
        self.base = tmp / "base"
        for d in (self.session, self.repo, self.other, self.base, self.base / "sub"):
            d.mkdir(parents=True)

    def assertResolves(self, command: str, expected: Path, kind: str = "git-commit"):
        got = resolve_git_cwd(kind, command, self.session)
        self.assertEqual(got.resolve(), expected.resolve(), command)

    def test_each_spelling_names_the_repository(self):
        # Fails if a flag form falls back to the session directory, or if the
        # separate-value spelling is read as a different signal.
        r = self.repo
        cases = (
            f"git --git-dir={r}/.git --work-tree={r} commit -m m",
            f"git --git-dir {r}/.git --work-tree {r} commit -m m",
            f"git --work-tree={r} commit -m m",
            f"git --work-tree {r} commit -m m",
        )
        for command in cases:
            with self.subTest(command=command):
                self.assertResolves(command, r)

    def test_the_work_tree_wins_over_the_git_dir(self):
        # Fails if `--git-dir`'s parent is taken while a work tree is named.
        for command in (
            f"git --git-dir={self.other}/.git --work-tree={self.repo} commit -m m",
            f"git --work-tree {self.repo} --git-dir {self.other}/.git commit -m m",
        ):
            with self.subTest(command=command):
                self.assertResolves(command, self.repo)

    def test_a_dot_git_suffixed_git_dir_resolves_to_its_parent(self):
        # Fails if the git dir itself (not its work tree) is taken as the
        # repository, or the flag is ignored.
        for command in (
            f"git --git-dir={self.repo}/.git commit -m m",
            f"git --git-dir {self.repo}/.git merge --squash add-thing",
        ):
            kind = "git-merge" if " merge " in command else "git-commit"
            with self.subTest(command=command):
                self.assertResolves(command, self.repo, kind=kind)

    def test_a_bare_git_dir_falls_through_to_the_next_signal(self):
        # Fails if a git dir with no `.git` name and no work tree is guessed
        # at instead of falling through, as the `GIT_DIR=` form does.
        self.assertResolves(f"git --git-dir={self.other}/store commit -m m", self.session)
        self.assertResolves(
            f"cd {self.repo} && git --git-dir {self.other}/store commit -m m", self.repo,
        )

    def test_dash_c_applies_first_and_relative_paths_resolve_against_it(self):
        # Fails if `-C` and the flags do not compose as git composes them.
        cases = (
            (f"git -C {self.base} --work-tree=sub commit -m m", self.base / "sub"),
            (f"git --work-tree=sub -C {self.base} commit -m m", self.base / "sub"),
            (f"git -C {self.base} --git-dir=sub/.git commit -m m", self.base / "sub"),
            (f"git -C {self.base} --work-tree={self.repo} commit -m m", self.repo),
        )
        for command, expected in cases:
            with self.subTest(command=command):
                self.assertResolves(command, expected)


if __name__ == "__main__":
    unittest.main()
