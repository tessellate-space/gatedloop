"""Quiet-on-green gate output (`scale-gate-cost` design D3): `gates run`
captures a declared gate's combined output to `.gatedloop/out/<gate>-<ts>.log`
and prints exactly one summary line on a green exit; on a red exit it prints
the full captured output and preserves the exit code. `--verbose` restores
unfiltered streaming (no capture file). Old-run rotation keeps the log
directory bounded.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST_GREEN = 'gatesVersion: 1\ngates:\n  ci: "echo HELLO-FROM-CI"\n'
MANIFEST_RED = 'gatesVersion: 1\ngates:\n  ci: "echo BOOM-OUTPUT && exit 7"\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path, manifest: str) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


class TestQuietOnGreen(unittest.TestCase):
    def test_green_run_prints_one_summary_line_and_saves_full_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_GREEN)

            r = _run_gates(root, "run", "ci")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("HELLO-FROM-CI", r.stdout + r.stderr)
            out_dir = root / ".gatedloop" / "out"
            logs = list(out_dir.glob("ci-*.log"))
            self.assertEqual(len(logs), 1, list(out_dir.iterdir()) if out_dir.exists() else "no out dir")
            self.assertIn("HELLO-FROM-CI", logs[0].read_text())
            # Summary line names the gate, the scope, duration, and the path.
            self.assertIn("ci[full]", r.stdout + r.stderr)
            self.assertIn(str(logs[0]), r.stdout + r.stderr)

    def test_red_run_prints_everything_and_preserves_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_RED)

            r = _run_gates(root, "run", "ci")

            self.assertEqual(r.returncode, 7)
            self.assertIn("BOOM-OUTPUT", r.stdout + r.stderr)

    def test_verbose_streams_unfiltered_with_no_capture_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_GREEN)

            r = _run_gates(root, "run", "ci", "--verbose")

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("HELLO-FROM-CI", r.stdout + r.stderr)
            out_dir = root / ".gatedloop" / "out"
            self.assertFalse(out_dir.exists() and list(out_dir.glob("ci-*.log")))

    def test_rotation_keeps_a_bounded_number_of_logs_per_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root, MANIFEST_GREEN)

            for _ in range(8):
                r = _run_gates(root, "run", "ci")
                self.assertEqual(r.returncode, 0, r.stderr)

            logs = list((root / ".gatedloop" / "out").glob("ci-*.log"))
            self.assertLessEqual(len(logs), 5)
            self.assertGreater(len(logs), 0)


if __name__ == "__main__":
    unittest.main()
