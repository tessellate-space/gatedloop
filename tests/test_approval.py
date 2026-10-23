"""Approval-attestation tests for the `gates` shim (design D10/D12, tasks
1c.4-1c.6, 1d.2-1d.6).

Stdlib only, per `zero-dep-shim`. `gh` is mocked with a throwaway executable
placed first on PATH -- these tests never touch a real forge or create a
real pull request; that is deliberately left to manual, live verification
(task 1d.7), since a unit test cannot legitimately merge a PR anyway.

Run with:  python3 -m unittest discover -s tests
"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
"""

FAKE_GH_APPROVED = """\
#!/usr/bin/env bash
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  echo '{"reviews":[{"state":"COMMENTED","author":{"login":"someone"},"submittedAt":"2026-08-18T10:00:00Z"},{"state":"APPROVED","author":{"login":"radub21"},"submittedAt":"2026-08-19T09:30:00Z"}]}'
  exit 0
fi
exit 1
"""

FAKE_GH_NO_APPROVAL = """\
#!/usr/bin/env bash
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  echo '{"reviews":[{"state":"COMMENTED","author":{"login":"someone"},"submittedAt":"2026-08-18T10:00:00Z"}]}'
  exit 0
fi
exit 1
"""

FAKE_GH_ERRORS = """\
#!/usr/bin/env bash
echo "error: authentication required" >&2
exit 1
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args, path=None):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True, env=env,
    )


def _install_fake_gh(bindir: Path, script: str) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(script)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


def _make_change_repo(root: Path, change: str = "my-change"):
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    change_dir = root / "openspec" / "changes" / change
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("plan\n")
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author plan")
    return change_dir


class TestAttestWritesFromApprovedReview(unittest.TestCase):
    def test_attest_writes_approved_fields_from_the_review(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root)
            path = _install_fake_gh(Path(bin_tmp), FAKE_GH_APPROVED)

            result = _run_gates(root, "approval", "attest", "my-change", "--pr", "42", path=path)
            self.assertEqual(result.returncode, 0, result.stderr)

            data = (change_dir / ".openspec.yaml").read_text()
            self.assertIn('x-gatedloop-approved-by: "radub21"', data)
            self.assertIn('x-gatedloop-approved-at: "2026-08-19T09:30:00Z"', data)
            self.assertIn("x-gatedloop-approved-sha:", data)

    def test_attest_never_takes_a_non_approved_review(self):
        """The FIRST approved review, not the first review of any state --
        a COMMENTED review sorted before the APPROVED one must not win."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _make_change_repo(root)
            path = _install_fake_gh(Path(bin_tmp), FAKE_GH_APPROVED)

            result = _run_gates(root, "approval", "attest", "my-change", "--pr", "1", path=path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("radub21", result.stdout)
            self.assertNotIn("someone", result.stdout)


class TestAttestFailsClosed(unittest.TestCase):
    """Task 1d.4/1d.5: never falls back to an unattested value."""

    def test_no_approved_review_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root)
            before = (change_dir / ".openspec.yaml").read_text()
            path = _install_fake_gh(Path(bin_tmp), FAKE_GH_NO_APPROVAL)

            result = _run_gates(root, "approval", "attest", "my-change", "--pr", "1", path=path)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((change_dir / ".openspec.yaml").read_text(), before)

    def test_gh_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root)
            before = (change_dir / ".openspec.yaml").read_text()

            result = _run_gates(root, "approval", "attest", "my-change", "--pr", "1", path="/usr/bin:/bin")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("gh", result.stderr)
            self.assertEqual((change_dir / ".openspec.yaml").read_text(), before)

    def test_gh_errors_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root)
            before = (change_dir / ".openspec.yaml").read_text()
            path = _install_fake_gh(Path(bin_tmp), FAKE_GH_ERRORS)

            result = _run_gates(root, "approval", "attest", "my-change", "--pr", "1", path=path)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((change_dir / ".openspec.yaml").read_text(), before)


class TestApprovedShaExcludesTasksAndMetadata(unittest.TestCase):
    """Task 1d.2: the hash covers plan artifacts (proposal.md, design.md,
    specs/**) and never tasks.md or .openspec.yaml itself."""

    def test_editing_tasks_md_does_not_change_the_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root)

            before = _run_gates(root, "approval", "sha", "my-change")
            self.assertEqual(before.returncode, 0, before.stderr)

            (change_dir / "tasks.md").write_text("- [ ] 1.1 do a thing\n")
            after = _run_gates(root, "approval", "sha", "my-change")
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertEqual(before.stdout, after.stdout)

    def test_editing_proposal_changes_the_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root)

            before = _run_gates(root, "approval", "sha", "my-change")
            (change_dir / "proposal.md").write_text("a different plan\n")
            after = _run_gates(root, "approval", "sha", "my-change")
            self.assertNotEqual(before.stdout, after.stdout)


if __name__ == "__main__":
    unittest.main()
