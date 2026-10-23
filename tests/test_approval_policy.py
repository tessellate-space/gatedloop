"""Tests for the declared plan-approval policy (design `solo-approval-mode`,
D1): `.gates.yaml`'s optional `approval` block and `gates validate`'s shape
check on it.

Stdlib only, per `zero-dep-shim`. Mirrors the subprocess-driven style of
`tests/test_approval.py` -- every case drives the real `bin/gates` shim
against a throwaway git repo, never imports its internals directly.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST_NO_APPROVAL = """\
gatesVersion: 1
gates:
  ci: "true"
"""

MANIFEST_SELF = """\
gatesVersion: 1
gates:
  ci: "true"
approval:
  plan: self
"""

MANIFEST_REVIEW = """\
gatesVersion: 1
gates:
  ci: "true"
approval:
  plan: review
"""

MANIFEST_INVALID = """\
gatesVersion: 1
gates:
  ci: "true"
approval:
  plan: yolo
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _make_change_repo(root: Path, manifest: str, change: str = "my-change") -> Path:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    change_dir = root / "openspec" / "changes" / change
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("plan\n")
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author plan")
    return change_dir


class TestPolicyResolution(unittest.TestCase):
    """Task 1.1: absent block -> review; `plan: self` -> self; invalid value
    -> `gates validate` errors naming the accepted values."""

    def test_absent_block_resolves_to_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_change_repo(root, MANIFEST_NO_APPROVAL)
            r = _run_gates(root, "approval", "policy")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "plan=review")

    def test_declared_self_resolves_to_self(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_change_repo(root, MANIFEST_SELF)
            r = _run_gates(root, "approval", "policy")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "plan=self")

    def test_declared_review_resolves_to_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_change_repo(root, MANIFEST_REVIEW)
            r = _run_gates(root, "approval", "policy")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "plan=review")

    def test_invalid_value_fails_validate_naming_accepted_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_change_repo(root, MANIFEST_INVALID)
            r = _run_gates(root, "validate")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("yolo", r.stderr)
            self.assertIn("review", r.stderr)
            self.assertIn("self", r.stderr)

    def test_valid_policies_pass_validate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_change_repo(root, MANIFEST_SELF)
            r = _run_gates(root, "validate")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestLocalAttestationUnderSelfPolicy(unittest.TestCase):
    """Task 2.1/2.2: `--local` under `self` writes keys with the D12 sha and
    the configured git identity; `--as` changes `approved_by` but never the
    sha; it reuses the exact same sha computation as `--pr` (one code path)."""

    def test_local_attest_writes_keys_with_git_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root, MANIFEST_SELF)

            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)

            data = (change_dir / ".openspec.yaml").read_text()
            self.assertIn('x-gatedloop-approved-by: "T <t@example.com>"', data)
            self.assertIn("x-gatedloop-approved-at:", data)
            self.assertIn("x-gatedloop-approved-sha:", data)

    def test_local_attest_sha_matches_the_pr_writers_computation(self):
        """D2: one code path for both writers -- `gates approval sha` (the
        same computation `--pr` uses) must equal what `--local` writes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root, MANIFEST_SELF)
            expected = _run_gates(root, "approval", "sha", "my-change").stdout.strip()

            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)
            data = (change_dir / ".openspec.yaml").read_text()
            self.assertIn(f'x-gatedloop-approved-sha: "{expected}"', data)

    def test_as_overrides_approved_by_but_never_the_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root, MANIFEST_SELF)
            expected_sha = _run_gates(root, "approval", "sha", "my-change").stdout.strip()

            r = _run_gates(root, "approval", "attest", "my-change", "--local", "--as", "Solo Dev")
            self.assertEqual(r.returncode, 0, r.stderr)
            data = (change_dir / ".openspec.yaml").read_text()
            self.assertIn('x-gatedloop-approved-by: "Solo Dev"', data)
            self.assertIn(f'x-gatedloop-approved-sha: "{expected_sha}"', data)

    def test_local_attest_appends_a_ledger_row(self):
        """Task 2.4: local attestation appends a durable ledger row,
        mirroring the shape other gate outcomes record (design Open
        Question, decided yes)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_change_repo(root, MANIFEST_SELF)
            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)

            ledger = root / ".gatedloop" / "runs" / "my-change.jsonl"
            self.assertTrue(ledger.exists())
            rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["gate"], "approval-local")
            self.assertEqual(rows[0]["change"], "my-change")
            self.assertEqual(rows[0]["exit"], 0)
            self.assertTrue(rows[0]["approved_by"])
            self.assertTrue(rows[0]["sha"])


class TestLocalAttestationRefusesUnderReviewPolicy(unittest.TestCase):
    """Task 2.1: under `review` (or the block absent), `--local` refuses and
    names the PR-based path -- never silently writes an unattested value."""

    def test_refuses_under_declared_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root, MANIFEST_REVIEW)
            before = (change_dir / ".openspec.yaml").read_text()

            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--pr", r.stderr)
            self.assertEqual((change_dir / ".openspec.yaml").read_text(), before)

    def test_refuses_when_block_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root, MANIFEST_NO_APPROVAL)
            before = (change_dir / ".openspec.yaml").read_text()

            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--pr", r.stderr)
            self.assertEqual((change_dir / ".openspec.yaml").read_text(), before)


class TestPostAttestationEditStillInvalidates(unittest.TestCase):
    """Task 2.3: a plan artifact edited after a `--local` attestation makes
    the recorded sha stale, and the D10 gate (`check-implement`) refuses --
    exactly as it does for a `--pr`-attested change."""

    def test_edit_after_local_attest_invalidates_check_implement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _make_change_repo(root, MANIFEST_SELF)

            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "attest approval")

            ok = _run_gates(root, "discipline", "check-implement", "my-change")
            self.assertEqual(ok.returncode, 0, ok.stderr)

            (change_dir / "proposal.md").write_text("a materially different plan\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "edit proposal after approval")

            stale = _run_gates(root, "discipline", "check-implement", "my-change")
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("edited after approval", stale.stderr)


def _load_shim():
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("gates_shim_acc_policy", str(GATES_SHIM))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _acceptance_manifest(acceptance: str, integration: str | None = None) -> str:
    text = MANIFEST_SELF + f"  acceptance: {acceptance}\n"
    if integration is not None:
        text += f"integration:\n  mode: {integration}\n"
    return text


class TestAcceptancePolicyDeclaration(unittest.TestCase):
    """acceptance-gate design D1: `approval.acceptance: review | self` is an
    optional key beside `plan`. Absent means no acceptance is required; any
    other value fails validate; `review` needs a pull request to review."""

    def _validate(self, manifest: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_change_repo(root, manifest)
            return _run_gates(root, "validate")

    def test_self_acceptance_beside_self_plan_validates(self):
        r = self._validate(_acceptance_manifest("self"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_invalid_acceptance_value_fails_naming_accepted_values(self):
        r = self._validate(_acceptance_manifest("nope"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("approval.acceptance", r.stderr)
        self.assertIn("nope", r.stderr)
        self.assertIn("'review'", r.stderr)
        self.assertIn("'self'", r.stderr)

    def _assert_review_conflict(self, r):
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("approval.acceptance", r.stderr)
        self.assertIn("pull request", r.stderr)
        # Both resolutions are named.
        self.assertIn("acceptance: self", r.stderr)
        self.assertIn("integration.mode: pull-request", r.stderr)

    def test_review_acceptance_without_integration_block_fails(self):
        self._assert_review_conflict(self._validate(_acceptance_manifest("review")))

    def test_review_acceptance_under_local_squash_merge_fails(self):
        self._assert_review_conflict(
            self._validate(_acceptance_manifest("review", "local-squash-merge"))
        )

    def test_review_acceptance_under_pull_request_validates(self):
        r = self._validate(_acceptance_manifest("review", "pull-request"))
        self.assertEqual(r.returncode, 0, r.stderr)


class TestAcceptancePolicyResolution(unittest.TestCase):
    """design D1: `_acceptance_policy(m)` is `None | "review" | "self"` --
    `None` whenever the key is undeclared (or the block is malformed, which
    is `gates validate`'s business), never a silent default policy."""

    @classmethod
    def setUpClass(cls):
        cls.gates = _load_shim()

    def test_undeclared_is_none(self):
        self.assertIsNone(self.gates._acceptance_policy({}))
        self.assertIsNone(self.gates._acceptance_policy({"approval": {"plan": "self"}}))

    def test_declared_values_resolve(self):
        self.assertEqual(
            self.gates._acceptance_policy({"approval": {"plan": "self", "acceptance": "self"}}),
            "self",
        )
        self.assertEqual(
            self.gates._acceptance_policy({"approval": {"plan": "self", "acceptance": "review"}}),
            "review",
        )

    def test_unrecognized_value_is_none(self):
        self.assertIsNone(
            self.gates._acceptance_policy({"approval": {"plan": "self", "acceptance": "yolo"}})
        )


if __name__ == "__main__":
    unittest.main()
