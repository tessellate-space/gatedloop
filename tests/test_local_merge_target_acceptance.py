"""Local merge-target acceptance (design D5 of `worktree-native-loop`).

`check-archive`'s guarantee is ORDERING (merge precedes archive) -- a sound
local counterpart of the merge target proves that just as well as origin,
so it's accepted with a loud "not pushed yet" advisory, closing the 4+
interim pushes per serialized merge session #17 reported. `check-implement`
guarantees a REVIEWED, ATTESTED plan: under policy `review` the attestation
is anchored to the forge's approving review, so origin stays required; under
policy `self`, local attestation is already the legitimate writer, so the
local counterpart is accepted the same way.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
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

MANIFEST_REVIEW = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
MANIFEST_SELF = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'

FAKE_GH_APPROVED = """\
#!/usr/bin/env bash
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  echo '{"reviews":[{"state":"APPROVED","author":{"login":"radub21"},"submittedAt":"2026-08-19T09:30:00Z"}]}'
  exit 0
fi
exit 1
"""


def _git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r


def _run_gates(root, *args, path=None):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True, env=env,
    )


def _install_fake_gh(bindir: Path, script: str) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(script)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


def _init_repo_with_origin(root: Path, remote_tmp: Path, manifest: str) -> Path:
    """A local repo on `main`, already tracking a bare `origin` at its
    initial commit -- so a LATER local-only commit (the "merge") is present
    on local `main` but not yet on `origin/main`, exactly the unpushed-merge
    shape design D5 accepts."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")

    bare = remote_tmp / "origin.git"
    _git(remote_tmp, "init", "--bare", "-b", "main", str(bare))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "origin", "HEAD:main")
    _git(root, "remote", "set-head", "origin", "main")
    return bare


def _author_change_dir(root: Path, change: str) -> Path:
    d = root / "openspec" / "changes" / change
    d.mkdir(parents=True)
    (d / "proposal.md").write_text("plan\n")
    (d / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    return d


class TestCheckArchiveLocalCounterpart(unittest.TestCase):
    def test_merged_local_unpushed_allowed_with_advisory(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as remote_tmp:
            root, remote = Path(tmp), Path(remote_tmp)
            _init_repo_with_origin(root, remote, MANIFEST_REVIEW)
            _author_change_dir(root, "my-change")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "merge my-change into local main")

            r = _run_gates(root, "discipline", "check-archive", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("not yet", r.stdout + r.stderr)
            self.assertIn("push", (r.stdout + r.stderr).lower())

    def test_unmerged_anywhere_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as remote_tmp:
            root, remote = Path(tmp), Path(remote_tmp)
            _init_repo_with_origin(root, remote, MANIFEST_REVIEW)

            r = _run_gates(root, "discipline", "check-archive", "never-merged")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("has not been merged", r.stderr)

    def test_merged_on_origin_allowed_silently(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as remote_tmp:
            root, remote = Path(tmp), Path(remote_tmp)
            _init_repo_with_origin(root, remote, MANIFEST_REVIEW)
            _author_change_dir(root, "my-change")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "merge my-change")
            _git(root, "push", "origin", "HEAD:main")

            r = _run_gates(root, "discipline", "check-archive", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            # No unpushed advisory when it's actually on origin.
            self.assertNotIn("not yet", r.stdout + r.stderr)


class TestCheckImplementPolicyDependentAcceptance(unittest.TestCase):
    def _merge_and_attest_locally(self, root: Path, change: str = "my-change") -> None:
        _author_change_dir(root, change)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "author plan")
        with tempfile.TemporaryDirectory() as bin_tmp:
            path = _install_fake_gh(Path(bin_tmp), FAKE_GH_APPROVED)
            env = dict(os.environ)
            env["PATH"] = path
            r = subprocess.run(
                [sys.executable, str(GATES_SHIM), "approval", "attest", change, "--local"],
                cwd=root, capture_output=True, text=True, env=env,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "attest approval locally")

    def test_self_policy_accepts_local_only_merge_with_advisory(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as remote_tmp:
            root, remote = Path(tmp), Path(remote_tmp)
            _init_repo_with_origin(root, remote, MANIFEST_SELF)
            self._merge_and_attest_locally(root)

            r = _run_gates(root, "discipline", "check-implement", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("push", r.stdout.lower())

    def test_review_policy_refuses_local_only_merge(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as remote_tmp:
            root, remote = Path(tmp), Path(remote_tmp)
            # MANIFEST_REVIEW: `gates approval attest --local` would itself
            # refuse under `review` policy, so attest by writing the keys
            # directly (this test is about check-implement's own acceptance
            # rule, not the attestation writer's policy gate).
            _init_repo_with_origin(root, remote, MANIFEST_REVIEW)
            change_dir = _author_change_dir(root, "my-change")
            sha_proc = subprocess.run(
                [sys.executable, str(GATES_SHIM), "approval", "sha", "my-change"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(sha_proc.returncode, 0, sha_proc.stderr)
            sha = sha_proc.stdout.strip()
            (change_dir / ".openspec.yaml").write_text(
                "schema: spec-driven\ncreated: 2026-08-19\n"
                "approved_by: T <t@example.com>\n"
                "approved_at: 2026-08-19T09:30:00+00:00\n"
                f"approved_sha: {sha}\n"
            )
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "merge and attest, locally only")

            r = _run_gates(root, "discipline", "check-implement", "my-change")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("not present on 'origin/main'", r.stderr)

    def test_self_policy_still_refuses_when_unapproved(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as remote_tmp:
            root, remote = Path(tmp), Path(remote_tmp)
            _init_repo_with_origin(root, remote, MANIFEST_SELF)
            _author_change_dir(root, "my-change")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "author plan, never attested")

            r = _run_gates(root, "discipline", "check-implement", "my-change")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("no approved_by", r.stderr)


if __name__ == "__main__":
    unittest.main()
