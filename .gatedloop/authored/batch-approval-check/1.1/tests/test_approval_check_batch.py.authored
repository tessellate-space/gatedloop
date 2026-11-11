"""The batched approval check (change `batch-approval-check`, design D1-D5).

A console that shows whether each change is approved used to call `gates
approval check <change>` once per change. The batch resolves the merge
target and the policy once, reads every plan blob through one `git ls-tree`
and one `git cat-file --batch` per ref, and prints one JSON document.

The regressions:
- the batched reader hashing different bytes than `_approval_sha_ref` (it
  reads through `text=True`, so CRLF and CR become LF), which would show an
  approved plan as edited, or an edited one as approved;
- a verdict or reason in the batch that differs from the single form's;
- the no-name form listing an archived change, or out of order;
- the unpushed local-counterpart fallback lost under `self`;
- a context failure answered with anything but a refused document;
- git calls that grow with the number of changes;
- a fingerprint that does not follow the target's commit;
- the single form's output or argument rules changing.

Real git with a bare `origin`, because what is read is git's: blobs at a
ref, a remote-tracking target and a local counterpart.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _approved_plan import APPROVED_AT, APPROVER, write_approved_plan
from _merge_fixture import GATES_SHIM, clean_env, git
from _plan_fixture import _shim

SELF_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'
SELF_M = {"approval": {"plan": "self"}}


class ApprovalRepo:
    """A primary checkout under the `self` policy. With `origin`, it tracks
    a bare `origin` whose HEAD names `branch`, so the target resolves to
    `origin/<branch>`; without, and on a branch other than main or master,
    no target resolves at all."""

    def __init__(self, tmp: Path, branch: str = "main", origin: bool = True):
        self.tmp = Path(tmp)
        self.primary = self.tmp / "primary"
        self.bare = self.tmp / "origin.git"
        self.branch = branch
        p = self.primary
        p.mkdir(parents=True)
        git(p, "init", "-q", "-b", branch)
        git(p, "config", "user.email", "t@example.com")
        git(p, "config", "user.name", "T")
        (p / ".gates.yaml").write_text(SELF_MANIFEST)
        self.commit("init")
        if origin:
            git(self.tmp, "init", "-q", "--bare", "-b", branch, str(self.bare))
            git(p, "remote", "add", "origin", str(self.bare))
            self.push()
            git(p, "remote", "set-head", "origin", branch)

    # ---- running -----------------------------------------------------------

    def gates(self, *args, path_prefix: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATES_SHIM), *args],
            cwd=self.primary, capture_output=True, text=True,
            env=clean_env(path_prefix=path_prefix),
        )

    def batch(self, *names, path_prefix: str | None = None) -> tuple[int, dict]:
        r = self.gates("approval", "check", "--json", *names, path_prefix=path_prefix)
        try:
            doc = json.loads(r.stdout)
        except ValueError:
            raise AssertionError(f"not a JSON document (exit {r.returncode}): {r.stdout}{r.stderr}")
        return r.returncode, doc

    def single(self, name: str) -> tuple[bool, str]:
        """The single form's verdict: `(ok, reason)`, the reason being the
        one printed line without its `gatedloop: ` prefix."""
        r = self.gates("approval", "check", name)
        line = (r.stdout or r.stderr).strip()
        return r.returncode == 0, line.removeprefix("gatedloop: ")

    # ---- building ----------------------------------------------------------

    def commit(self, subject: str) -> str:
        git(self.primary, "add", "-A")
        git(self.primary, "commit", "-q", "--allow-empty", "-m", subject)
        return git(self.primary, "rev-parse", "HEAD")

    def push(self) -> None:
        git(self.primary, "push", "-q", "origin", f"HEAD:{self.branch}")

    def approved(self, name: str) -> str:
        return write_approved_plan(self.primary, name)

    def unattested(self, name: str) -> None:
        write_approved_plan(self.primary, name)
        (self.primary / "openspec" / "changes" / name / ".openspec.yaml").write_text(
            "schema: spec-driven\n")

    def edit_proposal(self, name: str) -> None:
        p = self.primary / "openspec" / "changes" / name / "proposal.md"
        p.write_text(p.read_text() + "\nEdited after approval.\n")

    def crlf_plan(self, name: str) -> None:
        """A plan whose design is CRLF, whose proposal has a lone CR and
        non-ASCII text, whose spec is non-ASCII, and whose tasks.md carries
        an oracle tag on CRLF lines -- committed, then approved with the sha
        the single form computes from the ref, as an attest from the target
        would."""
        d = self.primary / "openspec" / "changes" / name
        (d / "specs" / "cap").mkdir(parents=True)
        (d / "proposal.md").write_bytes("# Proposal: café\r\rWhy — because.\n".encode())
        (d / "design.md").write_bytes(b"# Design\r\n\r\nD1. Do it.\r\n")
        (d / "specs" / "cap" / "spec.md").write_bytes(
            "## ADDED Requirements\n\n### Requirement: Ünïcode\n\nThe system SHALL say naïve.\n".encode())
        (d / "tasks.md").write_bytes(b"## 1. Do it\r\n\r\n- [ ] 1.1 Do it [oracle: unit]\r\n")
        (d / ".openspec.yaml").write_text("schema: spec-driven\n")
        self.commit(f"plan: {name}")
        with in_repo_env():
            sha = _shim()._approval_sha_ref(self.primary, name, "HEAD")
        assert sha, "fixture: the single form hashed nothing"
        (d / ".openspec.yaml").write_text(
            "schema: spec-driven\n"
            f"x-gatedloop-approved-by: {APPROVER}\n"
            f"x-gatedloop-approved-at: '{APPROVED_AT}'\n"
            f"x-gatedloop-approved-sha: {sha}\n"
        )
        self.commit(f"attest: {name}")


def in_repo_env():
    """The shim's in-process git calls read `os.environ`: a test run from a
    git hook would otherwise point them at the wrong repository."""
    return mock.patch.dict(os.environ, clean_env(), clear=True)


class BatchedReaderTest(unittest.TestCase):
    """D1, D2: one context, one reader, today's verdicts and today's hash."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_batched_sha_equals_the_ref_sha_for_crlf_and_non_ascii_files(self):
        repo = ApprovalRepo(self.tmp)
        repo.crlf_plan("crlf")
        repo.approved("plain")
        repo.commit("plan: plain")
        raw = subprocess.run(
            ["git", "cat-file", "blob", "HEAD:openspec/changes/crlf/design.md"],
            cwd=repo.primary, capture_output=True, env=clean_env(),
        ).stdout
        self.assertIn(b"\r\n", raw, "fixture: the committed design must keep its CRLF")
        shim = _shim()
        with in_repo_env():
            reader = shim._BatchPlanReader(repo.primary, ["crlf", "plain"])
            for name in ("crlf", "plain"):
                expected = shim._approval_sha_ref(repo.primary, name, "HEAD")
                self.assertIsNotNone(expected)
                self.assertEqual(reader.approval_sha(name, "HEAD"), expected, name)

    def test_verdicts_through_the_batched_reader_equal_the_wrapper(self):
        repo = ApprovalRepo(self.tmp)
        repo.approved("approved")
        repo.unattested("unattested")
        repo.approved("edited")
        repo.commit("plans")
        repo.edit_proposal("edited")
        repo.commit("edit after approval")
        repo.crlf_plan("crlf")
        repo.push()
        repo.approved("local-only")
        repo.commit("plan merged locally, not pushed")
        names = ["approved", "unattested", "edited", "crlf", "local-only", "absent"]
        shim = _shim()
        with in_repo_env():
            ctx = shim._approval_context(repo.primary, SELF_M)
            reader = shim._BatchPlanReader(repo.primary, names)
            for name in names:
                want = shim._approval_check_at(repo.primary, name, SELF_M)
                got = shim._approval_verdict(ctx, name, reader)
                self.assertEqual(tuple(got[:3]), want, name)
        self.assertTrue(want[0] is False and "not present" in want[2], want)

    def test_no_target_gives_the_wrapper_refusal(self):
        repo = ApprovalRepo(self.tmp, branch="trunk", origin=False)
        repo.approved("approved")
        repo.commit("plan")
        shim = _shim()
        with in_repo_env():
            ctx = shim._approval_context(repo.primary, SELF_M)
            reader = shim._BatchPlanReader(repo.primary, ["approved"])
            want = shim._approval_check_at(repo.primary, "approved", SELF_M)
            got = shim._approval_verdict(ctx, "approved", reader)
        self.assertEqual(tuple(got[:3]), want)
        self.assertFalse(want[0])


if __name__ == "__main__":
    unittest.main()
