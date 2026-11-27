"""A placed rewrite is the task's authored test, and review sees its diff
against base (openspec change `test-rewrites`, design D4 and D5; the
test-discipline delta's "A rewritten existing test is the task's authored test"
and "Review sees each rewrite's change against its base" requirements).

`gates tests show` lists each declared rewrite with its base blob and the lines
its handed-off content adds and removes against base, in text and JSON;
`--diff` prints the unified diff. The lock needs no change for a rewrite, and
these tests pin that on a real repository and a linked worktree: placed over
the existing file and run red, the commit holds; with no red run, or with the
placed file edited, it is refused; a `characterization` rewrite holds green
first; and after a defect the lock wants the file's content before the change.

Stdlib only, per `zero-dep-shim`. A throwaway repository per case with the
change branch in a linked worktree; the shim is driven as a subprocess.

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
    '  unit: "sh scripts/unit.sh"\n'
)

# The `unit` gate is red while the toolbar test asks for the new key.
UNIT_SH = "if grep -q KEY_K tests/toolbar.test.ts; then exit 1; fi\nexit 0\n"

TASKS = """\
## 2. Work

- [ ] 2.1 Move the key [oracle: unit rewrites: tests/toolbar.test.ts]
- [ ] 2.2 Drop the timing assertion [oracle: unit characterization rewrites: tests/menu.test.ts]
"""

TOOLBAR_BASE = "test('a')\ntest('b')\ntest('key E')\n"
TOOLBAR_NEW = "test('a')\ntest('b')\ntest('KEY_K one')\ntest('KEY_K two')\ntest('KEY_K three')\n"
MENU_BASE = "test('menu')\nexpect(ms).toBeLessThan(5)\n"
MENU_NEW = "test('menu')\n"


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


def _must(root, *args):
    r = _gates(root, *args)
    if r.returncode != 0:
        raise AssertionError(f"`gates {' '.join(args)}` failed: {r.stdout}{r.stderr}")
    return r


def _lane(tmp):
    """`main` holds the plan and the existing tests; the change branch is a
    linked worktree whose authoring is handed off and committed."""
    main = Path(tmp) / "main"
    main.mkdir()
    _git(main, "init", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "T")
    _write(main, ".gates.yaml", MANIFEST)
    _write(main, "scripts/unit.sh", UNIT_SH)
    _write(main, "src/toolbar.ts", "export const key = 'E'\n")
    _write(main, "tests/toolbar.test.ts", TOOLBAR_BASE)
    _write(main, "tests/menu.test.ts", MENU_BASE)
    _write(main, f"openspec/changes/{CHANGE}/.openspec.yaml", "schema: spec-driven\n")
    _write(main, f"openspec/changes/{CHANGE}/tasks.md", TASKS)
    _git(main, "add", "-A")
    _git(main, "commit", "-m", "plan")
    lane = Path(tmp) / "lane"
    _git(main, "worktree", "add", str(lane), "-b", CHANGE)
    held = lane / ".gatedloop" / "authored" / CHANGE
    _write(held, "2.1/tests/toolbar.test.ts.authored", TOOLBAR_NEW)
    _write(held, "2.2/tests/menu.test.ts.authored", MENU_NEW)
    _write(held, "2.2/CHARACTERIZATION", "drops a wall-clock assertion; the rest passes today\n")
    _must(lane, "tests", "handoff", CHANGE)
    _git(lane, "add", "-A")
    _git(lane, "commit", "-m", "author tests")
    return lane


def _blob(root, text):
    return subprocess.run(["git", "hash-object", "--stdin"], cwd=root, input=text,
                          capture_output=True, text=True, check=True).stdout.strip()


def _place(lane, task):
    _must(lane, "task", "start", task)
    _must(lane, "tests", "place", task)


def _implement(lane, task):
    _write(lane, f"src/task_{task.replace('.', '_')}.txt", f"task {task}\n")
    _git(lane, "add", "-A")


def _check(lane):
    return _gates(lane, "tests", "check")


class TestShowListsEachRewrite(unittest.TestCase):
    """Regression guarded: a rewrite that silently drops cases, invisible to the
    authored-set review because it reads only paths."""

    def test_json_carries_base_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            doc = json.loads(_must(lane, "tests", "show", CHANGE, "--json").stdout)
            rw = doc["tasks"]["2.1"]["rewrites"]
            self.assertEqual(rw, {"tests/toolbar.test.ts": {
                "base": _blob(lane, TOOLBAR_BASE), "added": 3, "removed": 1}})
            self.assertEqual(doc["tasks"]["2.2"]["rewrites"], {"tests/menu.test.ts": {
                "base": _blob(lane, MENU_BASE), "added": 0, "removed": 1}})

    def test_text_names_the_rewrite_with_its_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            out = _must(lane, "tests", "show", CHANGE).stdout
            self.assertIn("rewrites tests/toolbar.test.ts (+3 -1 vs base)", out)
            self.assertIn("rewrites tests/menu.test.ts (+0 -1 vs base)", out)

    def test_diff_prints_the_unified_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            out = _must(lane, "tests", "show", CHANGE, "--diff").stdout
            self.assertIn("tests/toolbar.test.ts", out)
            self.assertIn("-test('key E')", out)
            self.assertIn("+test('KEY_K one')", out)
            self.assertIn("-expect(ms).toBeLessThan(5)", out)
            self.assertIn("@@", out)

    def test_a_task_without_a_declaration_has_no_rewrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            _write(lane, ".gatedloop/authored/" + CHANGE + "/2.1/tests/new.test.ts.authored",
                   "test('KEY_K new')\n")
            _must(lane, "tests", "handoff", CHANGE, "--task", "2.1")
            doc = json.loads(_must(lane, "tests", "show", CHANGE, "--json").stdout)
            self.assertEqual(sorted(doc["tasks"]["2.1"]["rewrites"]), ["tests/toolbar.test.ts"])


class TestTheLockHoldsARewrite(unittest.TestCase):
    """Regression guarded: a later edit to the lock treating a rewrite of an
    existing file differently from a new authored test (D4)."""

    def test_placed_over_the_existing_file_and_run_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            _place(lane, "2.1")
            self.assertEqual((lane / "tests/toolbar.test.ts").read_text(), TOOLBAR_NEW)
            ran = _gates(lane, "run", "unit", "--task", "2.1")
            self.assertNotIn(ran.returncode, (0, 75), ran.stdout + ran.stderr)
            _implement(lane, "2.1")
            result = _check(lane)
            self.assertEqual(result.returncode, 0, result.stderr)
            _git(lane, "commit", "-m", "task 2.1")
            result = _gates(lane, "tests", "check", "--ref", "HEAD", "--change", CHANGE)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_red_run_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            _place(lane, "2.1")
            _implement(lane, "2.1")
            result = _check(lane)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("2.1", result.stderr)

    def test_an_edited_rewrite_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            _place(lane, "2.1")
            ran = _gates(lane, "run", "unit", "--task", "2.1")
            self.assertNotIn(ran.returncode, (0, 75))
            _write(lane, "tests/toolbar.test.ts", TOOLBAR_NEW.replace("KEY_K", "KEY_E"))
            _implement(lane, "2.1")
            result = _check(lane)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("tests/toolbar.test.ts", result.stderr)
            self.assertIn("defect", result.stderr)

    def test_a_characterization_rewrite_green_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            _place(lane, "2.2")
            self.assertEqual((lane / "tests/menu.test.ts").read_text(), MENU_NEW)
            ran = _gates(lane, "run", "unit", "--task", "2.2")
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
            _implement(lane, "2.2")
            result = _check(lane)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_defect_wants_the_base_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            lane = _lane(tmp)
            _place(lane, "2.1")
            ran = _gates(lane, "run", "unit", "--task", "2.1")
            self.assertNotIn(ran.returncode, (0, 75))
            _must(lane, "tests", "defect", "2.1", "--kind", "assertion",
                  "--detail", "asserts the wrong key")
            _git(lane, "add", "-A")
            result = _check(lane)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("tests/toolbar.test.ts", result.stderr)
            ledger = lane / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
            rows = ledger.read_bytes()
            _git(lane, "reset", "-q")
            _git(lane, "checkout", "-q", "--", ".")
            ledger.write_bytes(rows)
            self.assertEqual((lane / "tests/toolbar.test.ts").read_text(), TOOLBAR_BASE)
            _git(lane, "add", "-A")
            result = _check(lane)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
