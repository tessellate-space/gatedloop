"""Hook install, doctor and the adoption hook fact use git's effective hooks
directory (design D3 of `cross-worktree-evidence`, task 2.1; issue #38).

They used to find the hook through `git rev-parse --git-dir`, which in a
linked worktree is the private `.git/worktrees/<lane>`. Git runs hooks only
from the common directory (or `core.hooksPath`), so from a lane doctor
warned that an installed hook was missing, and install wrote a file git
never runs and reported success. Run from any worktree, all of them must
now see the hook the primary sees.

Real linked worktrees: where git runs hooks from is git's own answer, and
the hook firing (or not) for a real commit is the proof. Nothing here
touches this repository's own `.git/hooks`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _hook_fixture import OLDER_COPY, write_hook
from _lane_fixture import GATES_SHIM, lane_repo
from _merge_fixture import REPO, clean_env, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_hooks_dir", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _gates(cwd, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=str(cwd), capture_output=True,
        text=True, env=clean_env({"CLAUDE_PLUGIN_ROOT": str(REPO)}),
    )


class TestHooksFromALinkedWorktree(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(os.environ, clean_env(), clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.repo = lane_repo(self._tmp.name)
        self.primary = self.repo.primary
        self.lane = self.repo.lane
        self.shared_hook = (Path(self.primary) / ".git" / "hooks" / "pre-commit").resolve()
        self.private_hook = Path(git(self.lane, "rev-parse", "--absolute-git-dir")) / "hooks" / "pre-commit"

    def test_doctor_in_the_lane_reports_the_hook_installed_in_the_primary(self):
        # Fails if doctor looks in the lane's private git dir: it warned
        # "not installed" for a hook git runs for every worktree.
        self.assertEqual(_gates(self.primary, "hook", "install").returncode, 0)
        for where in (self.primary, self.lane):
            with self.subTest(where=where.name):
                r = _gates(where, "doctor")
                row = [line for line in r.stdout.splitlines() if "git-commit-hook" in line]
                self.assertEqual(len(row), 1, r.stdout)
                self.assertIn("[ok  ]", row[0])

    def test_install_in_the_lane_writes_the_shared_hook_and_it_fires_in_the_primary(self):
        # Fails if install writes `.git/worktrees/<lane>/hooks/pre-commit`, a
        # file git never runs, and reports success.
        r = _gates(self.lane, "hook", "install")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.shared_hook.is_file())
        self.assertFalse(self.private_hook.exists())
        self.assertIn(str(self.shared_hook), r.stdout)

        # The hook git now runs refuses an ungated agent commit in the primary.
        (Path(self.primary) / "ungated.txt").write_text("never gated\n")
        git(self.primary, "add", "ungated.txt")
        commit = subprocess.run(
            ["git", "commit", "-q", "-m", "ungated"], cwd=str(self.primary),
            capture_output=True, text=True, env=clean_env({"CLAUDE_PLUGIN_ROOT": str(REPO)}),
        )
        self.assertNotEqual(commit.returncode, 0, commit.stdout)
        self.assertIn("gatedloop", commit.stderr)

    def test_the_adoption_hook_fact_agrees_from_both_checkouts(self):
        # Fails if `git-hook-copy` / `git-hook-current` read the lane's
        # private git dir: from the lane, a stale copy in the shared hooks
        # directory read as "no copy", so the refresh was never offered.
        write_hook(self.shared_hook, OLDER_COPY)
        facts = {
            where.name: gates._adoption_project_facts(Path(where), {}, [])["hook"]
            for where in (self.primary, self.lane)
        }
        self.assertEqual(facts[self.primary.name], {"copy": True, "current": False})
        self.assertEqual(facts[self.lane.name], facts[self.primary.name])

    def test_a_core_hooks_path_redirect_is_still_refused_from_both_checkouts(self):
        # Fails if the shared-directory lookup swallows the `hooksPath`
        # classification and installs over an unrecognised redirect.
        git(self.primary, "config", "core.hooksPath", "custom-hooks")
        for where in (self.primary, self.lane):
            with self.subTest(where=where.name):
                kind, _path = gates._detect_hook_owner(Path(where))
                self.assertEqual(kind, "hooksPath")
                r = _gates(where, "hook", "install")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("core.hooksPath", r.stderr)
                self.assertFalse((Path(where) / "custom-hooks" / "pre-commit").exists())


if __name__ == "__main__":
    unittest.main()
