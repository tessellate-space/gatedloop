"""Declared propose-branch patterns (design D3 of `worktree-native-loop`).

The manifest may declare `discipline.propose-branches`, a list of fnmatch
globs accepted for proposal authoring alongside the merge target. Absent,
the accepted set is exactly today's (merge target + `plan/*`). Declaring the
block REPLACES the `plan/*` default rather than appending to it.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_propose_branches", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

BASE_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _git_ok(cwd, *args):
    r = _git(cwd, *args)
    assert r.returncode == 0, r.stderr
    return r


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path, manifest: str = BASE_MANIFEST) -> None:
    _git_ok(root, "init", "-b", "main")
    _git_ok(root, "config", "user.email", "t@example.com")
    _git_ok(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git_ok(root, "add", "-A")
    _git_ok(root, "commit", "-m", "init")


class TestManifestValidation(unittest.TestCase):
    def _validate(self, text: str) -> list[str]:
        parsed = gates._mini_yaml(text)
        with tempfile.TemporaryDirectory() as tmp:
            return gates._errors(parsed, Path(tmp))

    def test_absent_block_still_validates(self):
        self.assertEqual(self._validate(BASE_MANIFEST), [])

    def test_valid_declared_list_validates(self):
        text = BASE_MANIFEST + "discipline:\n  propose-branches:\n    - \"plan/*\"\n    - \"worktree/*\"\n"
        self.assertEqual(self._validate(text), [])

    def test_non_list_is_rejected(self):
        text = BASE_MANIFEST + "discipline:\n  propose-branches: \"plan/*\"\n"
        errs = self._validate(text)
        self.assertTrue(
            any("propose-branches" in e for e in errs), f"expected a propose-branches error, got: {errs}",
        )

    def test_empty_string_entry_is_rejected(self):
        text = BASE_MANIFEST + "discipline:\n  propose-branches:\n    - \"\"\n"
        errs = self._validate(text)
        self.assertTrue(
            any("propose-branches" in e for e in errs), f"expected a propose-branches error, got: {errs}",
        )

    def test_discipline_not_a_mapping_is_rejected(self):
        text = BASE_MANIFEST + "discipline: \"oops\"\n"
        errs = self._validate(text)
        self.assertTrue(
            any("discipline" in e for e in errs), f"expected a discipline error, got: {errs}",
        )


DECLARED_MANIFEST = (
    BASE_MANIFEST
    + "discipline:\n  propose-branches:\n    - \"worktree/*\"\n"
)


class TestDeclaredPatternAccepted(unittest.TestCase):
    def test_default_behavior_unchanged_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git_ok(root, "checkout", "-b", "plan/foo")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_declared_pattern_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, DECLARED_MANIFEST)
            _git_ok(root, "checkout", "-b", "worktree/lane-a")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_declaring_replaces_the_plan_default_not_appends(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, DECLARED_MANIFEST)
            _git_ok(root, "checkout", "-b", "plan/foo")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)

    def test_orphan_branch_matching_a_declared_pattern_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, DECLARED_MANIFEST)
            # An orphan history sharing no merge-base with main.
            _git_ok(root, "checkout", "--orphan", "worktree/orphan")
            _git_ok(root, "commit", "--allow-empty", "-m", "orphan root")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)

    def test_refusal_message_names_the_permitted_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, DECLARED_MANIFEST)
            _git_ok(root, "checkout", "-b", "some-other-branch")
            r = _run_gates(root, "discipline", "check-propose", "--scaffold")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("main", r.stderr)


if __name__ == "__main__":
    unittest.main()
