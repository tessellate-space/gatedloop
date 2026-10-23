"""End-to-end: each of the six `hooks/gate-*.sh` now resolves its repository
from the GUARDED COMMAND itself, not the harness session cwd (design D1 of
`worktree-native-loop`, task 1.2). Where `test_hook_git_cwd.py` unit-tests the
`gates hook git-cwd` subcommand directly, this file drives the real hook
scripts with a compound command carrying its own `cd <worktree>` -- the exact
shape a background agent issues -- while the hook input's `cwd` field points
at an unrelated "session" checkout, proving the hook evaluates the command's
own directory rather than the session's.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
HOOKS = REPO / "hooks"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
LIVE_CHECK_MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n  ci: "true"\n'
    'surfaces:\n'
    '  - name: all\n'
    '    match: "**"\n'
    '    live-check: "true"\n'
)

FAKE_GH_APPROVED = """\
#!/usr/bin/env bash
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  echo '{"reviews":[{"state":"APPROVED","author":{"login":"radub21"},"submittedAt":"2026-08-19T09:30:00Z"}]}'
  exit 0
fi
exit 1
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _run_hook(hook_name: str, session_cwd: Path, stdin: dict, env_overrides: dict | None = None):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", str(HOOKS / hook_name)], input=json.dumps(stdin), cwd=str(session_cwd),
        env=env, capture_output=True, text=True,
    )


def _init_repo(root: Path, branch: str = "main") -> None:
    _git(root, "init", "-b", branch)
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _change_dir(root: Path, change: str) -> Path:
    change_dir = root / "openspec" / "changes" / change
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("plan\n")
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    return change_dir


def _install_fake_gh(bindir: Path, script: str) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(script)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


class TestGateCommitCdResolution(unittest.TestCase):
    def test_cd_into_worktree_before_commit_evaluates_the_worktree(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)
            r = _run_gates(worktree, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            _init_repo(session)  # a real but unrelated repo -- no marker here

            result = _run_hook(
                "gate-commit.sh", session,
                {"tool_input": {"command": f"cd {worktree} && git commit -m x"}, "cwd": str(session)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_git_dash_c_evaluates_the_named_worktree(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)
            r = _run_gates(worktree, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            _init_repo(session)

            result = _run_hook(
                "gate-commit.sh", session,
                {"tool_input": {"command": f"git -C {worktree} commit -m x"}, "cwd": str(session)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class TestGateMergeCdResolution(unittest.TestCase):
    def test_cd_into_worktree_before_merge_evaluates_the_worktree(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _git(worktree, "init", "-b", "main")
            _git(worktree, "config", "user.email", "t@example.com")
            _git(worktree, "config", "user.name", "T")
            (worktree / ".gates.yaml").write_text(LIVE_CHECK_MANIFEST)
            _git(worktree, "add", "-A")
            _git(worktree, "commit", "-m", "init")
            r = _run_gates(worktree, "run", "live-check", "--all")
            self.assertEqual(r.returncode, 0, r.stderr)
            # gate-merge also requires an unscoped `ci` marker on the same
            # tree (scale-gate-cost D2) -- record it in the worktree only.
            r = _run_gates(worktree, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            _init_repo(session)  # no live-check or ci marker here

            result = _run_hook(
                "gate-merge.sh", session,
                {"tool_input": {"command": f"cd {worktree} && git merge feature"}, "cwd": str(session)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class TestGateScaffoldCdResolution(unittest.TestCase):
    def test_cd_into_a_plan_worktree_before_scaffold_is_allowed(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)
            _git(worktree, "checkout", "-b", "plan/foo")
            _init_repo(session)
            _git(session, "checkout", "-b", "unrelated-feature")  # disallowed here

            result = _run_hook(
                "gate-scaffold.sh", session,
                {"tool_input": {"command": f"cd {worktree} && openspec new change"}, "cwd": str(session)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_session_cwd_alone_would_have_refused(self):
        """Negative control: without the `cd`, the session's own (disallowed)
        branch is what gets checked -- proves the positive case above isn't
        just an always-allow."""
        with tempfile.TemporaryDirectory() as session:
            session = Path(session)
            _init_repo(session)
            _git(session, "checkout", "-b", "unrelated-feature")

            result = _run_hook(
                "gate-scaffold.sh", session,
                {"tool_input": {"command": "openspec new change"}, "cwd": str(session)},
            )
            self.assertNotEqual(result.returncode, 0)


class TestGateArchiveCdResolution(unittest.TestCase):
    def test_cd_into_the_repo_with_the_merged_change_is_allowed(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)
            _change_dir(worktree, "my-change")
            _git(worktree, "add", "-A")
            _git(worktree, "commit", "-m", "author plan directly on main")
            _init_repo(session)  # change not present here

            result = _run_hook(
                "gate-archive.sh", session,
                {"tool_input": {"command": f"cd {worktree} && openspec archive my-change"}, "cwd": str(session)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class TestGateImplementCdResolution(unittest.TestCase):
    def test_cd_into_the_repo_with_the_approved_change_is_allowed(self):
        with tempfile.TemporaryDirectory() as worktree, tempfile.TemporaryDirectory() as session:
            worktree, session = Path(worktree), Path(session)
            _init_repo(worktree)
            _change_dir(worktree, "my-change")
            _git(worktree, "add", "-A")
            _git(worktree, "commit", "-m", "author plan")
            with tempfile.TemporaryDirectory() as bin_tmp:
                path = _install_fake_gh(Path(bin_tmp), FAKE_GH_APPROVED)
                env = dict(os.environ)
                env["PATH"] = path
                r = subprocess.run(
                    [sys.executable, str(GATES_SHIM), "approval", "attest", "my-change", "--pr", "1"],
                    cwd=worktree, capture_output=True, text=True, env=env,
                )
                self.assertEqual(r.returncode, 0, r.stderr)
            _git(worktree, "add", "-A")
            _git(worktree, "commit", "-m", "attest approval")
            _init_repo(session)  # change unknown here

            result = _run_hook(
                "gate-implement.sh", session,
                {"tool_input": {"command": f"cd {worktree} && git checkout -b my-change"}, "cwd": str(session)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class TestGateProposeCdResolution(unittest.TestCase):
    """gate-propose.sh fires on a Write tool call -- there is no shell command
    to `cd` inside, so it keeps resolving from the hook's own `cwd` (D1's
    non-goal: no command signal exists here to derive from). This confirms
    that unchanged behavior still works after routing through `gates hook
    git-cwd` with no kind argument."""

    def test_write_tool_call_still_resolves_via_cwd_field(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as wrong:
            right, wrong = Path(right), Path(wrong)
            _init_repo(right)  # stays on main -> authoring allowed
            _init_repo(wrong)
            # authoring refused here: `foo` is in implementation on its
            # branch (hook-correctness D5)
            _git(wrong, "checkout", "-b", "foo")
            (wrong / "task.txt").write_text("task\n")
            _git(wrong, "add", "task.txt")
            _git(wrong, "commit", "-m", "task")

            file_path = str(right / "openspec" / "changes" / "foo" / "proposal.md")
            result = _run_hook(
                "gate-propose.sh", wrong,
                {"tool_input": {"file_path": file_path}, "cwd": str(right)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
