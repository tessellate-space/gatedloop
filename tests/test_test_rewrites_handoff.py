"""`gates tests handoff` holds the plan to its declared rewrites (openspec
change `test-rewrites`, design D3; the test-discipline delta's "The handoff
refuses a declaration that contradicts the plan" requirement and its rewrite
scenarios).

A declared path that does not exist at `HEAD`, and a declared path the task
holds no full `<N.M>/<path>.authored` for, are each refused, naming the task
and the path, and nothing is recorded -- for the whole set and under `--task`.
An undeclared overwrite of an existing path is recorded as before, its base the
file's content before the change, with one advisory line; a later task carrying
a path an earlier task declared draws no advisory.

Stdlib only, per `zero-dep-shim`. A throwaway git repository per case; the
shim is driven as a subprocess, as the test author drives it.

Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "toolbar-plan"

MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n'
    '  ci: "true"\n'
    '  unit: "true"\n'
)

TASKS = """\
## 2. Work

- [ ] 2.1 Move the key [oracle: unit rewrites: tests/toolbar.test.ts]
- [ ] 2.2 Add a button [oracle: unit]
- [ ] 3.1 Rework the menu
"""

TOOLBAR = "test('key E', () => {})\n"
MENU = "test('menu', () => {})\n"
RED = "test('red', () => { throw 1 })\n"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=60)


def _project(tmp, tasks=TASKS):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml", MANIFEST)
    change = f"openspec/changes/{CHANGE}"
    _write(root, f"{change}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"{change}/tasks.md", tasks)
    _write(root, "tests/toolbar.test.ts", TOOLBAR)
    _write(root, "tests/menu.test.ts", MENU)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    return root


def _held(root):
    return root / ".gatedloop" / "authored" / CHANGE


def _consistent(root):
    held = _held(root)
    _write(held, "2.1/tests/toolbar.test.ts.authored", "test('key K', () => {})\n")
    _write(held, "2.2/tests/button.test.ts.authored", RED)
    _write(held, "3.1/tests/menu_new.test.ts.authored", RED)


def _handoff(root, *extra):
    return _gates(root, "tests", "handoff", CHANGE, *extra)


def _rows(root):
    ledger = root / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
    if not ledger.exists():
        return []
    return [json.loads(x) for x in ledger.read_text().splitlines()
            if x.strip() and '"tests-handoff"' in x]


def _blob(root, rel):
    return _git(root, "hash-object", rel).stdout.strip()


class TestAConsistentRewrite(unittest.TestCase):
    """Regression guarded: a declared rewrite that is handed off refused, or
    recorded without the base the lock returns the file to."""

    def test_is_recorded_with_its_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            base = _blob(root, "tests/toolbar.test.ts")
            result = _handoff(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = _rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["base"]["tests/toolbar.test.ts"], base)
            self.assertNotIn("without declaring", result.stdout + result.stderr)


class TestTheRefusals(unittest.TestCase):
    """Regression guarded: a plan that names a rewrite the handoff never
    carries, so the test the task must change stays as it is and the task
    halts at its first red `ci`; or a rewrite of a file that is not there."""

    def _refused(self, root, *needles, extra=()):
        result = _handoff(root, *extra)
        self.assertEqual(result.returncode, 1, result.stdout)
        for n in needles:
            self.assertIn(n, result.stderr)
        self.assertEqual(_rows(root), [], "a refused handoff records nothing")
        return result

    def test_a_declared_rewrite_with_no_full_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            (_held(root) / "2.1" / "tests" / "toolbar.test.ts.authored").unlink()
            _write(_held(root), "2.1/tests/other.test.ts.authored", RED)
            self._refused(root, "2.1", "tests/toolbar.test.ts", "no full file")

    def test_the_same_under_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            (_held(root) / "2.1" / "tests" / "toolbar.test.ts.authored").unlink()
            _write(_held(root), "2.1/tests/other.test.ts.authored", RED)
            self._refused(root, "2.1", "tests/toolbar.test.ts", extra=("--task", "2.1"))

    def test_another_task_under_task_is_not_held_to_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            (_held(root) / "2.1" / "tests" / "toolbar.test.ts.authored").unlink()
            _write(_held(root), "2.1/tests/other.test.ts.authored", RED)
            result = _handoff(root, "--task", "2.2")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_declared_path_absent_at_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, TASKS.replace("tests/toolbar.test.ts]", "tests/gone.test.ts]"))
            _consistent(root)
            _write(_held(root), "2.1/tests/gone.test.ts.authored", RED)
            _write(root, "tests/gone.test.ts", "uncommitted\n")
            self._refused(root, "2.1", "tests/gone.test.ts", "does not exist at HEAD",
                          "amend")

    def test_absent_at_head_under_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, TASKS.replace("tests/toolbar.test.ts]", "tests/gone.test.ts]"))
            _consistent(root)
            _write(_held(root), "2.1/tests/gone.test.ts.authored", RED)
            self._refused(root, "2.1", "tests/gone.test.ts", "does not exist at HEAD",
                          extra=("--task", "2.1"))


class TestAnUndeclaredOverwrite(unittest.TestCase):
    """Regression guarded: an undeclared overwrite refused (a new adopter-facing
    refusal nobody opted into), or let through invisibly."""

    def test_is_recorded_with_an_advisory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            _write(_held(root), "3.1/tests/menu.test.ts.authored", RED)
            base = _blob(root, "tests/menu.test.ts")
            result = _handoff(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            out = result.stdout + result.stderr
            self.assertIn("3.1", out)
            self.assertIn("tests/menu.test.ts", out)
            self.assertIn("without declaring", out)
            rows = _rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["base"]["tests/menu.test.ts"], base)

    def test_under_task_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            _write(_held(root), "3.1/tests/menu.test.ts.authored", RED)
            result = _handoff(root, "--task", "3.1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("without declaring", result.stdout + result.stderr)

    def test_a_new_path_draws_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            result = _handoff(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("without declaring", result.stdout + result.stderr)

    def test_a_later_task_carrying_an_earlier_declaration_draws_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _consistent(root)
            _write(_held(root), "3.1/tests/toolbar.test.ts.authored", "test('key K, menu', () => {})\n")
            result = _handoff(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("without declaring", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
