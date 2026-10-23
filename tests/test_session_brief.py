"""Regression tests for `hooks/session-brief.sh`'s third branch (§3,
`onboarding-asks-first`): the brief must distinguish "no OpenSpec", "OpenSpec
present but no gatedloop gate manifest", and "fully onboarded", and the two
pre-existing states must keep their exact generated text.

The selection logic lives in bash, not Python, so these tests exercise the
real script end-to-end (`bash hooks/session-brief.sh`, per CLAUDE.md) against
throwaway git repos, rather than re-implementing its branching in Python.

Stdlib only, per `zero-dep-shim`. `gates validate` already shells out to the
`openspec` CLI (F5), so this suite is an existing environmental dependency,
not a new one — it skips itself when the binary isn't on PATH rather than
turning an environment gap into a false failure.

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SESSION_BRIEF = REPO / "hooks" / "session-brief.sh"

GATES_MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n'
    '  ci: "true"\n'
    'surfaces:\n'
    '  - name: all\n'
    '    match: "**"\n'
)

LEGACY_MANIFEST = (
    'harnessVersion: 1\n'
    'gates:\n'
    '  ci: "true"\n'
    'surfaces:\n'
    '  - name: all\n'
    '    match: "**"\n'
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@contextlib.contextmanager
def scratch_repo():
    """A throwaway git repo with locally-scoped identity, independent of the
    host's global git config (matches tests/test_selection.py's fixture)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _git(root, "init", "-q", "-b", "main")
        _git(root, "config", "user.email", "test@example.com")
        _git(root, "config", "user.name", "Test")
        (root / "README.md").write_text("# scratch\n")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "initial")
        yield root


def _openspec_init(root: Path) -> None:
    subprocess.run(
        ["openspec", "init", "--tools", "claude", "--no-animation"],
        cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        check=True, timeout=60,
    )


def _add_manifest(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"add {name}")


def run_brief(root: Path) -> str:
    """Run the real script against `root`, return its additionalContext."""
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    proc = subprocess.run(
        ["bash", str(SESSION_BRIEF)],
        cwd=root, env=env, capture_output=True, text=True, timeout=30,
    )
    data = json.loads(proc.stdout)
    return data["hookSpecificOutput"]["additionalContext"]


@unittest.skipUnless(shutil.which("openspec"), "openspec CLI not on PATH")
class TestSessionBriefThreeStates(unittest.TestCase):
    """F6 / review 2026-08-18 finding 2: the brief had no branch for
    "OpenSpec present, no .gates.yaml" — the likely brownfield-adopter state —
    so it offered the full loop menu, every entry of which reads a manifest
    that does not exist."""

    def test_no_openspec_offers_onboarding_only(self):
        with scratch_repo() as root:
            ctx = run_brief(root)
        self.assertIn("no OpenSpec state", ctx)
        self.assertIn("/gatedloop:gates-init", ctx)
        self.assertNotIn("/gatedloop:archive", ctx)
        self.assertNotIn("gates run ci", ctx)

    def test_openspec_without_manifest_offers_gates_init_only(self):
        """The third branch this change adds: OpenSpec is set up, but no
        .gates.yaml exists yet — offer exactly one step, not the loop menu."""
        with scratch_repo() as root:
            _openspec_init(root)
            ctx = run_brief(root)
        self.assertIn("no gatedloop gate manifest", ctx)
        self.assertIn("/gatedloop:gates-init", ctx)
        self.assertNotIn("/gatedloop:archive", ctx)
        self.assertNotIn("gates run ci", ctx)

    def test_fully_onboarded_offers_the_loop_menu(self):
        with scratch_repo() as root:
            _openspec_init(root)
            _add_manifest(root, ".gates.yaml", GATES_MANIFEST)
            ctx = run_brief(root)
        self.assertIn("/gatedloop:archive", ctx)
        self.assertIn("gates run ci", ctx)
        self.assertNotIn("no gatedloop gate manifest", ctx)
        self.assertNotIn("no OpenSpec state", ctx)

    def test_legacy_harness_manifest_no_longer_counts_as_onboarded(self):
        """`remove-harness-compat` retired the one-release `.harness.yaml`
        fallback from `bin/gates`; the brief's detection must agree — a
        project that still only has the old filename is the same
        "no gatedloop gate manifest" state as one with no manifest at all,
        not the fully-onboarded state."""
        with scratch_repo() as root:
            _openspec_init(root)
            _add_manifest(root, ".harness.yaml", LEGACY_MANIFEST)
            ctx = run_brief(root)
        self.assertIn("no gatedloop gate manifest", ctx)
        self.assertNotIn("/gatedloop:archive", ctx)


if __name__ == "__main__":
    unittest.main()
