"""An unparseable manifest fails loud in one line (loop-hardening D6,
#109).

The regression: a `.gates.yaml` left with merge-conflict markers crashed
every subcommand with a PyYAML traceback, and the commit hook reported the
crash as "this branch is shared with another worktree". Worse, without
PyYAML the fallback parser read each marker line as a key and carried on
with whichever side came last. Now both YAML paths exit 1 with the same
line -- the file, the position, the reason -- and say when the file holds
conflict markers. No traceback reaches the user.

Real repositories and the real shim. The fallback path is forced by running
the shim with PyYAML made unimportable, the technique `_epic_fixture` uses;
the PyYAML path runs only where PyYAML is installed.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

HAVE_PYYAML = importlib.util.find_spec("yaml") is not None

_NO_YAML_RUNNER = (
    "import runpy, sys; sys.modules['yaml'] = None; "
    "sys.argv = ['gates'] + sys.argv[1:]; "
    f"runpy.run_path({str(GATES_SHIM)!r}, run_name='__main__')"
)

CONFLICTED = """\
gatesVersion: 1
gates:
<<<<<<< HEAD
  ci: "true"
=======
  ci: "false"
>>>>>>> other-branch
"""

CONFLICT_LINE = ".gates.yaml could not be parsed at line 3, column 1"


def _gates(root: Path, *args: str, no_yaml: bool) -> subprocess.CompletedProcess:
    argv = ([sys.executable, "-c", _NO_YAML_RUNNER, *args] if no_yaml
            else [sys.executable, str(GATES_SHIM), *args])
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(argv, cwd=root, capture_output=True, text=True, env=env, timeout=60)


def _repo(tmp: str, manifest: str) -> Path:
    root = Path(tmp)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    (root / ".gates.yaml").write_text(manifest)
    return root


class AConflictedManifest(unittest.TestCase):
    def _assert_one_line(self, r: subprocess.CompletedProcess) -> None:
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn(CONFLICT_LINE, r.stderr)
        self.assertIn("`<<<<<<<`", r.stderr)
        self.assertIn("merge-conflict markers", r.stderr)
        self.assertIn("resolve the conflict first", r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_the_fallback_parser_refuses_it_in_one_line(self):
        for cmd in (("validate",), ("discipline", "check-worktree")):
            with self.subTest(cmd), tempfile.TemporaryDirectory() as tmp:
                self._assert_one_line(_gates(_repo(tmp, CONFLICTED), *cmd, no_yaml=True))

    @unittest.skipUnless(HAVE_PYYAML, "PyYAML is not installed here")
    def test_pyyaml_refuses_it_in_the_same_line(self):
        for cmd in (("validate",), ("discipline", "check-worktree")):
            with self.subTest(cmd), tempfile.TemporaryDirectory() as tmp:
                yaml_run = _gates(_repo(tmp, CONFLICTED), *cmd, no_yaml=False)
                self._assert_one_line(yaml_run)
                fallback = _gates(Path(tmp), *cmd, no_yaml=True)
                self.assertEqual(yaml_run.stderr, fallback.stderr)


class AnyOtherParseError(unittest.TestCase):
    @unittest.skipUnless(HAVE_PYYAML, "PyYAML is not installed here")
    def test_pyyaml_names_the_position_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, 'gatesVersion: 1\ngates:\n  ci: [unclosed\n')
            r = _gates(root, "validate", no_yaml=False)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertRegex(r.stderr, r"^gatedloop: \.gates\.yaml could not be parsed at line \d+, column \d+: ")
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)


if __name__ == "__main__":
    unittest.main()
