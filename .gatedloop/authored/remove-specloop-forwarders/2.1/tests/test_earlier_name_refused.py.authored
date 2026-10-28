"""A project still on the earlier state directory is refused from 0.9.0
(change `remove-specloop-forwarders`, design D2; spec "The earlier name is
refused after its release").

Once read-both goes, a project holding only the earlier state directory
would otherwise look like a fresh one: the next command would create
`.gatedloop/` beside it and the ledger would split, silently. So every
command except `gates doctor` and `gates migrate-name` refuses while the
earlier directory exists, and the refusal names `gates migrate-name`. The
regressions caught here:

- a command that runs on an unmigrated project, writing a second state
  directory (a split ledger), whatever route the command takes through the
  shim (one that loads the manifest, or one special-cased ahead of it);
- a refusal that does not say how to get out of it;
- the way out refused too: `gates doctor` or `gates migrate-name` blocked,
  or a migrated project still refused;
- a project holding both directories no longer refused.

The earlier name is taken from the shim (`gates.EARLIER_NAME`), which keeps
it for `gates migrate-name`, so this file needs no allow-list entry.
Stdlib only, per `zero-dep-shim`. Every repository is a throwaway one.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_earlier_name_refused", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

EARLIER_DIR = f".{gates.EARLIER_NAME}"
NEW_DIR = ".gatedloop"
CHANGE = "add-thing"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'
PROPOSAL = ("## Why\n\nBecause a reason that is long enough to pass the validator's checks.\n\n"
            "## What Changes\n\n- A thing changes.\n")


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    env["OPEN_SPEC_INTERACTIVE"] = "0"
    return env


def _git(cwd, *args) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env()).stdout.strip()


def _gates(root, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def _project(root: Path, state_dirs: tuple[str, ...]) -> None:
    """A repository on branch `add-thing`, the change planned on `main`, with
    each named state directory holding one committed ledger row."""
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    change = root / "openspec" / "changes" / CHANGE
    change.mkdir(parents=True)
    (change / "proposal.md").write_text(PROPOSAL)
    (change / "tasks.md").write_text("## 1. Do it\n\n- [ ] 1.1 Add the thing\n")
    (change / ".openspec.yaml").write_text("schema: spec-driven\n")
    for name in state_dirs:
        runs = root / name / "runs"
        runs.mkdir(parents=True)
        (runs / f"{CHANGE}.jsonl").write_text(json.dumps({"gate": "unit", "change": CHANGE}) + "\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "plan")
    _git(root, "checkout", "-q", "-b", CHANGE)


def _rows(root: Path, state_dir: str) -> int:
    path = root / state_dir / "runs" / f"{CHANGE}.jsonl"
    return len(path.read_text().splitlines()) if path.exists() else 0


class TestAnUnmigratedProjectIsRefused(unittest.TestCase):
    def test_every_route_through_the_shim_refuses_naming_the_command(self):
        # One command per route: through the manifest (`run`, which would
        # write a ledger row), and one special-cased ahead of it.
        for args in (("run", "ci"), ("hook", "install")):
            with self.subTest(args), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _project(root, (EARLIER_DIR,))

                r = _gates(root, *args)

                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("gates migrate-name", r.stderr)
                self.assertIn(EARLIER_DIR, r.stderr)
                self.assertFalse((root / NEW_DIR).exists(), "a second state directory was written")
                self.assertEqual(_rows(root, EARLIER_DIR), 1)

    def test_both_state_directories_are_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root, (EARLIER_DIR, NEW_DIR))

            r = _gates(root, "run", "ci")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("gates migrate-name", r.stderr)
            for name in (EARLIER_DIR, NEW_DIR):
                self.assertIn(name, r.stderr)
                self.assertEqual(_rows(root, name), 1, name)


class TestTheWayOut(unittest.TestCase):
    def test_doctor_reports_it_and_migrate_name_clears_the_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root, (EARLIER_DIR,))

            doctor = _gates(root, "doctor")
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
            rows = [line for line in doctor.stdout.splitlines() if "[WARN] name:" in line]
            self.assertEqual(len(rows), 1, doctor.stdout)
            self.assertIn("gates migrate-name", rows[0])

            migrated = _gates(root, "migrate-name")
            self.assertEqual(migrated.returncode, 0, migrated.stdout + migrated.stderr)

            r = _gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse((root / EARLIER_DIR).exists())
            self.assertEqual(_rows(root, NEW_DIR), 2)


if __name__ == "__main__":
    unittest.main()
