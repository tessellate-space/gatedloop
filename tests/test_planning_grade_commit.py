"""Planning-grade commit gate (design D2 of `unblock-parallel-planning`,
tasks 2.1/2.4). A staged diff that touches only planning files -- the
OpenSpec planning home (`openspec/`) plus the manifest's declared
`conventions.rules-doc` -- is satisfied by manifest + OpenSpec artifact
validation instead of a green `ci` marker; anything else keeps the full
`ci` marker requirement, unchanged.

Two layers: pure-function classification tests (in-process, via the same
by-path module load `test_selection.py` uses, since `bin/gates` has no `.py`
suffix), and `gates discipline check-commit <tree>` end-to-end tests in
throwaway git repos with a real staged index. `openspec` itself is faked on
PATH (same technique `test_approval.py` uses for `gh`) so these stay
hermetic and fast -- the shim's OWN classification and dispatch is what's
under test, not OpenSpec's validator.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_planning_grade", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

MANIFEST_WITH_RULES_DOC = (
    'gatesVersion: 1\n'
    'gates:\n  ci: "true"\n'
    'conventions:\n  rules-doc: docs/conventions.md\n'
)
MANIFEST_NO_RULES_DOC = 'gatesVersion: 1\ngates:\n  ci: "true"\n'

FAKE_OPENSPEC_VALID = """\
#!/usr/bin/env bash
if [ "$1" = "validate" ]; then
  echo '{"items":[{"id":"'"$2"'","type":"change","valid":true,"issues":[]}]}'
  exit 0
fi
exit 1
"""

FAKE_OPENSPEC_INVALID = """\
#!/usr/bin/env bash
if [ "$1" = "validate" ]; then
  echo 'validation failed: missing tasks.md' >&2
  exit 1
fi
exit 1
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args, path=None):
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True, env=env,
    )


def _install_fake_openspec(bindir: Path, script: str) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    exe = bindir / "openspec"
    exe.write_text(script)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"


def _init_repo(root: Path, manifest: str = MANIFEST_NO_RULES_DOC) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class TestIsPlanningPath(unittest.TestCase):
    def test_under_openspec_home_is_planning(self):
        self.assertTrue(gates._is_planning_path("openspec/changes/foo/proposal.md", {}))

    def test_declared_rules_doc_is_planning(self):
        m = {"conventions": {"rules-doc": "docs/conventions.md"}}
        self.assertTrue(gates._is_planning_path("docs/conventions.md", m))

    def test_undeclared_rules_doc_path_is_not_special(self):
        self.assertFalse(gates._is_planning_path("docs/conventions.md", {}))

    def test_code_path_is_not_planning(self):
        self.assertFalse(gates._is_planning_path("bin/gates", {}))

    def test_similarly_prefixed_non_planning_path_is_not_fooled(self):
        # "openspec-notes.md" starts with "openspec" but is not under the
        # openspec/ home -- the startswith check must require the slash.
        self.assertFalse(gates._is_planning_path("openspec-notes.md", {}))


class TestStagedChangeDirs(unittest.TestCase):
    def test_extracts_distinct_change_names_in_order(self):
        staged = [
            "openspec/changes/foo/proposal.md",
            "openspec/changes/foo/tasks.md",
            "openspec/changes/bar/design.md",
            "docs/conventions.md",
        ]
        self.assertEqual(gates._staged_change_dirs(staged), ["foo", "bar"])

    def test_empty_when_no_change_paths(self):
        self.assertEqual(gates._staged_change_dirs(["docs/conventions.md", "bin/gates"]), [])

    def test_reserved_archive_segment_never_yields_a_change_id(self):
        """`archive` under openspec/changes/ is the reserved namespace for
        archived changes, never itself a change id to validate (design D4
        of `harden-hook-matching`)."""
        staged = [
            "openspec/changes/archive/2026-01-01-foo/proposal.md",
            "openspec/changes/archive/2026-01-01-foo/tasks.md",
        ]
        self.assertEqual(gates._staged_change_dirs(staged), [])

    def test_reserved_archive_segment_does_not_shadow_a_real_change_id(self):
        staged = [
            "openspec/changes/archive/2026-01-01-foo/proposal.md",
            "openspec/changes/bar/design.md",
        ]
        self.assertEqual(gates._staged_change_dirs(staged), ["bar"])


class TestCheckCommitClassification(unittest.TestCase):
    """`gates discipline check-commit <tree>` end-to-end, task 2.1/2.4."""

    def test_planning_only_diff_valid_change_allowed_with_no_ci_marker(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            change_dir = root / "openspec" / "changes" / "foo"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            # Delta content (design D4, worktree-native-loop): this test is
            # about the full-validate path, so the change needs a specs/
            # file to classify that way -- a proposal-only change is task
            # 4.1/4.2's own scope.
            (change_dir / "specs").mkdir()
            (change_dir / "specs" / "spec.md").write_text("delta\n")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_VALID)

            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree, path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("ci' marker", r.stdout + r.stderr)

    def test_planning_only_including_declared_rules_doc_allowed(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root, manifest=MANIFEST_WITH_RULES_DOC)
            docs = root / "docs"
            docs.mkdir()
            (docs / "conventions.md").write_text("### a-rule\nApplies to: code\nRule: do the thing.\n")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_VALID)

            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree, path=path)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_planning_only_with_invalid_artifact_denied(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            change_dir = root / "openspec" / "changes" / "foo"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            # Delta content (design D4): this test wants the full-validate
            # path to run and fail, which now requires delta content --
            # otherwise the change classifies as proposal-only instead.
            (change_dir / "specs").mkdir()
            (change_dir / "specs" / "spec.md").write_text("delta\n")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_INVALID)

            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree, path=path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("openspec validate", r.stderr)

    def test_mixed_diff_still_requires_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            change_dir = root / "openspec" / "changes" / "foo"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            (root / "app.py").write_text("print('hi')\n")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_VALID)

            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree, path=path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("ci' marker", r.stderr)

    def test_mixed_diff_allowed_once_ci_marker_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            change_dir = root / "openspec" / "changes" / "foo"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            (root / "app.py").write_text("print('hi')\n")
            _git(root, "add", "-A")
            r0 = _run_gates(root, "run", "ci")
            self.assertEqual(r0.returncode, 0, r0.stderr)

            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_empty_staged_diff_is_not_treated_as_planning_only(self):
        """Zero evidence is never a free pass (design D2): an empty staged
        diff (nothing new since the last commit) still falls through to the
        unchanged marker requirement, not a vacuous planning-grade allow."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("ci' marker", r.stderr)

    def test_empty_staged_diff_allowed_once_ci_marker_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            r0 = _run_gates(root, "run", "ci")
            self.assertEqual(r0.returncode, 0, r0.stderr)
            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree)
            self.assertEqual(r.returncode, 0, r.stderr)


# A fake `openspec validate` that FAILS if ever invoked for the literal
# `archive` segment or for a change id whose directory the staged diff has
# just moved away -- so a wrongly-attempted validate call (rather than a
# vacuous "always succeeds" fake) is what would fail these tests (design D4,
# task 3.1).
FAKE_OPENSPEC_FAIL_ON_ARCHIVE_OR_MOVED = """\
#!/usr/bin/env bash
if [ "$1" = "validate" ]; then
  case "$2" in
    archive|foo)
      echo "should never be validated: $2" >&2
      exit 1
      ;;
  esac
  echo '{"items":[{"id":"'"$2"'","type":"change","valid":true,"issues":[]}]}'
  exit 0
fi
exit 1
"""


class TestArchiveMoveClassification(unittest.TestCase):
    """Archive-move commits classify at planning grade without ever
    attempting `openspec validate` against the reserved `archive` segment or
    a change directory the move has removed from the working tree (design
    D4, tasks 3.1/3.2)."""

    def test_pure_archive_move_allowed_without_validating_archive_or_the_moved_away_dir(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            change_dir = root / "openspec" / "changes" / "foo"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "add foo change")

            # Simulate `openspec archive foo`: move the directory under
            # openspec/changes/archive/<dated>/. The archived copy's content
            # is written distinctly (an "archived" marker) so git's default
            # rename-similarity detection does NOT pair it back to the old
            # path -- both the deletion at the old path and the addition at
            # the new one land as their own entries in the staged diff,
            # exactly what a real `openspec archive` move (which typically
            # touches at least one file, e.g. `.openspec.yaml`) produces.
            archived_dir = root / "openspec" / "changes" / "archive" / "2026-01-01-foo"
            archived_dir.mkdir(parents=True)
            (archived_dir / "proposal.md").write_text("archived plan, formerly foo\n")
            shutil.rmtree(change_dir)
            _git(root, "add", "-A")

            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_FAIL_ON_ARCHIVE_OR_MOVED)
            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree, path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("should never be validated", r.stdout + r.stderr)
            # The allow message announces what was skipped and why
            # (fail-loud in both directions -- design D4).
            self.assertIn("skip", (r.stdout + r.stderr).lower())
            self.assertIn("foo", r.stdout + r.stderr)

    def test_archive_move_alongside_a_still_present_change_validates_only_the_present_one(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            foo_dir = root / "openspec" / "changes" / "foo"
            foo_dir.mkdir(parents=True)
            (foo_dir / "proposal.md").write_text("plan\n")
            bar_dir = root / "openspec" / "changes" / "bar"
            bar_dir.mkdir(parents=True)
            (bar_dir / "proposal.md").write_text("plan\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "add foo and bar")

            archived_dir = root / "openspec" / "changes" / "archive" / "2026-01-01-foo"
            archived_dir.mkdir(parents=True)
            (archived_dir / "proposal.md").write_text("archived plan, formerly foo\n")
            shutil.rmtree(foo_dir)
            (bar_dir / "design.md").write_text("more plan\n")
            # Delta content (design D4): "bar" needs to classify as fully
            # validated (not proposal-only) for this test's fake openspec,
            # which only implements `validate`, to be the one that decides
            # the outcome.
            (bar_dir / "specs").mkdir()
            (bar_dir / "specs" / "spec.md").write_text("delta\n")
            _git(root, "add", "-A")

            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_FAIL_ON_ARCHIVE_OR_MOVED)
            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree, path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("should never be validated", r.stdout + r.stderr)

    def test_still_present_change_dir_is_validated_exactly_as_before(self):
        """A change dir that still exists on disk validates unconditionally
        -- this classification fix changes nothing about that path."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _init_repo(root)
            change_dir = root / "openspec" / "changes" / "foo"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            # Delta content (design D4): "validated unconditionally" here
            # means the full-validate path, which now requires delta
            # content to select it over the proposal-only path.
            (change_dir / "specs").mkdir()
            (change_dir / "specs" / "spec.md").write_text("delta\n")
            _git(root, "add", "-A")
            path = _install_fake_openspec(Path(bin_tmp), FAKE_OPENSPEC_INVALID)

            tree = subprocess.run(
                ["git", "write-tree"], cwd=root, capture_output=True, text=True,
            ).stdout.strip()
            r = _run_gates(root, "discipline", "check-commit", tree, path=path)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("openspec validate", r.stderr)


if __name__ == "__main__":
    unittest.main()
