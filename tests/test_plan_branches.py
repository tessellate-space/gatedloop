"""D9 admits `plan/*` branches based on the merge target (design D3 of
`unblock-parallel-planning`, tasks 3.1-3.3). `gates discipline check-propose`
allows authoring on the merge target itself (existing behavior) or on a
`plan/*` branch that shares history with it; a stale plan branch (the
target has since moved ahead) is still allowed, with an advisory naming how
far behind it is -- refusing would block every long review's own
amendments. Since `hook-correctness` D5 this branch rule governs the
scaffold step; an artifact write off these branches is refused only when its
change is in implementation (`test_propose_gate_change_state.py`). `check-implement`'s change-branch gate must never mistake a
`plan/*` branch for a change branch.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _git_ok(cwd, *args):
    r = _git(cwd, *args)
    assert r.returncode == 0, r.stderr
    return r


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path) -> None:
    _git_ok(root, "init", "-b", "main")
    _git_ok(root, "config", "user.email", "t@example.com")
    _git_ok(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git_ok(root, "add", "-A")
    _git_ok(root, "commit", "-m", "init")


PROPOSAL_REL = "openspec/changes/foo/proposal.md"


class TestCheckProposeAdmitsMergeTarget(unittest.TestCase):
    def test_on_the_merge_target_itself_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)  # stays on main == merge target
            r = _run_gates(root, "discipline", "check-propose", PROPOSAL_REL)
            self.assertEqual(r.returncode, 0, r.stderr)


class TestCheckProposeAdmitsPlanBranches(unittest.TestCase):
    def test_plan_branch_based_on_target_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "plan/foo")
            r = _run_gates(root, "discipline", "check-propose", PROPOSAL_REL)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_stale_plan_branch_still_allowed_with_advisory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "plan/foo")
            # main moves ahead of the plan branch's base.
            _git_ok(root, "checkout", "main")
            (root / "other.txt").write_text("x\n")
            _git_ok(root, "add", "-A")
            _git_ok(root, "commit", "-m", "unrelated main progress")
            _git_ok(root, "checkout", "plan/foo")

            r = _run_gates(root, "discipline", "check-propose", PROPOSAL_REL)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("commit(s) behind", r.stdout)

    def test_plan_branch_with_unrelated_history_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "--orphan", "plan/foo")
            _git(root, "rm", "-rf", "--cached", ".")
            (root / "unrelated.txt").write_text("x\n")
            _git_ok(root, "add", "-A")
            _git_ok(root, "commit", "-m", "unrelated orphan history")

            # The branch rule now governs scaffolding a change; an artifact
            # write is judged on the change's state (hook-correctness D5).
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("plan/*", r.stderr)


class TestCheckProposeRefusesOtherBranches(unittest.TestCase):
    def test_ordinary_feature_branch_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "feature-x")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("design D9", r.stderr)


class TestCheckImplementNeverSeesAPlanBranch(unittest.TestCase):
    """Task 3.3: a `plan/<existing-change>` name never matches
    `openspec/changes/<existing-change>/` (the change dir is named just
    `<existing-change>`, never `plan/<existing-change>`), so
    `check-implement` treats it as an unknown, ordinary branch -- pass
    through, no D10 approval gate applied to it at all."""

    def test_plan_prefixed_branch_name_is_not_a_known_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            change_dir = root / "openspec" / "changes" / "existing-change"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            _git_ok(root, "add", "-A")
            _git_ok(root, "commit", "-m", "author plan directly on main")

            r = _run_gates(root, "discipline", "check-implement", "plan/existing-change")
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
