"""`gates approval migrate [<change>]` and doctor's `approval-keys` row
(openspec change `openspec-1-14-compat`, design D3/D4; requirement
"Old-spelled approval keys can be migrated and are diagnosed").

Migrate renames the 0.5.0 approval keys to the `x-gatedloop-` spelling in each
active change's `.openspec.yaml`, keeping values and order, and never touches
an archived change. The approval sha covers no `.openspec.yaml`, so a
migrated approval still checks. Doctor warns, naming the change and the
command; like every doctor row it is advisory.

Stdlib only, per `zero-dep-shim`. Every repository is a throwaway one, and
`openspec` is faked on PATH for the doctor run so it never depends on the
host's CLI.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_approval_migrate", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

MANIFEST_SELF = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'
FAKE_OPENSPEC = '#!/usr/bin/env bash\nif [ "$1" = "--version" ]; then echo 1.14.3; exit 0; fi\nexit 1\n'


def _env(path: str | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    if path is not None:
        env["PATH"] = path
    return env


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=_env())


def _run_gates(root, *args, path=None):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(path), timeout=120)


def _repo(root: Path) -> None:
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST_SELF)


def _change(root: Path, name: str, keys: str = "", archived: bool = False) -> Path:
    base = root / "openspec" / "changes"
    d = base / "archive" / f"2026-01-01-{name}" if archived else base / name
    d.mkdir(parents=True)
    (d / "proposal.md").write_text(f"plan for {name}\n")
    (d / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n" + keys)
    return d / ".openspec.yaml"


def _old(sha: str = "a" * 64) -> str:
    return ("approved_by: Old <o@example.com>\napproved_at: 2026-08-19T09:30:00+00:00\n"
            f"approved_sha: {sha}\n")


def _new_of(old_text: str) -> str:
    return (old_text.replace("approved_by:", "x-gatedloop-approved-by:")
            .replace("approved_at:", "x-gatedloop-approved-at:")
            .replace("approved_sha:", "x-gatedloop-approved-sha:"))


class TestMigrate(unittest.TestCase):
    def test_renames_old_keys_keeping_values_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root)
            path = _change(root, "alpha", _old())
            before = path.read_text()

            r = _run_gates(root, "approval", "migrate")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(path.read_text(), _new_of(before))
            self.assertIn("alpha", r.stdout)

    def test_every_active_change_is_migrated_and_archived_ones_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root)
            alpha = _change(root, "alpha", _old())
            beta = _change(root, "beta", _old("b" * 64))
            done = _change(root, "gamma", _old(), archived=True)
            archived_before = done.read_text()

            r = _run_gates(root, "approval", "migrate")
            self.assertEqual(r.returncode, 0, r.stderr)
            for p in (alpha, beta):
                self.assertNotIn("\napproved_", "\n" + p.read_text())
                self.assertIn("x-gatedloop-approved-sha:", p.read_text())
            self.assertEqual(done.read_text(), archived_before)

    def test_a_named_change_is_the_only_one_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root)
            alpha = _change(root, "alpha", _old())
            beta = _change(root, "beta", _old())
            beta_before = beta.read_text()

            r = _run_gates(root, "approval", "migrate", "alpha")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("x-gatedloop-approved-by:", alpha.read_text())
            self.assertEqual(beta.read_text(), beta_before)

    def test_nothing_to_do_exits_zero_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root)
            new = _change(root, "alpha", _new_of(_old()))
            plain = _change(root, "beta")
            before = (new.read_text(), plain.read_text())

            r = _run_gates(root, "approval", "migrate")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((new.read_text(), plain.read_text()), before)

    def test_an_unknown_named_change_fails_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root)
            r = _run_gates(root, "approval", "migrate", "no-such-change")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("no-such-change", r.stderr)

    def test_migrated_approval_still_checks(self):
        # Scenario "Migrating an active change".
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root)
            path = _change(root, "alpha")
            sha = _run_gates(root, "approval", "sha", "alpha").stdout.strip()
            path.write_text(path.read_text() + _old(sha))
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "plan approved under 0.5.0")

            r = _run_gates(root, "approval", "migrate")
            self.assertEqual(r.returncode, 0, r.stderr)
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "migrate approval keys")
            text = path.read_text()
            self.assertIn(f"x-gatedloop-approved-sha: {sha}", text)
            self.assertNotIn("\napproved_", "\n" + text)

            r = _run_gates(root, "approval", "check", "alpha")
            self.assertEqual(r.returncode, 0, r.stderr)


class TestOldKeyScan(unittest.TestCase):
    """The one fact doctor and the upgrade walk both read."""

    def test_lists_only_active_changes_with_an_old_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _change(root, "alpha", "approved_sha: abc\n")
            _change(root, "beta", _new_of(_old()))
            _change(root, "gamma")
            _change(root, "delta", _old(), archived=True)
            self.assertEqual(gates._changes_with_old_approval_keys(root), ["alpha"])

    def test_no_openspec_dir_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gates._changes_with_old_approval_keys(Path(tmp)), [])


def _levels(checks):
    return {title: level for level, title, _detail in checks}


def _details(checks):
    return {title: detail for _level, title, detail in checks}


class TestDoctorRow(unittest.TestCase):
    def test_omitted_when_not_checked(self):
        checks = gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p")
        self.assertNotIn("approval-keys", _levels(checks))

    def test_ok_when_no_change_carries_an_old_key(self):
        checks = gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p",
                                     old_approval_changes=[])
        self.assertEqual(_levels(checks)["approval-keys"], "ok")

    def test_warns_naming_the_changes_the_command_and_strict(self):
        checks = gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p",
                                     old_approval_changes=["alpha", "beta"])
        self.assertEqual(_levels(checks)["approval-keys"], "warn")
        detail = _details(checks)["approval-keys"]
        self.assertIn("alpha", detail)
        self.assertIn("beta", detail)
        self.assertIn("gates approval migrate", detail)
        self.assertIn("--strict", detail)


class TestDoctorEndToEnd(unittest.TestCase):
    """Scenario "Doctor on an unmigrated change"."""

    def test_doctor_warns_on_an_active_change_with_approved_sha(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as bin_tmp:
            root = Path(tmp)
            _repo(root)
            _change(root, "alpha", "approved_sha: abc\n")
            exe = Path(bin_tmp) / "openspec"
            exe.write_text(FAKE_OPENSPEC)
            exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
            path = f"{bin_tmp}{os.pathsep}{os.environ.get('PATH', '')}"

            r = _run_gates(root, "doctor", path=path)
            self.assertEqual(r.returncode, 0, r.stderr)
            row = [line for line in r.stdout.splitlines() if "approval-keys" in line]
            self.assertEqual(len(row), 1, r.stdout)
            self.assertIn("[WARN]", row[0])
            self.assertIn("alpha", row[0])
            self.assertIn("gates approval migrate", row[0])


if __name__ == "__main__":
    unittest.main()
