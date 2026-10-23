"""`gates doctor`'s `gates-on-path` row (openspec change `gates-on-path`,
design D2, issue #40): doctor checks the symptom -- whether `gates`
resolves by name -- instead of a proxy for it.

`doctor_checks` takes the path `shutil.which("gates")` returned as the
`gates_on_path` primitive (None: not found) and the running shim's path as
`shim_path` (both by keyword); leaving `gates_on_path` out omits the row. The end-to-end case
runs the real shim with PATH set explicitly, never inherited, so the result
does not depend on the host's install.

Stdlib only. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import clean_env

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _row(checks, title):
    rows = [(level, detail) for level, t, detail in checks if t == title]
    return rows[0] if rows else None


def _exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


class TestGatesOnPathRow(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        self.shim = _exe(self.base / "plugin" / "bin" / "gates")

    def tearDown(self):
        self._tmp.cleanup()

    def checks(self, found):
        return gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1,
                                   shim_path=str(self.shim), gates_on_path=found)

    def test_omitted_when_not_checked(self):
        checks = gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p")
        self.assertIsNone(_row(checks, "gates-on-path"))

    def test_found_as_the_running_shim_is_ok_naming_the_path(self):
        level, detail = _row(self.checks(str(self.shim)), "gates-on-path")
        self.assertEqual(level, "ok")
        self.assertIn(str(self.shim), detail)
        self.assertNotIn("different copy", detail)

    def test_found_through_a_symlink_to_the_running_shim_is_the_same_copy(self):
        # Regression: comparing unresolved paths calls the plugin's own
        # bin/ symlink "a different copy".
        link_dir = self.base / "on-path"
        link_dir.mkdir()
        (link_dir / "gates").symlink_to(self.shim)
        level, detail = _row(self.checks(str(link_dir / "gates")), "gates-on-path")
        self.assertEqual(level, "ok")
        self.assertNotIn("different copy", detail)

    def test_found_as_a_different_copy_is_ok_and_says_so(self):
        # Regression: a stale copy earlier on PATH runs instead of this shim,
        # and doctor says nothing about it.
        other = _exe(self.base / "stale" / "bin" / "gates")
        level, detail = _row(self.checks(str(other)), "gates-on-path")
        self.assertEqual(level, "ok")
        self.assertIn(str(other), detail)
        self.assertIn("different copy", detail)
        self.assertIn(str(self.shim), detail)

    def test_not_found_warns_with_remedies_built_from_the_shim(self):
        # Regression (#40): doctor reported nothing about the one fact that
        # breaks every `gates ...` step.
        level, detail = _row(self.checks(None), "gates-on-path")
        self.assertEqual(level, "warn")
        self.assertIn("not on this shell's PATH", detail)
        self.assertIn(f'export PATH="$PATH:{self.shim.parent}"', detail)
        self.assertIn("new session", detail)
        self.assertIn("SETUP.md", detail)

    def test_never_blocking(self):
        for found in (None, str(self.shim)):
            for level, _t, _d in self.checks(found):
                self.assertIn(level, ("ok", "warn"))


class TestDoctorCommandGatesOnPath(unittest.TestCase):
    """The real shim, with PATH set explicitly: the row reads `gates` from
    PATH and builds the remedy from the shim's own bin/ directory."""

    def run_doctor(self, path: str) -> str:
        proc = subprocess.run(
            [sys.executable, str(GATES_SHIM), "doctor"], cwd=REPO,
            env=clean_env({"PATH": path, "CLAUDE_PLUGIN_ROOT": None}),
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_not_on_path_warns_with_this_shims_bin(self):
        out = self.run_doctor("/usr/bin:/bin")
        self.assertIn("[WARN] gates-on-path:", out)
        self.assertIn(f'export PATH="$PATH:{GATES_SHIM.parent}"', out)

    def test_on_path_as_this_shim_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "gates"
            link.symlink_to(GATES_SHIM)
            out = self.run_doctor(f"{tmp}:/usr/bin:/bin")
        self.assertIn("[ok  ] gates-on-path:", out)
        self.assertNotIn("different copy", out)


if __name__ == "__main__":
    unittest.main()
