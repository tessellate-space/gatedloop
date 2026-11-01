"""Tests for the acceptance writers (acceptance-gate design D2, D3):
`gates acceptance attest <change> --local | --pr <n>` and `gates acceptance
reject <change> --cause <c> --detail <t>`.

An acceptance is one `acceptance` row in the change's ledger, pinned to the
ledger-normalized tree of the change branch's head, with `accepted_by` taken
from the configured git identity (`--local`, `reject`) or the pull request's
actual APPROVED review (`--pr`). The writers mirror plan approval's: the
policy in `approval.acceptance` decides which writer is legitimate, and with
no policy declared every writer refuses.

Stdlib only, per `zero-dep-shim`. `gh` is stubbed with a throwaway
executable placed first on the PATH handed to the subprocess -- the test
process's own `os.environ` is never modified, and no test touches a real
forge.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _approved_plan import write_approved_plan

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_acc_attest", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

BASE = """\
gatesVersion: 1
gates:
  ci: "true"
"""

MANIFEST_SELF = BASE + "approval:\n  plan: self\n  acceptance: self\n"
MANIFEST_REVIEW = (
    BASE
    + "approval:\n  plan: self\n  acceptance: review\n"
    + "integration:\n  mode: pull-request\n"
)
MANIFEST_NONE = BASE + "approval:\n  plan: self\n"

FAKE_GH_APPROVED = """\
#!/usr/bin/env bash
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  echo '{"reviews":[{"state":"COMMENTED","author":{"login":"someone"},"submittedAt":"2026-09-20T10:00:00Z"},{"state":"APPROVED","author":{"login":"product-owner"},"submittedAt":"2026-09-21T09:30:00Z"}]}'
  exit 0
fi
exit 1
"""

FAKE_GH_NO_APPROVAL = """\
#!/usr/bin/env bash
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  echo '{"reviews":[{"state":"COMMENTED","author":{"login":"someone"},"submittedAt":"2026-09-20T10:00:00Z"}]}'
  exit 0
fi
exit 1
"""

NO_GH_PATH = "/usr/bin:/bin"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_gates(root, *args, path=None):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True, env=env,
    )


def _stub_gh_path(bindir: Path, script: str) -> str:
    """A PATH value with a stub `gh` first. Only ever passed to the
    subprocess's own environment, so the caller's PATH is untouched."""
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(script)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


def _make_branch_repo(root: Path, manifest: str, change: str = "my-change") -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    # An acceptance is refused for a plan that is not the approved one
    # (loop-hardening D2), so the plan lands on main with its approval.
    write_approved_plan(root, change)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", change)
    (root / "feature.txt").write_text("the increment\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "task work")


def _ledger_rows(root: Path, change: str = "my-change") -> list[dict]:
    p = root / ".gatedloop" / "runs" / f"{change}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _acceptance_rows(root: Path) -> list[dict]:
    return [r for r in _ledger_rows(root) if r.get("gate") == "acceptance"]


def _normalized_head(root: Path) -> str:
    return gates._normalize_tree(root, _git(root, "rev-parse", "HEAD^{tree}"))


class TestLocalAttestation(unittest.TestCase):
    """Task 2.2: `--local` under `acceptance: self`."""

    def test_local_attest_appends_one_accept_row_pinned_to_the_head_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)

            r = _run_gates(root, "acceptance", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)

            rows = _acceptance_rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["verdict"], "accept")
            self.assertEqual(rows[0]["tree"], _normalized_head(root))
            self.assertEqual(rows[0]["accepted_by"], "T <t@example.com>")
            self.assertEqual(rows[0]["change"], "my-change")

    def test_local_attest_changes_no_tracked_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)
            before = _git(root, "rev-parse", "HEAD^{tree}")

            r = _run_gates(root, "acceptance", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)

            self.assertEqual(_git(root, "diff", "--name-only", "HEAD"), "")
            self.assertEqual(_git(root, "rev-parse", "HEAD^{tree}"), before)

    def test_local_attest_refuses_under_review_naming_pr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_REVIEW)

            r = _run_gates(root, "acceptance", "attest", "my-change", "--local")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--pr", r.stderr)
            self.assertEqual(_acceptance_rows(root), [])

    def test_as_changes_only_accepted_by(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)

            r = _run_gates(root, "acceptance", "attest", "my-change", "--local", "--as", "Solo Dev")
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = _acceptance_rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["accepted_by"], "Solo Dev")
            self.assertEqual(rows[0]["tree"], _normalized_head(root))


class TestWritersRefuseWithNoPolicy(unittest.TestCase):
    """Task 2.2: with no `approval.acceptance`, every acceptance writer
    refuses, writes nothing, and names the key to declare."""

    def test_local_refuses_naming_the_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_NONE)
            r = _run_gates(root, "acceptance", "attest", "my-change", "--local")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("approval.acceptance", r.stderr)
            self.assertEqual(_ledger_rows(root), [])

    def test_pr_refuses_naming_the_key(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_NONE)
            path = _stub_gh_path(Path(bin_tmp), FAKE_GH_APPROVED)
            r = _run_gates(root, "acceptance", "attest", "my-change", "--pr", "7", path=path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("approval.acceptance", r.stderr)
            self.assertEqual(_ledger_rows(root), [])

    def test_reject_refuses_naming_the_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_NONE)
            r = _run_gates(
                root, "acceptance", "reject", "my-change",
                "--cause", "weak-spec", "--detail", "not what was meant",
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("approval.acceptance", r.stderr)
            self.assertEqual(_ledger_rows(root), [])


class TestPrAttestation(unittest.TestCase):
    """Task 2.3: `--pr <n>` reads the pull request's actual APPROVED review
    and fails closed on anything less."""

    def test_approved_review_appends_accept_row_with_review_author(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_REVIEW)
            path = _stub_gh_path(Path(bin_tmp), FAKE_GH_APPROVED)

            r = _run_gates(root, "acceptance", "attest", "my-change", "--pr", "7", path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = _acceptance_rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["verdict"], "accept")
            self.assertEqual(rows[0]["accepted_by"], "product-owner")
            self.assertEqual(rows[0]["ts"], "2026-09-21T09:30:00Z")
            self.assertEqual(rows[0]["tree"], _normalized_head(root))

    def test_pr_is_legitimate_under_self_too(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)
            path = _stub_gh_path(Path(bin_tmp), FAKE_GH_APPROVED)

            r = _run_gates(root, "acceptance", "attest", "my-change", "--pr", "7", path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_acceptance_rows(root)[0]["accepted_by"], "product-owner")

    def test_no_approving_review_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_REVIEW)
            path = _stub_gh_path(Path(bin_tmp), FAKE_GH_NO_APPROVAL)

            r = _run_gates(root, "acceptance", "attest", "my-change", "--pr", "7", path=path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("not accepted", r.stderr)
            self.assertEqual(_ledger_rows(root), [])

    def test_missing_gh_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_REVIEW)

            r = _run_gates(root, "acceptance", "attest", "my-change", "--pr", "7", path=NO_GH_PATH)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("gh", r.stderr)
            self.assertEqual(_ledger_rows(root), [])

    def test_pr_with_as_refuses(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_REVIEW)
            path = _stub_gh_path(Path(bin_tmp), FAKE_GH_APPROVED)

            r = _run_gates(
                root, "acceptance", "attest", "my-change", "--pr", "7", "--as", "Someone",
                path=path,
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("review", r.stderr)
            self.assertEqual(_ledger_rows(root), [])


class TestReject(unittest.TestCase):
    """Task 2.4: a rejection is an escalation with one of two causes."""

    def test_reject_appends_row_with_cause_detail_and_head_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)

            r = _run_gates(
                root, "acceptance", "reject", "my-change",
                "--cause", "weak-spec", "--detail", "t",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = _acceptance_rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["verdict"], "reject")
            self.assertEqual(rows[0]["cause"], "weak-spec")
            self.assertEqual(rows[0]["detail"], "t")
            self.assertEqual(rows[0]["tree"], _normalized_head(root))
            self.assertEqual(rows[0]["accepted_by"], "T <t@example.com>")

    def test_other_cause_is_refused_naming_the_two_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)

            r = _run_gates(
                root, "acceptance", "reject", "my-change",
                "--cause", "stalled", "--detail", "t",
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("weak-spec", r.stderr)
            self.assertIn("missing-oracle", r.stderr)
            self.assertEqual(_ledger_rows(root), [])

    def test_empty_detail_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_branch_repo(root, MANIFEST_SELF)

            r = _run_gates(
                root, "acceptance", "reject", "my-change",
                "--cause", "missing-oracle", "--detail", "  ",
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--detail", r.stderr)
            self.assertEqual(_ledger_rows(root), [])


class TestPolicyCommand(unittest.TestCase):
    """Task 2.5: `gates acceptance policy` prints the declared policy in a
    shape a prompt can branch on (design D6), `none` when undeclared."""

    def test_prints_each_policy(self):
        for manifest, expected in (
            (MANIFEST_SELF, "acceptance=self"),
            (MANIFEST_REVIEW, "acceptance=review"),
            (MANIFEST_NONE, "acceptance=none"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _make_branch_repo(root, manifest)
                r = _run_gates(root, "acceptance", "policy")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
