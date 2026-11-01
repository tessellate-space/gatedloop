"""A task's own tick does not widen `unit`'s scope (scope-own-tasks D4, #122).

`unit` scopes off the working set, which holds the `tasks.md` `[x]` from the
moment the loop flips it. The current change's own `tasks.md` is left out of
`unit`'s scope selection and of the multi-surface union, exactly as for `ci`.
`gates surfaces` -- the hot set convention review and live-check read -- still
sees it.

Each command appends a line to a file outside the repository, so what ran is
read from that file, not from captured output.

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

CHANGE = "demo"
OWN_TASKS = f"openspec/changes/{CHANGE}/tasks.md"


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


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root = base / "repo"
        self.root.mkdir()
        self.ran = base / "ran.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def cmd(self, word: str) -> str:
        return f'"echo {word} >> {self.ran}"'

    def manifest(self, backend: bool, openspec_surface: bool) -> str:
        text = (
            "gatesVersion: 1\n"
            "gates:\n"
            '  ci: "true"\n'
            f"  unit: {self.cmd('GLOBAL')}\n"
            "surfaces:\n"
            "  - name: frontend\n"
            '    match: "frontend/**"\n'
            "    gates:\n"
            f"      unit: {self.cmd('FRONTEND')}\n"
        )
        if backend:
            text += (
                "  - name: backend\n"
                '    match: "backend/**"\n'
                "    gates:\n"
                f"      unit: {self.cmd('BACKEND')}\n"
            )
        if openspec_surface:
            # No `unit` override: were it hot, the union would add the global `unit`.
            text += '  - name: docs\n    match: "openspec/**"\n'
        return text

    def init(self, manifest: str) -> None:
        _git(self.root, "init", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(manifest)
        _write(self.root, OWN_TASKS, "## 1. Do it\n\n- [ ] 1.1 Do the thing\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-m", "init")
        _git(self.root, "checkout", "-b", CHANGE)

    def tick(self) -> None:
        p = self.root / OWN_TASKS
        p.write_text(p.read_text().replace("- [ ]", "- [x]"))

    def lines(self) -> list[str]:
        return self.ran.read_text().splitlines() if self.ran.exists() else []


class TestOwnTickDoesNotWidenUnit(_Case):
    def test_one_surface_plus_own_tick_runs_that_surfaces_unit(self):
        self.init(self.manifest(backend=False, openspec_surface=False))
        _write(self.root, "frontend/app.test.js")
        self.tick()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["FRONTEND"])

    def test_own_tick_does_not_join_the_union_through_an_openspec_surface(self):
        self.init(self.manifest(backend=False, openspec_surface=True))
        _write(self.root, "frontend/app.test.js")
        self.tick()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.lines(), ["FRONTEND"])

    def test_two_surfaces_plus_own_tick_run_exactly_those_two(self):
        self.init(self.manifest(backend=True, openspec_surface=True))
        _write(self.root, "frontend/app.test.js")
        _write(self.root, "backend/test_api.py")
        self.tick()

        r = _run_gates(self.root, "run", "unit")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(self.lines()), ["BACKEND", "FRONTEND"])

    def test_gates_surfaces_still_sees_the_tick(self):
        self.init(self.manifest(backend=False, openspec_surface=True))
        _write(self.root, "frontend/app.test.js")
        self.tick()

        r = _run_gates(self.root, "surfaces")

        self.assertEqual(r.returncode, 0, r.stderr)
        names = [line.split(":", 1)[0] for line in r.stdout.splitlines()]
        self.assertIn("docs", names)
        self.assertIn("frontend", names)


if __name__ == "__main__":
    unittest.main()
