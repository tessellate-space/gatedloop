"""Every `openspec` process the shim starts is told it is not interactive
(openspec change `openspec-1-14-compat`, design D5; requirement "The shim
runs OpenSpec non-interactively").

OpenSpec before 1.14.3 could spin forever in `validate` on a terminal that
reports zero columns, as some pre-commit runners do; `OPEN_SPEC_INTERACTIVE=0`
turns the spinner off. The shim runs `openspec` from hooks and from the git
pre-commit layer, so every call goes through one helper, `_openspec`, that
adds the variable whatever version is installed.

Stdlib only, per `zero-dep-shim`. `openspec` is faked on PATH by a script
that records the variable it saw; every repository is a throwaway one.

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
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_openspec_noninteractive", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

# Records "<subcommand> <OPEN_SPEC_INTERACTIVE or UNSET>" per call, then
# answers like a valid OpenSpec.
FAKE_OPENSPEC = """\
#!/usr/bin/env bash
echo "$1 ${OPEN_SPEC_INTERACTIVE-UNSET}" >> "$OPENSPEC_ENV_LOG"
case "$1" in
  --version) echo 1.14.3 ;;
  validate) echo '{"items":[{"id":"'"$2"'","type":"change","valid":true,"issues":[]}]}' ;;
  status) echo '{"changeName":"'"$3"'","artifacts":[]}' ;;
  *) exit 1 ;;
esac
exit 0
"""


def _git(cwd, *args, env=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                   env=env or _base_env())


def _base_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    env.pop("OPEN_SPEC_INTERACTIVE", None)
    return env


class _FakeOpenSpec:
    def __init__(self, test: unittest.TestCase):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        exe = self.dir / "openspec"
        exe.write_text(FAKE_OPENSPEC)
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        self.log = self.dir / "env.log"

    def env(self) -> dict:
        env = _base_env()
        env["PATH"] = f"{self.dir}{os.pathsep}{env.get('PATH', '')}"
        env["OPENSPEC_ENV_LOG"] = str(self.log)
        return env

    def calls(self) -> list[tuple[str, str]]:
        if not self.log.exists():
            return []
        return [tuple(line.split(" ", 1)) for line in self.log.read_text().splitlines()]


def _repo(root: Path) -> None:
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text('gatesVersion: 1\ngates:\n  ci: "true"\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def _staged_tree(root: Path) -> str:
    return subprocess.run(["git", "write-tree"], cwd=root, capture_output=True, text=True,
                          env=_base_env()).stdout.strip()


class TestPlanningGradeCommitCheck(unittest.TestCase):
    """Scenario "A hook validates a change"."""

    def test_validate_runs_non_interactive(self):
        fake = _FakeOpenSpec(self)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root)
            change_dir = root / "openspec" / "changes" / "foo"
            (change_dir / "specs").mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            (change_dir / "specs" / "spec.md").write_text("delta\n")
            _git(root, "add", "-A")

            r = subprocess.run([sys.executable, str(GATES_SHIM), "discipline", "check-commit",
                                _staged_tree(root)], cwd=root, capture_output=True, text=True,
                               env=fake.env(), timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            calls = fake.calls()
            self.assertIn(("validate", "0"), calls, calls)
            self.assertTrue(all(value == "0" for _sub, value in calls), calls)

    def test_status_for_a_proposal_only_change_runs_non_interactive(self):
        fake = _FakeOpenSpec(self)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _repo(root)
            change_dir = root / "openspec" / "changes" / "foo"
            change_dir.mkdir(parents=True)
            (change_dir / "proposal.md").write_text("plan\n")
            _git(root, "add", "-A")

            r = subprocess.run([sys.executable, str(GATES_SHIM), "discipline", "check-commit",
                                _staged_tree(root)], cwd=root, capture_output=True, text=True,
                               env=fake.env(), timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            calls = fake.calls()
            self.assertIn(("status", "0"), calls, calls)
            self.assertTrue(all(value == "0" for _sub, value in calls), calls)


class TestVersionProbe(unittest.TestCase):
    def test_doctor_version_probe_runs_non_interactive(self):
        fake = _FakeOpenSpec(self)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, fake.env(), clear=True):
            self.assertEqual(gates._installed_openspec_version(Path(tmp)), "1.14.3")
        self.assertEqual(fake.calls(), [("--version", "0")])


if __name__ == "__main__":
    unittest.main()
