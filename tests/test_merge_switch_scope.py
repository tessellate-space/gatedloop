"""The merge hook judges a switch-then-merge by the branch the switch names
(openspec change `friction-fixes`, design D5; the loop-enforcement delta's
"Only integration merges are gated" requirement and its scenarios; issue #44).

Since hook-correctness D2, any `git checkout` / `git switch` earlier in the
same command kept a merge gated, because the checkout the hook sees is not the
one the merge lands on. A lane syncing its branch in one command (`git
checkout my-change && git merge --ff-only origin/main`) was then asked for a
live-check marker that can never exist for a sync. Now:

- a switch to a named branch other than the target's passes, judged by
  `gates discipline merge-scope --branch <b>`;
- a switch to the target stays gated;
- a switch the hook cannot resolve stays gated, and its denial says to run the
  merge as its own command after the switch.

Real git: a bare remote and a clone, so the merge target is `origin/main`,
and the real `hooks/gate-merge.sh` driven with a PreToolUse payload. No gate
marker exists anywhere, so a pass means the hook judged the merge
not-integrating, and a gated merge is denied for its missing live-check.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
MERGE_HOOK = REPO / "hooks" / "gate-merge.sh"
UNRESOLVED = "run the merge as its own command after the switch"

MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: "true"
"""


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env()).stdout.strip()


def _clone_with_a_change(tmp: Path) -> Path:
    """A clone of a bare remote: `main` tracking `origin/main`, a change
    branch `my-change` with one commit, and `origin/main` one commit ahead of
    where `my-change` started. The clone is left on `main`."""
    remote = tmp / "remote.git"
    _git(tmp, "init", "-q", "--bare", "-b", "main", str(remote))
    root = tmp / "clone"
    _git(tmp, "clone", "-q", str(remote), str(root))
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "push", "-q", "-u", "origin", "main")
    _git(root, "checkout", "-q", "-b", "my-change")
    (root / "change.txt").write_text("the change\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "the change")
    _git(root, "checkout", "-q", "main")
    (root / "later.txt").write_text("main moved on\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "main moves")
    _git(root, "push", "-q", "origin", "main")
    return root


def _run_hook(root: Path, command: str):
    env = _env()
    env["CLAUDE_PROJECT_DIR"] = str(root)
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(root)})
    return subprocess.run(["bash", str(MERGE_HOOK)], input=payload, cwd=str(root),
                          env=env, capture_output=True, text=True, timeout=120)


def _merge_scope(root: Path, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), "discipline", "merge-scope", *args],
                          cwd=root, capture_output=True, text=True, env=_env(), timeout=60)


class TestMergeScopeForANamedBranch(unittest.TestCase):
    """Regression guarded: the hook has no way to ask whether a merge on a
    branch other than the current one integrates."""

    def test_a_change_branch_is_not_integrating(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            r = _merge_scope(root, "--branch", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "not-integrating")

    def test_the_target_branch_is_integrating(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            _git(root, "checkout", "-q", "my-change")
            r = _merge_scope(root, "--branch", "main")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "integrating")

    def test_without_the_flag_the_current_checkout_decides_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            self.assertEqual(_merge_scope(root).stdout.strip(), "integrating")
            _git(root, "checkout", "-q", "my-change")
            self.assertEqual(_merge_scope(root).stdout.strip(), "not-integrating")


class TestSwitchingToAChangeBranchAndSyncing(unittest.TestCase):
    """Regression guarded: #44 -- a one-command sync of a lane's branch
    refused for a live-check marker no sync can have."""

    def test_checkout_then_fast_forward_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            r = _run_hook(root, "git checkout my-change && git merge --ff-only origin/main")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_switch_then_merge_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            # loop-hardening D3: the sync itself must not commit.
            r = _run_hook(root, "git switch my-change && git merge --no-commit origin/main")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestSwitchingToTheTargetStaysGated(unittest.TestCase):
    """Regression guarded: an integration let through because a switch now
    passes when it names a branch."""

    def test_checkout_main_then_merge_is_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            _git(root, "checkout", "-q", "my-change")
            r = _run_hook(root, "git checkout main && git merge --ff-only my-change")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("live-check", r.stderr)
            self.assertNotIn(UNRESOLVED, r.stderr)

    def test_creating_the_target_branch_then_merging_is_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            _git(root, "checkout", "-q", "my-change")
            _git(root, "branch", "-q", "-D", "main")
            r = _run_hook(root, "git checkout -b main origin/main && git merge my-change")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("live-check", r.stderr)


class TestASwitchTheHookCannotResolve(unittest.TestCase):
    """Regression guarded: a detached checkout of the target let through, or
    denied with no word on how to get past it."""

    def test_a_detached_checkout_then_merge_is_gated_and_says_why(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _clone_with_a_change(Path(tmp))
            _git(root, "checkout", "-q", "my-change")
            r = _run_hook(root, "git checkout --detach origin/main && git merge my-change")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("live-check", r.stderr)
            self.assertIn(UNRESOLVED, r.stderr)


if __name__ == "__main__":
    unittest.main()
