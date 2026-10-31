"""`gates hook git-cwd` — command-derived repository resolution (design D1
of `worktree-native-loop`, task 1.1).

Every gate hook used to `cd` to the hook input's `cwd` (the harness SESSION
cwd), which is wrong for a background agent whose shell resets cwd per call
and issues `cd <worktree> && git commit …` or `git -C <worktree> …`. This
subcommand resolves the directory the GUARDED COMMAND itself will run in,
in the precedence order design D1 states:

  1. `git -C <dir>` on the guarded git invocation (repeatable, composing)
  2. `GIT_DIR`/`GIT_WORK_TREE` assignments carried by the command
  3. the last `cd <dir>` before the guarded token, chained against the hook cwd
  4. the hook input's own `cwd`
  5. `CLAUDE_PROJECT_DIR`, then the process's own pwd

It reuses `hooks/_gate_match.py`'s tokenizer (one parser, two consumers).
A `cd` it cannot statically evaluate exits 3 rather than falling through to
the hook cwd (loop-hardening D8), so the hook denies instead of judging the
wrong repository.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"


def _git_cwd(kind: list[str] | None, stdin: dict, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, str(GATES_SHIM), "hook", "git-cwd"]
    if kind:
        args.append(kind)
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        args, input=json.dumps(stdin), env=env, capture_output=True, text=True,
    )


class TestNoCommandSignal(unittest.TestCase):
    """Rung 4/5: no command carries a directory of its own -- identical to
    today's single-checkout behavior."""

    def test_falls_back_to_hook_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            r = _git_cwd("git-commit", {"tool_input": {"command": "git commit -m x"}, "cwd": d})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(d).resolve())

    def test_falls_back_to_claude_project_dir_when_cwd_absent(self):
        with tempfile.TemporaryDirectory() as d:
            r = _git_cwd(
                "git-commit", {"tool_input": {"command": "git commit -m x"}},
                env_overrides={"CLAUDE_PROJECT_DIR": d},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(d).resolve())

    def test_falls_back_to_pwd_when_neither_set(self):
        with tempfile.TemporaryDirectory() as d:
            args = [sys.executable, str(GATES_SHIM), "hook", "git-cwd", "git-commit"]
            env = dict(os.environ)
            env.pop("CLAUDE_PROJECT_DIR", None)
            r = subprocess.run(
                args, input=json.dumps({"tool_input": {"command": "git commit -m x"}}),
                cwd=d, env=env, capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(d).resolve())

    def test_write_tool_input_with_no_command_falls_back(self):
        """gate-propose.sh fires on a Write tool call -- no `command` field
        at all -- so git-cwd must still degrade cleanly to the hook cwd."""
        with tempfile.TemporaryDirectory() as d:
            r = _git_cwd(None, {"tool_input": {"file_path": "/x/proposal.md"}, "cwd": d})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(d).resolve())


class TestCdChain(unittest.TestCase):
    """Rung 3: the last `cd <dir>` before the guarded token, chained
    left-to-right against the hook cwd."""

    def test_cd_before_commit_wins_over_session_cwd(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": f"cd {worktree} && git commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())

    def test_quoted_directory_with_spaces(self):
        with tempfile.TemporaryDirectory() as base:
            worktree = Path(base) / "a worktree"
            worktree.mkdir()
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": f'cd "{worktree}" && git commit -m "msg && more"'}, "cwd": base},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), worktree.resolve())

    def test_relative_cd_chains_off_hook_cwd(self):
        with tempfile.TemporaryDirectory() as session:
            sub = Path(session) / "wt"
            sub.mkdir()
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": "cd wt && git commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), sub.resolve())

    def test_second_cd_chains_off_first(self):
        with tempfile.TemporaryDirectory() as session:
            a = Path(session) / "a"
            b = a / "b"
            b.mkdir(parents=True)
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": "cd a && cd b && git commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), b.resolve())

    def test_unevaluable_cd_target_exits_3_naming_it(self):
        """loop-hardening D8: falling through to the hook cwd judged the
        session's checkout instead of the one the command runs in. An
        unresolvable `cd` now exits 3 with the reason, printing no directory."""
        with tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": "cd $SOME_VAR && git commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertEqual(r.stdout.strip(), "")
            self.assertIn("cd $SOME_VAR", r.stderr)
            self.assertIn("git -C <dir>", r.stderr)

    def test_cd_after_the_guarded_token_is_not_considered(self):
        """Only a `cd` BEFORE the guarded token matters -- one issued after
        commits in the compound command has already fired must not move it."""
        with tempfile.TemporaryDirectory() as session, tempfile.TemporaryDirectory() as other:
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": f"git commit -m x && cd {other}"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(session).resolve())


class TestGitDashC(unittest.TestCase):
    """Rung 1: `git -C <dir>` on the guarded invocation itself, regardless
    of the hook input's cwd."""

    def test_dash_c_wins_over_hook_cwd(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": f"git -C {worktree} commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())

    def test_repeated_dash_c_composes_left_to_right(self):
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as session:
            sub = Path(base) / "sub"
            sub.mkdir()
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": f"git -C {base} -C sub commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), sub.resolve())

    def test_dash_c_on_git_merge(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "git-merge",
                {"tool_input": {"command": f"git -C {worktree} merge feature"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())


class TestGitDirWorkTree(unittest.TestCase):
    """Rung 2: `GIT_DIR`/`GIT_WORK_TREE` assignments carried by the command."""

    def test_git_work_tree_assignment(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": f"GIT_WORK_TREE={worktree} git commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())

    def test_git_dir_assignment_uses_parent_of_dot_git(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            gitdir = Path(worktree) / ".git"
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": f"GIT_DIR={gitdir} git commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())

    def test_env_wrapper_assignment(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": f"env GIT_WORK_TREE={worktree} git commit -m x"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())


class TestOtherKinds(unittest.TestCase):
    def test_implement_branch_cd(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "implement-branch",
                {"tool_input": {"command": f"cd {worktree} && git checkout -b my-change"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())

    def test_openspec_archive_cd(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "openspec-archive",
                {"tool_input": {"command": f"cd {worktree} && openspec archive my-change"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())

    def test_openspec_scaffold_cd(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "openspec-scaffold",
                {"tool_input": {"command": f"cd {worktree} && openspec new change"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(worktree).resolve())

    def test_unmatched_kind_falls_back_to_hook_cwd(self):
        """A compound command that never contains the given kind's
        invocation at all (e.g. `git status`) has no guarded token to
        anchor on -- falls straight through to the hook cwd."""
        with tempfile.TemporaryDirectory() as session:
            r = _git_cwd(
                "git-commit",
                {"tool_input": {"command": "git status"}, "cwd": session},
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(session).resolve())


if __name__ == "__main__":
    unittest.main()
