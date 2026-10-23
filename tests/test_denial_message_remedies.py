"""Denial-message audit (design D5 of `harden-hook-matching`, task 4.1):
every denial emitted by `cmd_discipline`'s checks names the precise unmet
prerequisite AND the exact command that satisfies it -- no message requires
reading enforcement source to act on it.

Stdlib only, per `zero-dep-shim`. Mirrors the subprocess-driven style of
`tests/test_approval_policy.py` -- every case drives the real `bin/gates`
shim against a throwaway git repo.

Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST_SELF = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path, manifest: str = MANIFEST_SELF) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class TestCheckArchiveDenialNamesTheRemedy(unittest.TestCase):
    def test_unmerged_change_names_the_merge_and_the_retry_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            r = _run_gates(root, "discipline", "check-archive", "never-merged-change")
            self.assertNotEqual(r.returncode, 0)
            # Names the unmet prerequisite concretely...
            self.assertIn("has not been merged to 'main'", r.stderr)
            # ...and the exact remedy: merge, then re-run the archive command.
            self.assertIn("merge branch 'never-merged-change' to 'main'", r.stderr)
            self.assertIn("re-run `openspec archive never-merged-change`", r.stderr)


class TestCheckProposeDenialNamesTheRemedy(unittest.TestCase):
    def test_wrong_branch_names_the_checkout_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "feature-x")
            # The branch rule governs scaffolding (hook-correctness D5).
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("design D9", r.stderr)
            self.assertIn("`git checkout main`", r.stderr)
            self.assertIn("`git checkout -b plan/<name> main`", r.stderr)


class TestCheckImplementApprovalDenialsNameTheRemedy(unittest.TestCase):
    def _make_change_repo(self, root: Path, change: str = "my-change") -> Path:
        _init_repo(root)
        change_dir = root / "openspec" / "changes" / change
        change_dir.mkdir(parents=True)
        (change_dir / "proposal.md").write_text("plan\n")
        (change_dir / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "author plan")
        return change_dir

    def test_missing_approved_by_names_the_attest_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_change_repo(root)
            r = _run_gates(root, "discipline", "check-implement", "my-change")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("no approved_by", r.stderr)
            self.assertIn("`gates approval attest my-change --local`", r.stderr)
            self.assertIn("--pr", r.stderr)

    def test_stale_approval_after_edit_names_the_reattest_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = self._make_change_repo(root)
            attest = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(attest.returncode, 0, attest.stderr)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "attest approval")

            (change_dir / "proposal.md").write_text("a materially different plan\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "edit proposal after approval")

            r = _run_gates(root, "discipline", "check-implement", "my-change")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("edited after approval", r.stderr)
            self.assertIn("`gates approval attest my-change --local`", r.stderr)

    def test_change_not_present_on_target_names_what_must_happen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            # A change dir authored only in the working tree (untracked),
            # never merged to main -- the not-present-on-target path.
            change_dir = root / "openspec" / "changes" / "wip-change"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")

            r = _run_gates(root, "discipline", "check-implement", "wip-change")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("is not present on 'main'", r.stderr)
            self.assertIn("reviewed and merged to 'main'", r.stderr)


if __name__ == "__main__":
    unittest.main()
