"""End-to-end integration check for `harden-hook-matching` (task 5.1): the
real `hooks/gate-merge.sh` and `hooks/gate-commit.sh` scripts, piped crafted
`PreToolUse` JSON exactly as Claude Code would, in a scratch git repo --
reproducing the false-positive shapes from issue #8/#40 (a `merge-base`
query, and prose that merely mentions "git merge") and the archive-move
commit misclassification from issue #16 item 4.

`openspec` itself is faked on PATH for `validate` only (same technique
`test_planning_grade_commit.py` uses) -- the archive MOVE is performed
directly (mkdir/rmtree), the same mechanical rename `openspec archive`
itself performs, so the test stays hermetic while still exercising the
real hook scripts end to end.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
MERGE_HOOK = REPO / "hooks" / "gate-merge.sh"
COMMIT_HOOK = REPO / "hooks" / "gate-commit.sh"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

FAKE_OPENSPEC_VALID = """\
#!/usr/bin/env bash
if [ "$1" = "validate" ]; then
  echo '{"items":[{"id":"'"$2"'","type":"change","valid":true,"issues":[]}]}'
  exit 0
fi
exit 1
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args, path=None):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True, env=env,
    )


def _run_hook(hook: Path, root: Path, command: str, path: str | None = None):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    if path is not None:
        env["PATH"] = path
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(root)})
    return subprocess.run(
        ["bash", str(hook)], input=payload, cwd=str(root), env=env, capture_output=True, text=True,
    )


def _install_fake_openspec(bindir: Path, script: str) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    exe = bindir / "openspec"
    exe.write_text(script)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class TestMergeGateFalsePositiveRepros(unittest.TestCase):
    """Issue #8/#40 item 4's exact repro shapes, through the real hook."""

    def test_merge_base_is_ancestor_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            r = _run_hook(MERGE_HOOK, root, "git merge-base --is-ancestor HEAD HEAD")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_quoted_prose_mentioning_git_merge_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            r = _run_hook(
                MERGE_HOOK, root,
                'gh issue create --body "please run git merge after the review lands"',
            )
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_real_unmarked_merge_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "branch", "feature")
            r = _run_hook(MERGE_HOOK, root, "git merge feature")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("live-check", r.stderr)


class TestArchiveMoveCommitLandsAtPlanningGrade(unittest.TestCase):
    """Issue #16 item 4's repro: a merged change's `openspec archive` move,
    committed with no ledger-row staged, lands at planning grade through the
    real `hooks/gate-commit.sh` -- no green `ci` marker required."""

    def test_archive_move_commit_allowed_by_the_real_hook(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)

            # A change whose plan is already on `main` -- "merged", trivially,
            # since this scratch repo's main IS the change's home.
            change_dir = root / "openspec" / "changes" / "foo"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "add foo change")

            # The archive move itself: the same mechanical rename `openspec
            # archive` performs. Content differs from the original so git's
            # default rename detection does not collapse it and hide the old
            # path from the staged diff (matching a real multi-file move).
            archived_dir = root / "openspec" / "changes" / "archive" / "2026-01-01-foo"
            archived_dir.mkdir(parents=True)
            (archived_dir / "proposal.md").write_text("archived plan, formerly foo\n")
            shutil.rmtree(change_dir)
            _git(root, "add", "-A")
            # Deliberately no ledger row staged (.gatedloop/runs/**) -- the
            # commit must classify at planning grade on the archive move's
            # own merits, not by riding a green `ci` marker.

            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_VALID)
            r = _run_hook(COMMIT_HOOK, root, "git commit -m 'archive foo'", path=path)
            self.assertEqual(r.returncode, 0, r.stderr)

            # No `ci` marker was ever recorded for this tree -- confirms the
            # allow came from the planning-grade rung, not a stale/borrowed
            # marker.
            check = _run_gates(root, "discipline", "check-commit",
                                subprocess.run(["git", "write-tree"], cwd=root,
                                                capture_output=True, text=True).stdout.strip(),
                                path=path)
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertIn("planning-grade", check.stdout)


if __name__ == "__main__":
    unittest.main()
