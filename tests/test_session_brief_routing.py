"""Tests for the session brief's approval-aware routing (design D4,
`solo-approval-mode`, task 4.1): an apply-ready change (artifacts written,
zero completed tasks) is split into "approved and ready to implement" —
which offers spawning the implementer as the default action — and "not yet
approved", which names the missing step instead.

Feeds `hooks/_session_brief.py` a synthesized `openspec list --json` payload
directly on stdin (never a real `openspec list` call — the routing logic
under test only cares what the payload says), against a real throwaway git
repo so `gates approval check <name>` (which the script shells out to) sees
real merged/approved or merged/unapproved state. Stdlib only, per
`zero-dep-shim`'s spirit for this test surface.

Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRIEF_HELPER = REPO / "hooks" / "_session_brief.py"
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST_SELF = """\
gatesVersion: 1
gates:
  ci: "true"
approval:
  plan: self
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _payload(change: str, completed: int, total: int) -> str:
    return json.dumps({
        "changes": [
            {"name": change, "status": "in-progress", "completedTasks": completed, "totalTasks": total},
        ],
    })


def _run_brief(root: Path, stdin_text: str) -> str:
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    proc = subprocess.run(
        [sys.executable, str(BRIEF_HELPER)],
        cwd=root, input=stdin_text, env=env, capture_output=True, text=True, timeout=30,
    )
    return proc.stdout


def _init_repo_with_change(root: Path, change: str = "my-change") -> Path:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST_SELF)
    change_dir = root / "openspec" / "changes" / change
    change_dir.mkdir(parents=True)
    (change_dir / "proposal.md").write_text("plan\n")
    (change_dir / "tasks.md").write_text("- [ ] 1.1 do a thing\n")
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "author plan")
    return change_dir


class TestApprovedAndUnimplementedIsRoutedToTheImplementer(unittest.TestCase):
    def test_approved_change_offers_spawning_the_implementer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo_with_change(root, "my-change")
            attest = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(attest.returncode, 0, attest.stderr)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "attest approval")

            out = _run_brief(root, _payload("my-change", 0, 3))
            self.assertIn("approved and ready to implement", out)
            self.assertIn("my-change", out)
            self.assertIn("spawn", out.lower())


class TestUnapprovedChangeNamesTheMissingStep(unittest.TestCase):
    def test_never_attested_change_names_the_gap_instead_of_offering_the_implementer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo_with_change(root, "my-change")

            out = _run_brief(root, _payload("my-change", 0, 3))
            self.assertIn("not yet approved", out)
            self.assertIn("my-change", out)
            self.assertNotIn("approved and ready to implement", out)

    def test_edited_after_attestation_also_names_the_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change_dir = _init_repo_with_change(root, "my-change")
            attest = _run_gates(root, "approval", "attest", "my-change", "--local")
            self.assertEqual(attest.returncode, 0, attest.stderr)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "attest approval")

            (change_dir / "proposal.md").write_text("a different plan\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "edit proposal after approval")

            out = _run_brief(root, _payload("my-change", 0, 3))
            self.assertIn("not yet approved", out)
            self.assertNotIn("approved and ready to implement", out)


class TestApprovedChangeOffersTheTestAuthorFirst(unittest.TestCase):
    """split-test-author design D6: under `separate`, an approved change with
    no handoff offers dispatching the test author before the implementer —
    which would otherwise halt `missing-oracle`. Regression guarded: the
    brief offering the implementer alone when it cannot yet succeed, or
    still offering the author once the tests are authored or inline."""

    def _approved(self, root, manifest=MANIFEST_SELF):
        _init_repo_with_change(root, "my-change")
        (root / ".gates.yaml").write_text(manifest)
        attest = _run_gates(root, "approval", "attest", "my-change", "--local")
        self.assertEqual(attest.returncode, 0, attest.stderr)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "attest approval")

    def _line(self, out):
        return next(ln for ln in out.splitlines() if "my-change" in ln)

    def test_separate_without_handoff_offers_the_author_then_the_implementer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._approved(root)
            line = self._line(_run_brief(root, _payload("my-change", 0, 3)))
        self.assertIn("dispatch test-author, then the implementer", line)

    def test_with_a_handoff_offers_the_implementer_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._approved(root)
            held = root / ".gatedloop" / "authored" / "my-change" / "1.1" / "NO-TESTS"
            held.parent.mkdir(parents=True)
            held.write_text("docs only\n")
            self.assertEqual(_run_gates(root, "tests", "handoff", "my-change").returncode, 0)
            line = self._line(_run_brief(root, _payload("my-change", 0, 3)))
        self.assertNotIn("test-author", line)
        self.assertIn("tdd-implementer", line)

    def test_inline_offers_the_implementer_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._approved(root, MANIFEST_SELF + "loop:\n  test-author: inline\n")
            line = self._line(_run_brief(root, _payload("my-change", 0, 3)))
        self.assertNotIn("test-author", line)
        self.assertIn("tdd-implementer", line)


if __name__ == "__main__":
    unittest.main()
