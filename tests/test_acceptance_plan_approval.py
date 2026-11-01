"""Every acceptance writer refuses an unapproved plan (loop-hardening D2,
#101).

The regression: a human accepted a tree whose plan was not the approved
one -- amended after approval and never re-attested -- and the acceptance
then let it merge. `gates acceptance attest` now runs `gates merge`'s plan
check before writing, with `--local`, `--pr` or `--merged`. Under
`approval.acceptance: self`, `gates record-merged` still records the merge
row, because the forge merge already happened, but no `accept` row, and it
exits non-zero naming the re-approval so the job goes red.

Real git (the target is a ref); `gh` is a stub or `_forge_fixture`'s fake
forge, so no test reaches a real API.

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

from _approved_plan import GATES_SHIM, write_approved_plan
from _forge_fixture import NO_CI
from _merge_fixture import CHANGE, LEDGER_REL, combined, git, rows_from_text
from test_merged_acceptance import merged_change

LOCAL_CHANGE = "my-change"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n  acceptance: self\n'

FAKE_GH_APPROVED = """\
#!/usr/bin/env bash
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  echo '{"reviews":[{"state":"APPROVED","author":{"login":"product-owner"},"submittedAt":"2026-09-21T09:30:00Z"}]}'
  exit 0
fi
exit 1
"""


def _gates(root: Path, *args, path: str | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    if path is not None:
        env["PATH"] = path
    return subprocess.run([sys.executable, str(GATES_SHIM), *args],
                          cwd=root, capture_output=True, text=True, env=env)


def _branch_with_an_edited_spec(root: Path) -> None:
    """`main` carries `my-change`'s approved plan; the branch then widens
    its own requirement after approval."""
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    write_approved_plan(root, LOCAL_CHANGE)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "plan: my-change")
    git(root, "checkout", "-q", "-b", LOCAL_CHANGE)
    (root / "feature.txt").write_text("the increment\n")
    spec = root / "openspec" / "changes" / LOCAL_CHANGE / "specs" / "cap" / "spec.md"
    spec.write_text(spec.read_text() + "\n### Requirement: More\n\nThe system SHALL also fly.\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "task work, and a wider spec")


def _acceptance_rows(rows: list) -> list:
    return [r for r in rows if r.get("gate") == "acceptance"]


def _local_ledger(root: Path) -> list:
    p = root / ".gatedloop" / "runs" / f"{LOCAL_CHANGE}.jsonl"
    return rows_from_text(p.read_text()) if p.exists() else []


class AttestRefusesAnUnapprovedPlan(unittest.TestCase):
    def test_local_refuses_a_plan_edited_after_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _branch_with_an_edited_spec(root)

            r = _gates(root, "acceptance", "attest", LOCAL_CHANGE, "--local")

            self.assertEqual(r.returncode, 1, combined(r))
            self.assertIn("differs from the plan approved", r.stderr)
            self.assertIn("Nothing was written", r.stderr)
            self.assertEqual(_acceptance_rows(_local_ledger(root)), [])

    def test_pr_refuses_a_plan_edited_after_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _branch_with_an_edited_spec(root)
            bindir = root.parent / f"{root.name}-bin"
            bindir.mkdir()
            gh = bindir / "gh"
            gh.write_text(FAKE_GH_APPROVED)
            gh.chmod(gh.stat().st_mode | stat.S_IEXEC)

            r = _gates(root, "acceptance", "attest", LOCAL_CHANGE, "--pr", "7",
                       path=f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}")

            self.assertEqual(r.returncode, 1, combined(r))
            self.assertIn("differs from the plan approved", r.stderr)
            self.assertEqual(_acceptance_rows(_local_ledger(root)), [])


def _amend_the_target_plan(repo) -> None:
    """After the implementation PR merged, another commit amends the
    change's design on `main` without re-attesting it (#101's shape)."""
    design = repo.primary / "openspec" / "changes" / CHANGE / "design.md"
    design.write_text("# Design\n\nD1. Do it differently.\n")
    git(repo.primary, "add", "-A")
    git(repo.primary, "commit", "-q", "-m", "amend add-thing's design")
    git(repo.primary, "push", "-q", "origin", "HEAD:main")
    repo.push_log.write_text("")


class MergedAcceptanceRefusesAnUnapprovedPlan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _ledger(self, repo) -> list:
        p = repo.primary / LEDGER_REL
        return rows_from_text(p.read_text()) if p.exists() else []

    def test_merged_refuses_a_plan_amended_on_the_target(self):
        repo, _forge, _squash = merged_change(self.tmp)
        _amend_the_target_plan(repo)

        r = repo.gates("acceptance", "attest", CHANGE, "--merged", "42", **NO_CI)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("approved_sha does not match", r.stderr)
        self.assertIn("Nothing was written", r.stderr)
        self.assertEqual(_acceptance_rows(self._ledger(repo)), [])

    def test_record_merged_records_the_merge_without_an_acceptance_and_fails(self):
        repo, _forge, squash = merged_change(self.tmp)
        _amend_the_target_plan(repo)
        before = git(repo.primary, "rev-parse", "HEAD")

        r = repo.gates("record-merged", squash, **NO_CI)

        self.assertNotEqual(r.returncode, 0, combined(r))
        self.assertIn("approved_sha does not match", r.stderr)
        self.assertIn(f"gates approval attest {CHANGE}", r.stderr)
        head = git(repo.primary, "rev-parse", "HEAD")
        self.assertNotEqual(head, before, "the merge row was not committed")
        archived = git(repo.primary, "ls-tree", "-r", "--name-only", head,
                       "--", "openspec/changes/archive", ".gatedloop/runs")
        ledger_paths = [p for p in archived.splitlines() if p.endswith(f"{CHANGE}.jsonl")]
        self.assertEqual(len(ledger_paths), 1, archived)
        rows = rows_from_text(git(repo.primary, "show", f"{head}:{ledger_paths[0]}"))
        self.assertTrue(any(x.get("gate") == "merge" and x.get("sha") == squash for x in rows),
                        json.dumps(rows, indent=1))
        self.assertEqual(_acceptance_rows(rows), [])


if __name__ == "__main__":
    unittest.main()
