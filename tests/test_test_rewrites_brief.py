"""`gates tests brief` prints each declared rewrite's content at HEAD (openspec
change `test-rewrites`, design D2; the test-discipline delta's "The test author
is told each task's declared oracle" requirement and its rewrite scenarios).

Under `## Declared rewrites`, each declaring task lists each path followed by
its full content at `HEAD`, fenced, or `absent at HEAD`. No other existing test
file's content is printed: "Where tests live" stays paths only.

Stdlib only, per `zero-dep-shim`. A throwaway git repository per case; the
shim is driven as a subprocess.

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
CHANGE = "toolbar-plan"

MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n'
    '  ci: "true"\n'
    '  unit: "true"\n'
)

TASKS = """\
## 2. Work

- [ ] 2.1 Move the key in `src/toolbar.ts` [oracle: unit rewrites: tests/toolbar.test.ts, tests/gone.test.ts]
- [ ] 2.2 Add a button in `src/toolbar.ts` [oracle: unit]
"""

TOOLBAR_HEAD = "test('key E opens the toolbar', () => {})\n"
OTHER_TEST = "test('SECRET-OTHER-CONTENT', () => {})\n"


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
    _write(root, f"{change}/design.md", "# Design\n")
    _write(root, "src/toolbar.ts", "export const key = 'E'\n")
    _write(root, "tests/toolbar.test.ts", TOOLBAR_HEAD)
    _write(root, "src/toolbar.spec.ts", OTHER_TEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    return root


def _brief(root):
    result = _gates(root, "tests", "brief", CHANGE)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _section(text, heading):
    start = text.index(f"## {heading}\n")
    rest = text[start + len(heading) + 4:]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


class TestTheDeclaredRewritesSection(unittest.TestCase):
    """Regression guarded: the author asked to carry forward cases it cannot
    see, so the rewrite is written blind (#157)."""

    def test_prints_the_content_at_head_under_its_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            text = _brief(root)
            self.assertIn("## Declared rewrites", text)
            self.assertLess(text.index("## Declared oracles"), text.index("## Declared rewrites"))
            sec = _section(text, "Declared rewrites")
            self.assertIn("2.1", sec)
            self.assertIn("tests/toolbar.test.ts", sec)
            self.assertIn(TOOLBAR_HEAD.strip(), sec)
            self.assertIn("```", sec)
            self.assertNotIn("2.2", sec)

    def test_reads_head_not_the_working_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _write(root, "tests/toolbar.test.ts", "test('WORKING-TREE-EDIT', () => {})\n")
            text = _brief(root)
            self.assertIn(TOOLBAR_HEAD.strip(), text)
            self.assertNotIn("WORKING-TREE-EDIT", text)

    def test_a_path_absent_at_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            _write(root, "tests/gone.test.ts", "test('UNCOMMITTED', () => {})\n")
            sec = _section(_brief(root), "Declared rewrites")
            self.assertIn("tests/gone.test.ts", sec)
            self.assertIn("absent at HEAD", sec)
            self.assertNotIn("UNCOMMITTED", sec)

    def test_no_declaration_says_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, TASKS.replace(
                " rewrites: tests/toolbar.test.ts, tests/gone.test.ts", ""))
            sec = _section(_brief(root), "Declared rewrites")
            self.assertIn("none", sec)
            self.assertNotIn(TOOLBAR_HEAD.strip(), sec)


class TestOtherTestsStayPathsOnly(unittest.TestCase):
    """Regression guarded: the exception widening into the author reading
    every existing test near the code."""

    def test_where_tests_live_prints_no_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            text = _brief(root)
            where = _section(text, "Where tests live")
            self.assertIn("src/toolbar.spec.ts", where)
            self.assertNotIn("SECRET-OTHER-CONTENT", text)


if __name__ == "__main__":
    unittest.main()
