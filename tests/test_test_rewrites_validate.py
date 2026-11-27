"""`gates validate` checks each `rewrites:` clause (openspec change
`test-rewrites`, design D1; the test-discipline delta's "A task may declare its
oracle in the plan" requirement and its scenarios).

It fails, naming the change, the task and the path, on an absolute path, a
`..` segment, a path under gatedloop's state directory and a path named twice;
the clause on `none` and an empty clause fail as malformed. It warns, without
failing, on a path absent from the working tree and on one that does not look
like a test path. A well-formed clause on existing tests passes silently.

Stdlib only, per `zero-dep-shim`. A throwaway git repository per case, the shim
driven as a subprocess.

Run with:  python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "rewrite-plan"

MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n'
    '  ci: "true"\n'
    '  unit: "true"\n'
)


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                   env=_env())


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _project(tmp, *lines):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml", MANIFEST)
    _write(root, "tests/a.test.ts", "test('a', () => {})\n")
    _write(root, "tests/b.test.ts", "test('b', () => {})\n")
    _write(root, "src/toolbar.ts", "export const toolbar = 1\n")
    _write(root, f"openspec/changes/{CHANGE}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"openspec/changes/{CHANGE}/tasks.md",
           "## 1. Group\n\n" + "".join(f"{x}\n" for x in lines))
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return root


def _validate(root):
    return subprocess.run([sys.executable, str(GATES_SHIM), "validate"], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=60)


class TestAValidClause(unittest.TestCase):
    """Regression guarded: a correct declaration refused, so no task can
    rewrite a test inside the loop."""

    def test_passes_without_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(
                tmp,
                "- [ ] 2.1 Move the key [oracle: unit rewrites: tests/a.test.ts]",
                "- [ ] 2.2 Drop timing [oracle: unit characterization rewrites: tests/a.test.ts, tests/b.test.ts]",
            )
            result = _validate(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("warning", result.stderr)


class TestEachFailure(unittest.TestCase):
    """Regression guarded: a declaration that would show the author a file
    outside the repository, gatedloop's own state, or one path twice."""

    def _fails(self, tag, *needles):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, f"- [ ] 2.1 Move the key {tag}")
            result = _validate(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(CHANGE, result.stderr)
            self.assertIn("2.1", result.stderr)
            for n in needles:
                self.assertIn(n, result.stderr)
            return result

    def test_an_absolute_path(self):
        self._fails("[oracle: unit rewrites: /etc/a.test.ts]", "/etc/a.test.ts", "absolute")

    def test_a_dot_dot_segment(self):
        self._fails("[oracle: unit rewrites: ../other/a.test.ts]", "../other/a.test.ts", "..")

    def test_a_dot_dot_segment_mid_path(self):
        self._fails("[oracle: unit rewrites: tests/../../a.test.ts]", "tests/../../a.test.ts")

    def test_a_path_under_the_state_directory(self):
        self._fails("[oracle: unit rewrites: .gatedloop/authored/x.test.ts]",
                    ".gatedloop/authored/x.test.ts", "state")

    def test_a_duplicate_path(self):
        self._fails("[oracle: unit rewrites: tests/a.test.ts, tests/a.test.ts]",
                    "tests/a.test.ts", "twice")

    def test_the_clause_on_none(self):
        self._fails("[oracle: none rewrites: tests/a.test.ts]", "has a test")

    def test_an_empty_clause(self):
        self._fails("[oracle: unit rewrites:]", "no path")


class TestEachWarning(unittest.TestCase):
    """Regression guarded: a rename on the target breaking every other
    change's `ci` (a refusal where a warning belongs), or a non-test file
    named silently, which would show the author implementation."""

    def _warns(self, tag, *needles):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, f"- [ ] 2.1 Move the key {tag}")
            result = _validate(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("warning", result.stderr)
            self.assertIn(CHANGE, result.stderr)
            self.assertIn("2.1", result.stderr)
            for n in needles:
                self.assertIn(n, result.stderr)

    def test_a_path_absent_from_the_working_tree(self):
        self._warns("[oracle: unit rewrites: tests/gone.test.ts]", "tests/gone.test.ts",
                    "does not exist")

    def test_a_path_that_does_not_look_like_a_test(self):
        self._warns("[oracle: unit rewrites: src/toolbar.ts]", "src/toolbar.ts",
                    "test path")


if __name__ == "__main__":
    unittest.main()
