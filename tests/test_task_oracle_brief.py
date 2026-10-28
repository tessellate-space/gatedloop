"""The test author is told each task's declared oracle (openspec change
`task-oracle`, design D3 and D5; the test-discipline delta's "The test author
is told each task's declared oracle" requirement).

`gates tests brief` prints, under `## Declared oracles`, one line per task:
the gate and whether it goes red first, `characterization` on a gate, `none`,
or -- for an untagged task -- that the author decides. `gates tests show`
carries the same declaration per task, as an `oracle` field in its JSON
(`"<gate>"`, `"<gate> characterization"`, `"none"`, or null) and an
`oracle:` column in its text.

Stdlib only, per `zero-dep-shim`. A throwaway git repository per case; the
shim is driven as a subprocess.

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
CHANGE = "mixed-plan"

MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n'
    '  ci: "true"\n'
    '  unit: "true"\n'
    '  integration: "true"\n'
)

TASKS = """\
## 1. Work

- [ ] 1.1 Wire the e2e step [oracle: integration]
- [ ] 2.1 Add the parser
- [ ] 3.1 Verify the data an earlier task wrote [oracle: unit characterization]
- [ ] 4.2 Edit the prompt [oracle: none]
"""


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


def _project(tmp):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml", MANIFEST)
    change = f"openspec/changes/{CHANGE}"
    _write(root, f"{change}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"{change}/tasks.md", TASKS)
    _write(root, f"{change}/design.md", "# Design\n")
    _write(root, "src/calc.py", "def add(a, b): ...\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    _git(root, "checkout", "-b", CHANGE)
    return root


def _handed_off(root):
    held = root / ".gatedloop" / "authored" / CHANGE
    _write(held, "1.1/tests/test_e2e.py.authored", "def test_e2e():\n    assert False\n")
    _write(held, "2.1/tests/test_parse.py.authored", "def test_parse():\n    assert False\n")
    _write(held, "3.1/tests/test_data.py.authored", "def test_data():\n    assert True\n")
    _write(held, "3.1/CHARACTERIZATION", "pins the data task 1.1 already wrote\n")
    _write(held, "4.2/NO-TESTS", "a prompt edit; no behaviour a test can see\n")
    result = _gates(root, "tests", "handoff", CHANGE)
    assert result.returncode == 0, result.stderr
    return root


def _section(text, heading):
    lines = text.splitlines()
    start = lines.index(heading) + 1
    out = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


def _line_for(lines, task):
    found = [x for x in lines if x.strip().startswith(f"{task}:")]
    if len(found) != 1:
        raise AssertionError(f"expected one line for {task} in {lines!r}")
    return found[0]


class TestTheBriefNamesEachOracle(unittest.TestCase):
    """Regression guarded: the author inferring a task's kind from prose (the
    #56 misread of 3.1 and 5.1) when the plan has already declared it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _project(self._tmp.name)
        result = _gates(self.root, "tests", "brief", CHANGE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.section = _section(result.stdout, "## Declared oracles")

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_gate_tagged_task_is_red_first_on_its_gate(self):
        line = _line_for(self.section, "1.1")
        self.assertIn("`integration`", line)
        self.assertIn("red first", line)

    def test_a_characterization_task_names_its_gate(self):
        line = _line_for(self.section, "3.1")
        self.assertIn("characterization", line)
        self.assertIn("`unit`", line)

    def test_a_none_task_needs_no_tests(self):
        self.assertIn("no tests", _line_for(self.section, "4.2"))

    def test_an_untagged_task_is_the_authors_to_decide(self):
        self.assertIn("the author decides", _line_for(self.section, "2.1"))

    def test_the_task_list_carries_no_tag(self):
        result = _gates(self.root, "tests", "brief", CHANGE)
        self.assertIn("  1.1 Wire the e2e step", result.stdout.splitlines())
        self.assertNotIn("[oracle:", result.stdout)


class TestShowCarriesTheOracle(unittest.TestCase):
    """Regression guarded: the implementer running its red step on `unit`
    because nothing it reads says which gate the plan declared."""

    def test_the_json_names_each_tasks_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _handed_off(_project(tmp))
            result = _gates(root, "tests", "show", CHANGE, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            tasks = json.loads(result.stdout)["tasks"]
            self.assertEqual(tasks["1.1"]["oracle"], "integration")
            self.assertEqual(tasks["3.1"]["oracle"], "unit characterization")
            self.assertEqual(tasks["4.2"]["oracle"], "none")
            self.assertIsNone(tasks["2.1"]["oracle"])

    def test_the_text_has_an_oracle_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _handed_off(_project(tmp))
            result = _gates(root, "tests", "show", CHANGE)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.splitlines()

            def task_line(tid):
                found = [x for x in lines if x.strip().startswith(tid + " ")]
                self.assertEqual(len(found), 1, lines)
                return found[0]

            self.assertIn("oracle: integration", task_line("1.1"))
            self.assertIn("oracle: unit characterization", task_line("3.1"))
            self.assertIn("oracle: none", task_line("4.2"))
            self.assertIn("oracle: undeclared", task_line("2.1"))


if __name__ == "__main__":
    unittest.main()
