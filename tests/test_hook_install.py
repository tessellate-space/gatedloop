"""Tests for `gates hook install` (enforce-at-the-effect §2, design D4).

Stdlib only, per `zero-dep-shim`. The install logic is exercised two ways:
black-box as a subprocess in throwaway git repos (matching how gates-init calls
it, and the way that catches a real clobber), and — for the pure doctor
sub-check (task 2.4) — by loading the shim by path and calling `_hook_state` /
`doctor_checks` on primitives (the house pattern in test_doctor.py; runs the
same with or without PyYAML).

Run with:  python3 -m unittest discover -s tests
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

_loader = importlib.machinery.SourceFileLoader("gates_shim", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_install(root):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), "hook", "install"],
        cwd=root, capture_output=True, text=True,
    )


def _init_repo(root):
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")


class TestInstallNothingPresent(unittest.TestCase):
    """Task 2.3: no hook and no manager → install the shipped template directly."""

    def test_installs_template_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            r = _run_install(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            hook = root / ".git" / "hooks" / "pre-commit"
            self.assertTrue(hook.exists())
            self.assertTrue(hook.stat().st_mode & 0o111, "hook must be executable")
            body = hook.read_text()
            self.assertIn("discipline check-commit", body)
            self.assertIn("CLAUDECODE", body, "must be env-scoped (design D2)")

    def test_idempotent_second_run_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            self.assertEqual(_run_install(root).returncode, 0)
            first = (root / ".git" / "hooks" / "pre-commit").read_text()
            r2 = _run_install(root)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertIn("already installed", r2.stdout)
            second = (root / ".git" / "hooks" / "pre-commit").read_text()
            self.assertEqual(first, second, "a second install must not rewrite the hook")


class TestComposeWithHusky(unittest.TestCase):
    """Task 2.2 / 2.5: a manager present → composes, preserving existing content."""

    def test_appends_to_existing_husky_hook_without_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            husky = root / ".husky"
            husky.mkdir()
            hook = husky / "pre-commit"
            hook.write_text("#!/usr/bin/env sh\necho existing-husky-step\n")

            r = _run_install(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            body = hook.read_text()
            self.assertIn("echo existing-husky-step", body, "existing content preserved")
            self.assertIn(gates.HOOK_BEGIN, body, "our block composed in")
            # A manager owns the hook path; do not also write .git/hooks/pre-commit.
            self.assertFalse((root / ".git" / "hooks" / "pre-commit").exists())

    def test_creates_husky_hook_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".husky").mkdir()  # manager present, no per-hook file yet
            r = _run_install(root)
            self.assertEqual(r.returncode, 0, r.stderr)
            hook = root / ".husky" / "pre-commit"
            self.assertTrue(hook.exists())
            self.assertIn(gates.HOOK_BEGIN, hook.read_text())

    def test_idempotent_compose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".husky").mkdir()
            self.assertEqual(_run_install(root).returncode, 0)
            after_first = (root / ".husky" / "pre-commit").read_text()
            r2 = _run_install(root)
            self.assertEqual(r2.returncode, 0)
            self.assertIn("already installed", r2.stdout)
            self.assertEqual(after_first, (root / ".husky" / "pre-commit").read_text())


class TestRefuseAndInstruct(unittest.TestCase):
    """Spec: an unclassifiable topology → refuse-and-instruct, never clobber."""

    def _assert_refuses_unchanged(self, root, guarded_file):
        before = guarded_file.read_text() if guarded_file.exists() else None
        r = _run_install(root)
        self.assertEqual(r.returncode, 1, "refuse must be a non-zero exit (fail-loud)")
        self.assertIn("refusing", r.stderr.lower())
        # The instruction prints the exact block to add by hand.
        self.assertIn(gates.HOOK_BEGIN, r.stderr)
        if before is not None:
            self.assertEqual(before, guarded_file.read_text(), "must not modify the existing hook")

    def test_bare_foreign_hook_is_not_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            hook = root / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/bin/sh\necho someone-elses-hook\nexit 0\n")
            hook.chmod(0o755)
            self._assert_refuses_unchanged(root, hook)

    def test_lefthook_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "lefthook.yml").write_text("pre-commit:\n  commands:\n    lint:\n      run: echo hi\n")
            self._assert_refuses_unchanged(root, root / "lefthook.yml")
            self.assertFalse((root / ".git" / "hooks" / "pre-commit").exists())

    def test_pre_commit_framework_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / ".pre-commit-config.yaml").write_text("repos: []\n")
            self._assert_refuses_unchanged(root, root / ".pre-commit-config.yaml")

    def test_custom_hookspath_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "myhooks").mkdir()
            _git(root, "config", "core.hooksPath", "myhooks")
            r = _run_install(root)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("refusing", r.stderr.lower())
            self.assertFalse((root / "myhooks" / "pre-commit").exists())


class TestHookOwnerDetection(unittest.TestCase):
    """The classification underpinning the branches above (pure, on real repos)."""

    def test_kinds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            self.assertEqual(gates._detect_hook_owner(root)[0], "none")
            (root / ".husky").mkdir()
            self.assertEqual(gates._detect_hook_owner(root)[0], "husky")

    def test_a_copy_of_the_pre_0_5_template_is_still_ours(self):
        """lock-and-ledger-hygiene D4 changed the template's check from
        `gate-marker check ci` to `discipline check-commit`. A copy installed
        before that still has the old body, and must read as our own stale
        copy (adoption-followups D1/D7) -- not as a foreign hook the installer
        refuses to touch."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            hook = root / ".git" / "hooks" / "pre-commit"
            hook.write_text(
                "#!/usr/bin/env bash\n"
                "# gatedloop git pre-commit hook (enforce-at-the-effect, design D1/D2).\n"
                'if marker_out="$("${GATES}" gate-marker check ci "${tree}" 2>&1)"; then\n'
                "  exit 0\nfi\nexit 1\n"
            )
            self.assertEqual(gates._hook_state(root), "stale-copy")


class TestDoctorHookSubCheck(unittest.TestCase):
    """Task 2.4: hook status ships as a `gates doctor` sub-check, not a verb.
    Exercised as a pure function on the state primitive."""

    def _titles(self, checks):
        return {title: level for level, title, _ in checks}

    def test_omitted_when_not_checked(self):
        checks = gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p", None)
        self.assertNotIn("git-commit-hook", self._titles(checks))

    def test_wired_is_ok(self):
        checks = gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p", "wired")
        self.assertEqual(self._titles(checks)["git-commit-hook"], "ok")

    def test_unwired_states_warn(self):
        for state in ("absent", "manager-uncomposed", "unmanaged-hook"):
            checks = gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p", state)
            self.assertEqual(
                self._titles(checks)["git-commit-hook"], "warn",
                f"state {state!r} should warn",
            )

    def test_hook_check_is_never_blocking(self):
        for state in (None, "wired", "absent", "manager-uncomposed", "unmanaged-hook"):
            for level, _t, _d in gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p", state):
                self.assertIn(level, ("ok", "warn"))

    def test_no_top_level_hook_status_verb(self):
        """The decision is explicit: no `gates hook status` verb — doctor owns it."""
        r = subprocess.run(
            [sys.executable, str(GATES_SHIM), "hook", "status"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(r.returncode, 0, "`hook status` must not be a valid verb")


if __name__ == "__main__":
    unittest.main()
