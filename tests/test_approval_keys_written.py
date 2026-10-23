"""The attestation writer uses the `x-` spelling (openspec change
`openspec-1-14-compat`, design D1/D2; scenario "Attesting writes the new
keys").

`_write_approval_keys` writes `x-gatedloop-approved-by|at|sha` and removes any
0.5.0-spelled key in the same file, so a re-attest migrates as a side effect.
One test runs the real `openspec validate --strict` and skips when the CLI is
not on PATH: what is under test there is that OpenSpec itself accepts the
file, which no fake can tell us.

Stdlib only, per `zero-dep-shim`. Every repository is a throwaway one.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST_SELF = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'
OLD_KEYS = ("approved_by", "approved_at", "approved_sha")
NEW_KEYS = ("x-gatedloop-approved-by", "x-gatedloop-approved-at", "x-gatedloop-approved-sha")

PROPOSAL = ("## Why\n\nBecause a reason that is long enough to pass the validator's checks.\n\n"
            "## What Changes\n\n- A thing changes.\n")
SPEC = ("## ADDED Requirements\n\n### Requirement: A thing\n\nThe system SHALL do a thing.\n\n"
        "#### Scenario: It does\n\n- **WHEN** asked\n- **THEN** it does\n")


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    env["OPEN_SPEC_INTERACTIVE"] = "0"
    return env


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=_env())


def _run_gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def _repo(root: Path, openspec_yaml: str) -> Path:
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST_SELF)
    change_dir = root / "openspec" / "changes" / "my-change"
    (change_dir / "specs" / "cap").mkdir(parents=True)
    (change_dir / "proposal.md").write_text(PROPOSAL)
    (change_dir / "specs" / "cap" / "spec.md").write_text(SPEC)
    (change_dir / ".openspec.yaml").write_text(openspec_yaml)
    return change_dir


def _top_keys(text: str) -> list[str]:
    return [line.split(":", 1)[0] for line in text.splitlines()
            if line and not line[0].isspace() and ":" in line]


OLD_SPELLED = ("schema: spec-driven\ncreated: 2026-08-19\napproved_by: Old\n"
               "approved_at: 2026-08-19T09:30:00+00:00\napproved_sha: " + "0" * 64 + "\n")


class TestWriterSpelling(unittest.TestCase):
    def test_fresh_attest_writes_only_the_new_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _repo(root, "schema: spec-driven\ncreated: 2026-08-19\n")
            expected = _run_gates(root, "approval", "sha", "my-change").stdout.strip()

            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)
            text = (change_dir / ".openspec.yaml").read_text()
            keys = _top_keys(text)
            for key in NEW_KEYS:
                self.assertIn(key, keys)
            for key in OLD_KEYS:
                self.assertNotIn(key, keys)
            self.assertIn('x-gatedloop-approved-by: "T <t@example.com>"', text)
            self.assertIn(f'x-gatedloop-approved-sha: "{expected}"', text)

    def test_reattest_removes_the_old_spelling_and_keeps_other_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _repo(root, OLD_SPELLED)

            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)
            text = (change_dir / ".openspec.yaml").read_text()
            keys = _top_keys(text)
            self.assertEqual(keys.count("schema"), 1)
            self.assertEqual(keys.count("created"), 1)
            for key in NEW_KEYS:
                self.assertEqual(keys.count(key), 1, text)
            for key in OLD_KEYS:
                self.assertNotIn(key, keys, text)
            self.assertNotIn("Old", text)

    def test_the_new_attestation_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root, OLD_SPELLED)
            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "plan, approved")
            r = _run_gates(root, "approval", "check", "my-change")
            self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipIf(shutil.which("openspec") is None, "the OpenSpec CLI is not on PATH")
class TestRealOpenSpecStrict(unittest.TestCase):
    """Scenario "Attesting writes the new keys": OpenSpec 1.14 itself reports
    no unrecognized key, and `--strict` passes."""

    def test_attested_change_passes_strict_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root, OLD_SPELLED)
            r = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(r.returncode, 0, r.stderr)

            v = subprocess.run(["openspec", "validate", "my-change", "--strict"], cwd=root,
                               capture_output=True, text=True, env=_env(), timeout=120)
            out = v.stdout + v.stderr
            self.assertEqual(v.returncode, 0, out)
            self.assertNotIn("Unrecognized key", out)


if __name__ == "__main__":
    unittest.main()
