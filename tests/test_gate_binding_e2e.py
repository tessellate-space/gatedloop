"""Task 7.2 end-to-end check: the real `bin/gates` shim and the real
`hooks/gate-commit.sh` / `hooks/gate-merge.sh` scripts, in throwaway repos,
walked through each scenario in
`openspec/changes/fix-marker-mechanics/specs/gate-binding/spec.md` --
cross-referenced by scenario title in each test's docstring. This is the
closure check for `fix-marker-mechanics`, not incremental per-task coverage
(that already exists in `test_marker_normalization.py`,
`test_live_check_skip_verdict.py`, `test_live_check_dedupe.py`,
`test_merge_gate_incoming_tree.py`, and `test_ledger_grade_commit.py`) --
this file's job is to confirm the pieces compose through the REAL hook
scripts, not just the shim in isolation.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
MERGE_HOOK = REPO / "hooks" / "gate-merge.sh"
COMMIT_HOOK = REPO / "hooks" / "gate-commit.sh"

DOCS_ONLY_MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: code
    match: "src/**"
    live-check: "true"
"""

CODE_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _run_hook(hook: Path, root: Path, command: str):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(root)})
    return subprocess.run(
        ["bash", str(hook)], input=payload, cwd=str(root), env=env, capture_output=True, text=True,
    )


def _write_tree(root: Path) -> str:
    return subprocess.run(
        ["git", "write-tree"], cwd=root, capture_output=True, text=True,
    ).stdout.strip()


def _init_repo(root: Path, manifest: str) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class TestDocsOnlyChangeMergesAfterAnHonestSkip(unittest.TestCase):
    """Spec scenario "A docs-only diff can merge after an honest skip"
    (spec.md line 44): a change whose diff selects no surface with a
    `live-check` still merges, through the REAL merge hook, on a recorded
    skip verdict -- not a permanent deadlock."""

    def test_docs_only_branch_then_squash_merge_from_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, DOCS_ONLY_MANIFEST)
            _git(root, "checkout", "-b", "my-change")
            (root / "README.md").write_text("docs only\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "docs change")

            # scale-gate-cost D2: the merge also requires an unscoped `ci`
            # marker on the branch head (nothing staged -> scope "full").
            ci = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(ci.returncode, 0, ci.stderr)
            result = _run_gates(root, "run", "live-check", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("skipping", result.stdout)

            _git(root, "checkout", "main")
            r = _run_hook(MERGE_HOOK, root, "git merge --squash my-change")
            self.assertEqual(r.returncode, 0, r.stderr)

            # THEN also requires the report to name the skip and its
            # evidence (spec.md line 49) -- the hook itself is silent on
            # success, so check the underlying `gate-marker check` directly.
            branch_head_tree = _git(root, "rev-parse", "my-change^{tree}")
            direct = _run_gates(root, "gate-marker", "check", "live-check", branch_head_tree)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            self.assertIn("verdict=skip", direct.stdout)
            self.assertIn("baseline", direct.stdout.lower())


class TestNoLiveCheckAnywhereCanStillMerge(unittest.TestCase):
    """Spec scenario "A repo with no live-check declared anywhere can
    merge" (spec.md line 51)."""

    def test_squash_merge_allowed_with_no_live_check_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_MANIFEST)
            _git(root, "checkout", "-b", "my-change")
            (root / "app.py").write_text("print('hi')\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "code change")

            # scale-gate-cost D2: the merge also requires an unscoped `ci`
            # marker on the branch head (nothing staged -> scope "full").
            ci = _run_gates(root, "run", "ci", "--change", "my-change")
            self.assertEqual(ci.returncode, 0, ci.stderr)
            result = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)

            _git(root, "checkout", "main")
            r = _run_hook(MERGE_HOOK, root, "git merge --squash my-change")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestTaskCommitStagingItsOwnLedgerRowPassesTheRealCommitHook(unittest.TestCase):
    """Spec scenario "Staging the gate's own ledger row keeps the marker
    fresh" (spec.md line 13), exercised through the REAL `gate-commit.sh`
    hook rather than just `discipline check-commit` directly -- the exact
    shape a task commit takes (skills/tdd-apply/SKILL.md §5h): a green `ci`,
    then the task's files AND the ledger row `gates run` just appended,
    staged and committed together."""

    def test_real_commit_hook_allows_code_plus_its_own_ledger_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_MANIFEST)
            _git(root, "checkout", "-b", "my-change")

            (root / "app.py").write_text("print('hi')\n")
            _git(root, "add", "-A")
            r0 = _run_gates(root, "run", "ci", "--task", "1.1")
            self.assertEqual(r0.returncode, 0, r0.stderr)
            _git(root, "add", "-A")  # the task's files AND the fresh ledger row

            r = _run_hook(COMMIT_HOOK, root, "git commit -m 'task 1.1'")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestLedgerOnlyMergeRowCommitEarnsTheLedgerGrade(unittest.TestCase):
    """Spec scenario "Committing only the merge row" (spec.md line 114): the
    one `change -> squash SHA` row `gates ledger record-merge` appends is,
    by itself, a ledger-only staged diff -- allowed outright through the
    REAL commit hook, no fresh `ci` marker required."""

    def test_real_commit_hook_allows_the_merge_row_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_MANIFEST)
            _git(root, "checkout", "-b", "my-change")
            (root / "app.py").write_text("print('hi')\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task work")

            _git(root, "checkout", "main")
            _git(root, "merge", "--squash", "my-change")
            _git(root, "commit", "-m", "squash merge my-change")

            merge_result = _run_gates(root, "ledger", "record-merge", "my-change")
            self.assertEqual(merge_result.returncode, 0, merge_result.stderr)
            _git(root, "add", "-A")

            r = _run_hook(COMMIT_HOOK, root, "git commit -m 'record merge ledger row'")
            self.assertEqual(r.returncode, 0, r.stderr)

            # The hook itself is silent on success (it only echoes `gates`'
            # output on denial); the printed ledger-grade verdict (fail-
            # loud-gates) is visible on the direct `discipline check-commit`
            # call the hook makes under the hood.
            tree = _write_tree(root)
            direct = _run_gates(root, "discipline", "check-commit", tree)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            self.assertIn("ledger-grade", direct.stdout)


class TestCommittingTheLiveCheckLedgerRowDoesNotRestartTheChase(unittest.TestCase):
    """Spec scenario "Committing the merge ledger row does not restart the
    chase" (spec.md line 20): once a green `live-check` has written its
    marker, committing the run's OWN ledger row (a real commit, moving HEAD)
    must not stale that marker against the new HEAD tree -- the ledger-blind
    normalization (design D1) applies to `live-check` markers exactly as it
    does to `ci`'s."""

    def test_marker_survives_committing_its_own_ledger_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_MANIFEST)

            result = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)

            _git(root, "add", "-A")
            _git(root, "commit", "-m", "record the live-check ledger row")

            new_head_tree = _git(root, "rev-parse", "HEAD^{tree}")
            check = _run_gates(root, "gate-marker", "check", "live-check", new_head_tree)
            self.assertEqual(check.returncode, 0, check.stderr)


class TestStaleBranchMarkerStillDeniesTheSquashMerge(unittest.TestCase):
    """Spec scenario "A stale branch marker still denies" (spec.md line
    101): a real code commit AFTER the live-check marker was written moves
    the branch head past what was validated -- the merge gate must still
    deny, not silently accept the older, now-stale evidence."""

    def test_squash_merge_denied_after_a_later_unvalidated_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, CODE_MANIFEST)
            _git(root, "checkout", "-b", "my-change")
            (root / "app.py").write_text("print('hi')\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 1")

            result = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)

            # A further, unvalidated commit -- the marker is now stale.
            (root / "app.py").write_text("print('changed')\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 2, no fresh live-check")

            _git(root, "checkout", "main")
            r = _run_hook(MERGE_HOOK, root, "git merge --squash my-change")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("live-check", r.stderr)


if __name__ == "__main__":
    unittest.main()
