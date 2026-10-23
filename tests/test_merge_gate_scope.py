"""The merge hook guards integration only (design D2 of `hook-correctness`,
#33 item 2).

Syncing the integration target into a change branch (`git merge main` on
`my-change`) was gated as if it were integrating the change: the hook looked
for a live-check marker on `main`'s tree, which no loop ever records, so the
merge could never be satisfied and a lane halted on it. The hook now exits 0
before any marker work unless the checkout it runs in IS the integration
target -- the target branch itself, or a detached HEAD sitting at its tip
(the merge recipe's detach onto the target).

Change-into-main staying gated is covered by
`test_merge_gate_incoming_tree.TestSquashMergeChecksSourceBranchTree`.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MERGE_HOOK = REPO / "hooks" / "gate-merge.sh"

MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: all
    match: "**"
    live-check: "true"
"""


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_hook(root: Path, command: str):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(root)})
    return subprocess.run(
        ["bash", str(MERGE_HOOK)], input=payload, cwd=str(root), env=env,
        capture_output=True, text=True,
    )


def _repo_with_two_branches(root: Path) -> None:
    """`main` plus two change branches, none carrying any gate marker."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    for name in ("my-change", "other-change"):
        _git(root, "checkout", "-b", name, "main")
        (root / f"{name}.txt").write_text(name)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", name)
    _git(root, "checkout", "main")
    (root / "later.txt").write_text("main moved on")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "main moves")


class TestNonIntegrationMergesPassWithoutMarkers(unittest.TestCase):
    def test_syncing_main_into_a_change_branch_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo_with_two_branches(root)
            _git(root, "checkout", "my-change")
            r = _run_hook(root, "git merge main")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_merging_one_change_branch_into_another_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo_with_two_branches(root)
            _git(root, "checkout", "other-change")
            r = _run_hook(root, "git merge my-change 2>&1")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_detached_head_away_from_the_target_tip_is_not_integrating(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo_with_two_branches(root)
            _git(root, "checkout", "--detach", "my-change")
            r = _run_hook(root, "git merge --squash other-change")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestASwitchBeforeTheMergeKeepsItGated(unittest.TestCase):
    """The hook sees the checkout as it is BEFORE the command runs. A command
    that switches to the target and then merges would otherwise be judged
    from the change branch and skip every check."""

    def test_checkout_then_merge_in_one_command_is_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo_with_two_branches(root)
            _git(root, "checkout", "my-change")
            r = _run_hook(root, "git checkout main && git merge --squash my-change")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("live-check", r.stderr)


class TestDetachedAtTheTargetTipIsIntegrating(unittest.TestCase):
    def test_merge_from_a_detached_head_at_the_target_tip_is_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo_with_two_branches(root)
            _git(root, "checkout", "--detach", "main")
            r = _run_hook(root, "git merge --squash my-change")
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("live-check", r.stderr)


if __name__ == "__main__":
    unittest.main()
