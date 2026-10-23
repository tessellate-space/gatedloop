"""Tests for recipe dedupe on `gates run live-check` (design D3,
`fix-marker-mechanics`, issues #14.2/#40.3).

Two hot surfaces that bind the exact same live-check command string are one
recipe, not two -- running it twice would double-count a non-idempotent
suite's flake (#14) as a second, independent failure. Dedupe is by *exact*
command string (the manifest binds plain strings, so string equality is
recipe identity, per D3), first-declaration order kept; the log line
attributes the one execution to every surface that binds it. Distinct
command strings each still run once under `--all`.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path, manifest: str) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


SHARED_COMMAND_MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: frontend
    match: "frontend/**"
    live-check: "echo RAN >> shared.count"
  - name: e2e
    match: "e2e/**"
    live-check: "echo RAN >> shared.count"
  - name: backend
    match: "backend/**"
    live-check: "echo RAN >> distinct.count"
"""


class TestSharedCommandRunsOnce(unittest.TestCase):
    def test_two_surfaces_sharing_one_command_produce_exactly_one_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, SHARED_COMMAND_MANIFEST)

            result = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)

            shared = root / "shared.count"
            self.assertTrue(shared.exists())
            self.assertEqual(
                len(shared.read_text().splitlines()), 1,
                "the shared command must execute exactly once, not once per surface",
            )

            distinct = root / "distinct.count"
            self.assertTrue(distinct.exists())
            self.assertEqual(len(distinct.read_text().splitlines()), 1)

            # The log line attributes the one execution to every surface
            # that binds it.
            self.assertIn("frontend", result.stderr)
            self.assertIn("e2e", result.stderr)

    def test_first_declaration_order_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: second
    match: "b/**"
    live-check: "echo B >> order.log"
  - name: first
    match: "a/**"
    live-check: "echo A >> order.log"
"""
            _init_repo(root, manifest)

            result = _run_gates(root, "run", "live-check", "--all", "--change", "my-change")
            self.assertEqual(result.returncode, 0, result.stderr)

            order = (root / "order.log").read_text().splitlines()
            self.assertEqual(order, ["B", "A"], "first-declaration order must be kept")


if __name__ == "__main__":
    unittest.main()
