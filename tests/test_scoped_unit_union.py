"""A multi-surface `unit` run runs the union of the hot surfaces' oracles
(err-full-scoping D2, #45).

The global `unit` used to stand in for every multi-surface run, so a surface
whose `unit` override is not part of the global one never ran its new test,
and the task's required red read green. Each hot surface's override now runs
in surface order, the global `unit` once for hot surfaces declaring none,
identical commands once, all preconditions before any command, under one
lock; the exit is the first non-zero code.

Each command appends a line to a file outside the repository, so what ran
and in what order is read from that file, not from captured output.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _write(root: Path, rel: str, text: str = "x\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


class _UnionCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root = base / "repo"
        self.root.mkdir()
        self.ran = base / "ran.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, word: str, exit_code: int = 0) -> str:
        # The redirection may sit anywhere, so arguments appended after it
        # still reach `echo` and are recorded on the same line.
        tail = f"; exit {exit_code}" if exit_code else ""
        return f'"echo {word} >> {self.ran}{tail}"'

    def init(self, manifest: str) -> None:
        _git(self.root, "init", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(manifest)
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-m", "init")

    def touch_both(self) -> None:
        _write(self.root, "frontend/app.test.js")
        _write(self.root, "e2e/steps.js")

    def lines(self) -> list[str]:
        return self.ran.read_text().splitlines() if self.ran.exists() else []


class TestUnitUnion(_UnionCase):
    def manifest(self, frontend: str, e2e: str | None, global_unit: str,
                 catchall: bool = True) -> str:
        # `frontend` is a scalar command, or already a block mapping's lines.
        e2e_gates = f"    gates:\n      unit: {e2e}\n" if e2e else ""
        text = (
            "gatesVersion: 1\n"
            "gates:\n"
            '  ci: "true"\n'
            f"  unit: {global_unit}\n"
            "surfaces:\n"
            "  - name: frontend\n"
            '    match: "frontend/**"\n'
            "    gates:\n"
            f"      unit: {frontend}\n"
            "  - name: e2e\n"
            '    match: "e2e/**"\n'
            f"{e2e_gates}"
        )
        if catchall:
            text += '  - name: all\n    match: "**"\n'
        return text

    def test_two_overrides_both_run_in_surface_order(self):
        self.init(self.manifest(self.cmd("FRONTEND"), self.cmd("E2E"), self.cmd("GLOBAL")))
        self.touch_both()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["FRONTEND", "E2E"])

    def test_extra_arguments_reach_every_command(self):
        self.init(self.manifest(self.cmd("FRONTEND"), self.cmd("E2E"), self.cmd("GLOBAL")))
        self.touch_both()

        r = _run_gates(self.root, "run", "unit", "--", "-p", "x")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["FRONTEND -p x", "E2E -p x"])

    def test_one_red_makes_the_run_red_and_every_command_reports(self):
        self.init(self.manifest(self.cmd("FRONTEND"), self.cmd("E2E", 3), self.cmd("GLOBAL")))
        self.touch_both()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(self.lines(), ["FRONTEND", "E2E"])
        out = r.stdout + r.stderr
        self.assertRegex(out, r"unit\[frontend\] green")
        self.assertRegex(out, r"unit\[e2e\] red \(exit 3\)")

    def test_first_red_does_not_stop_the_rest(self):
        self.init(self.manifest(self.cmd("FRONTEND", 4), self.cmd("E2E", 5), self.cmd("GLOBAL")))
        self.touch_both()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(self.lines(), ["FRONTEND", "E2E"])

    def test_surface_without_override_adds_the_global_once(self):
        self.init(self.manifest(self.cmd("FRONTEND"), None, self.cmd("GLOBAL")))
        self.touch_both()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["FRONTEND", "GLOBAL"])

    def test_shared_command_runs_once(self):
        shared = self.cmd("SHARED")
        self.init(self.manifest(shared, shared, self.cmd("GLOBAL")))
        self.touch_both()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["SHARED"])

    def test_failing_precondition_runs_nothing(self):
        frontend = f'\n        run: {self.cmd("FRONTEND")}\n        requires: "false"'
        self.init(self.manifest(frontend, self.cmd("E2E"), self.cmd("GLOBAL")))
        self.touch_both()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 75, r.stdout + r.stderr)
        self.assertEqual(self.lines(), [])
        self.assertIn("precondition", r.stderr)

    def test_single_surface_still_runs_only_its_override(self):
        self.init(self.manifest(self.cmd("FRONTEND"), self.cmd("E2E"), self.cmd("GLOBAL")))
        _write(self.root, "frontend/app.test.js")

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["FRONTEND"])


if __name__ == "__main__":
    unittest.main()
