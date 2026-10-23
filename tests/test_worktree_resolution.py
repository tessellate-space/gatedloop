"""Worktree-aware repo resolution for the six gate hooks (design D1, tasks
1.1-1.4 of `unblock-parallel-planning`).

Every hook today does `cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"`, ignoring the
`cwd` field Claude Code sends in every hook input. That means a hook fired
for a command running in a secondary git worktree still measures the
*session root's* repo -- wrong index, wrong (empty) per-worktree marker
store. The fix: parse `cwd` from the hook input and `cd` there first,
falling back to `CLAUDE_PROJECT_DIR` only when `cwd` is absent, and to `pwd`
only when neither is set.

These tests drive each hook script directly -- stdin JSON, env, and the
test process's own cwd -- and observe the resolution through the shim
boundary the hook actually calls into (a marker compare or a discipline
check). The marker-clearing hook is gone (`hook-correctness` D3), and its
cases with it. Stdlib only, per `zero-dep-shim`.

Run with:  python3 -m unittest discover -s tests
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
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path, branch: str = "main") -> None:
    _git(root, "init", "-b", branch)
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _repo_with_green_ci_marker(root: Path) -> None:
    """A repo whose staged tree (nothing further staged since `init`) has a
    matching green `ci` marker -- `gate-commit.sh` should allow a commit
    here."""
    _init_repo(root)
    r = _run_gates(root, "run", "ci")
    assert r.returncode == 0, r.stderr


def _repo_with_green_live_check_marker(root: Path) -> None:
    """A repo whose HEAD tree has a matching green `live-check` marker AND a
    fresh, unscoped `ci` marker (scale-gate-cost D2: the merge also requires
    full `ci` on the head, alongside `live-check`) -- `gate-merge.sh` should
    allow a merge here."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(LIVE_CHECK_MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    r = _run_gates(root, "run", "ci")
    assert r.returncode == 0, r.stderr
    r = _run_gates(root, "run", "live-check", "--all")
    assert r.returncode == 0, r.stderr


def _install_fake_gh(bindir: Path, script: str) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(script)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


def _change_dir(root: Path, change: str) -> Path:
    change_dir = root / "openspec" / "changes" / change
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("plan\n")
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    return change_dir


def _repo_with_approved_change(root: Path, change: str = "my-change") -> None:
    """A repo where `change` is merged to `main` (committed directly there)
    and carries a real, attested approval -- `check-implement` allows
    cutting `change`'s branch here."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _change_dir(root, change)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author plan")
    with tempfile.TemporaryDirectory() as bin_tmp:
        path = _install_fake_gh(Path(bin_tmp), FAKE_GH_APPROVED)
        env = dict(os.environ)
        env["PATH"] = path
        r = subprocess.run(
            [sys.executable, str(GATES_SHIM), "approval", "attest", change, "--pr", "1"],
            cwd=root, capture_output=True, text=True, env=env,
        )
        assert r.returncode == 0, r.stderr
    # `approval attest` only writes the file -- `check-implement` reads
    # `.openspec.yaml` from the merge-target REF (`git show <ref>:...`), so
    # the attested content must actually be committed to be visible there.
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "attest approval")


def _repo_with_unapproved_change(root: Path, change: str = "my-change") -> None:
    """Same change directory, merged to `main`, but never attested --
    `check-implement` refuses cutting `change`'s branch here."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _change_dir(root, change)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author plan")


def _run_hook(hook_name: str, process_cwd: Path, stdin: dict, env_overrides: dict | None = None):
    """Invoke a hook script directly. `CLAUDE_PROJECT_DIR` is cleared by
    default so each test controls it explicitly; `process_cwd` is the real
    OS working directory the script starts in (the `pwd` fallback rung)."""
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", str(HOOKS / hook_name)],
        input=json.dumps(stdin),
        cwd=str(process_cwd),
        env=env,
        capture_output=True,
        text=True,
    )


class TestGateCommitResolvesFromCwd(unittest.TestCase):
    """gate-commit.sh: the observable is `gates gate-marker check ci`,
    which allows (exit 0) only against the repo whose staged tree has a
    fresh green marker."""

    def test_cwd_field_resolves_to_that_repo(self):
        with tempfile.TemporaryDirectory() as right, \
             tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            _repo_with_green_ci_marker(right)
            _init_repo(wrong)  # no marker written here

            result = _run_hook(
                "gate-commit.sh", neutral,
                {"tool_input": {"command": "git commit -m x"}, "cwd": str(right)},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_cwd_absent_falls_back_to_claude_project_dir(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as neutral:
            right, neutral = Path(right), Path(neutral)
            _repo_with_green_ci_marker(right)

            result = _run_hook(
                "gate-commit.sh", neutral,
                {"tool_input": {"command": "git commit -m x"}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(right)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_neither_set_falls_back_to_pwd(self):
        with tempfile.TemporaryDirectory() as right:
            right = Path(right)
            _repo_with_green_ci_marker(right)

            result = _run_hook(
                "gate-commit.sh", right,
                {"tool_input": {"command": "git commit -m x"}},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_repo_via_stale_claude_project_dir_is_still_denied(self):
        """Negative control: without a `cwd` field, an unrelated
        `CLAUDE_PROJECT_DIR` is still what gets checked -- proves the hook
        isn't just allowing everything."""
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            _repo_with_green_ci_marker(right)
            _init_repo(wrong)

            result = _run_hook(
                "gate-commit.sh", neutral,
                {"tool_input": {"command": "git commit -m x"}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertNotEqual(result.returncode, 0)


class TestGateMergeResolvesFromCwd(unittest.TestCase):
    """gate-merge.sh: the observable is `gates gate-marker check live-check`
    (plus an always-clean `gates taint check` on a freshly-init repo),
    which together allow (exit 0) only against the repo whose HEAD tree has
    a fresh green marker."""

    def test_cwd_field_resolves_to_that_repo(self):
        with tempfile.TemporaryDirectory() as right, \
             tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            _repo_with_green_live_check_marker(right)
            _init_repo(wrong)  # no live-check marker written here

            result = _run_hook(
                "gate-merge.sh", neutral,
                {"tool_input": {"command": "git merge feature"}, "cwd": str(right)},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_cwd_absent_falls_back_to_claude_project_dir(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as neutral:
            right, neutral = Path(right), Path(neutral)
            _repo_with_green_live_check_marker(right)

            result = _run_hook(
                "gate-merge.sh", neutral,
                {"tool_input": {"command": "git merge feature"}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(right)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_neither_set_falls_back_to_pwd(self):
        with tempfile.TemporaryDirectory() as right:
            right = Path(right)
            _repo_with_green_live_check_marker(right)

            result = _run_hook(
                "gate-merge.sh", right,
                {"tool_input": {"command": "git merge feature"}},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_repo_via_stale_claude_project_dir_is_still_denied(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            _repo_with_green_live_check_marker(right)
            _init_repo(wrong)

            result = _run_hook(
                "gate-merge.sh", neutral,
                {"tool_input": {"command": "git merge feature"}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertNotEqual(result.returncode, 0)


class TestGateArchiveResolvesFromCwd(unittest.TestCase):
    """gate-archive.sh: the observable is `gates discipline check-archive`,
    which allows (exit 0) only against the repo where the change is present
    on the resolved merge target."""

    def _repo_with_change_on_main(self, root: Path, change: str = "my-change") -> None:
        _init_repo(root)
        _change_dir(root, change)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "author plan directly on main")

    def test_cwd_field_resolves_to_that_repo(self):
        with tempfile.TemporaryDirectory() as right, \
             tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            self._repo_with_change_on_main(right)
            _init_repo(wrong)  # change not present here

            result = _run_hook(
                "gate-archive.sh", neutral,
                {"tool_input": {"command": "openspec archive my-change"}, "cwd": str(right)},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_cwd_absent_falls_back_to_claude_project_dir(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as neutral:
            right, neutral = Path(right), Path(neutral)
            self._repo_with_change_on_main(right)

            result = _run_hook(
                "gate-archive.sh", neutral,
                {"tool_input": {"command": "openspec archive my-change"}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(right)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_neither_set_falls_back_to_pwd(self):
        with tempfile.TemporaryDirectory() as right:
            right = Path(right)
            self._repo_with_change_on_main(right)

            result = _run_hook(
                "gate-archive.sh", right,
                {"tool_input": {"command": "openspec archive my-change"}},
            )
            self.assertEqual(result.returncode, 0, result.stderr)


class TestGateImplementResolvesFromCwd(unittest.TestCase):
    """gate-implement.sh: the observable is `gates discipline
    check-implement`, which allows (exit 0) only against the repo where the
    named change is merged AND carries a matching, attested approval."""

    def test_cwd_field_resolves_to_that_repo(self):
        with tempfile.TemporaryDirectory() as right, \
             tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            _repo_with_approved_change(right, "my-change")
            _repo_with_unapproved_change(wrong, "my-change")

            result = _run_hook(
                "gate-implement.sh", neutral,
                {"tool_input": {"command": "git checkout -b my-change"}, "cwd": str(right)},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_cwd_absent_falls_back_to_claude_project_dir(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as neutral:
            right, neutral = Path(right), Path(neutral)
            _repo_with_approved_change(right, "my-change")

            result = _run_hook(
                "gate-implement.sh", neutral,
                {"tool_input": {"command": "git checkout -b my-change"}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(right)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_neither_set_falls_back_to_pwd(self):
        with tempfile.TemporaryDirectory() as right:
            right = Path(right)
            _repo_with_approved_change(right, "my-change")

            result = _run_hook(
                "gate-implement.sh", right,
                {"tool_input": {"command": "git checkout -b my-change"}},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_repo_via_stale_claude_project_dir_is_still_denied(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            _repo_with_approved_change(right, "my-change")
            _repo_with_unapproved_change(wrong, "my-change")

            result = _run_hook(
                "gate-implement.sh", neutral,
                {"tool_input": {"command": "git checkout -b my-change"}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertNotEqual(result.returncode, 0)


class TestGateProposeResolvesFromCwd(unittest.TestCase):
    """gate-propose.sh: the observable is `gates discipline check-propose`,
    which refuses a planning write for a change in implementation outside
    the merge target (hook-correctness D5) -- and the path relativization
    (`rel="${file_path#$(pwd)/}"`) must be computed against the *resolved*
    repo, not the session root."""

    def test_cwd_field_resolves_to_that_repo(self):
        with tempfile.TemporaryDirectory() as right, \
             tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            _init_repo(right)  # stays on main -> authoring allowed
            _init_repo(wrong)
            # authoring refused here: `foo` is in implementation on its branch
            _git(wrong, "checkout", "-b", "foo")
            (wrong / "task.txt").write_text("task\n")
            _git(wrong, "add", "task.txt")
            _git(wrong, "commit", "-m", "task")

            file_path = str(right / "openspec" / "changes" / "foo" / "proposal.md")
            result = _run_hook(
                "gate-propose.sh", neutral,
                {"tool_input": {"file_path": file_path}, "cwd": str(right)},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_cwd_absent_falls_back_to_claude_project_dir(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as neutral:
            right, neutral = Path(right), Path(neutral)
            _init_repo(right)

            file_path = str(right / "openspec" / "changes" / "foo" / "proposal.md")
            result = _run_hook(
                "gate-propose.sh", neutral,
                {"tool_input": {"file_path": file_path}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(right)},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_neither_set_falls_back_to_pwd(self):
        with tempfile.TemporaryDirectory() as right:
            right = Path(right)
            _init_repo(right)

            file_path = str(right / "openspec" / "changes" / "foo" / "proposal.md")
            result = _run_hook(
                "gate-propose.sh", right,
                {"tool_input": {"file_path": file_path}},
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_repo_via_stale_claude_project_dir_is_still_denied(self):
        with tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as wrong, \
             tempfile.TemporaryDirectory() as neutral:
            right, wrong, neutral = Path(right), Path(wrong), Path(neutral)
            _init_repo(right)
            _init_repo(wrong)
            # `foo` is in implementation in `wrong`: its own branch, one
            # commit ahead (hook-correctness D5 refuses only that).
            _git(wrong, "checkout", "-b", "foo")
            (wrong / "task.txt").write_text("task\n")
            _git(wrong, "add", "task.txt")
            _git(wrong, "commit", "-m", "task")

            file_path = str(wrong / "openspec" / "changes" / "foo" / "proposal.md")
            result = _run_hook(
                "gate-propose.sh", neutral,
                {"tool_input": {"file_path": file_path}},
                env_overrides={"CLAUDE_PROJECT_DIR": str(wrong)},
            )
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
