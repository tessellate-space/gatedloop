"""A task id may carry a letter suffix (openspec change `friction-fixes`,
design D1 and D4; the test-discipline delta's "A task id may carry a letter
suffix" requirement; issue #46).

A plan amendment adds a task as `1.2a`. Every reader of a change's task lines
must read it as it reads `1.2`: the task-line parser with its oracle tag, the
test author's brief, the completion walk's checked-task reader, and the D9
approval digest. `1A.2`, `1.2-b` and an unnumbered line are still not tasks.

The regressions guarded: a lettered task's tag, brief line, tick or digest
entry silently dropped, and a prose bullet read as a task.

Stdlib only, per `zero-dep-shim`. The parsers are tested directly; the brief
and the approval sha through the shim, in a throwaway git repository.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "amended-plan"
CDIR = f"openspec/changes/{CHANGE}"

_loader = importlib.machinery.SourceFileLoader("gates_shim_lettered_ids", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

UNIT = {"gate": "unit", "characterization": False}

PLAN = """\
## 1. Work

- [ ] 1.2 Parse the input [oracle: unit]
- [ ] 1.2a Handle the empty case [oracle: unit]
- [ ] 1.3 Report the result
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


def _project(tmp, tasks):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml",
           'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n  integration: "true"\n')
    _write(root, f"{CDIR}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"{CDIR}/proposal.md", "# Proposal\n\nWhy.\n")
    _write(root, f"{CDIR}/design.md", "# Design\n\nHow.\n")
    _write(root, f"{CDIR}/specs/x/spec.md", "## ADDED Requirements\n\n### Requirement: X\n")
    _write(root, f"{CDIR}/tasks.md", tasks)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "plan")
    return root


class TestTheTaskLineParser(unittest.TestCase):
    """Regression guarded: `1.2a`'s line, and with it its oracle tag, never
    read by the one parser every consumer goes through."""

    def test_a_lettered_line_is_read_with_its_tag(self):
        lines = gates._task_lines_text(PLAN)
        self.assertIn(("1.2a", "Handle the empty case", UNIT), lines)

    def test_lettered_and_bare_ids_are_both_read_in_file_order(self):
        ids = [tid for tid, _text, _oracle in gates._task_lines_text(PLAN)]
        self.assertEqual(ids, ["1.2", "1.2a", "1.3"])

    def test_a_deeper_numbered_id_takes_a_letter_too(self):
        lines = gates._task_lines_text("- [ ] 1.2.3b Deep amendment [oracle: unit]\n")
        self.assertEqual(lines, [("1.2.3b", "Deep amendment", UNIT)])

    def test_ids_outside_the_grammar_are_not_tasks(self):
        for line in ("- [ ] 1A.2 Uppercase in the middle [oracle: unit]",
                     "- [ ] 1.2-b Hyphenated [oracle: unit]",
                     "- [ ] 1.2ab Two letters [oracle: unit]",
                     "- [ ] Update the docs [oracle: unit]"):
            with self.subTest(line=line):
                self.assertEqual(gates._task_lines_text(line + "\n"), [])


class TestTheCheckedTaskReader(unittest.TestCase):
    """Regression guarded: a committed `[x] 1.2a` never seen by the
    completion walk, so a later halt at `1.2a` voided its placement as if it
    were still in flight (unblock-authored-lock D2 and D3)."""

    def test_a_checked_lettered_task_is_read(self):
        text = "- [x] 1.2 Done\n- [x] 1.2a Done too\n- [ ] 1.3 Open\n"
        self.assertEqual(gates._checked_task_ids(text), {"1.2", "1.2a"})

    def test_an_unchecked_lettered_task_is_not(self):
        self.assertEqual(gates._checked_task_ids("- [ ] 1.2a Open\n"), set())

    def test_ids_outside_the_grammar_are_not_read(self):
        text = "- [x] 1A.2 a\n- [x] 1.2-b b\n- [x] Unnumbered c\n"
        self.assertEqual(gates._checked_task_ids(text), set())


class TestTheBrief(unittest.TestCase):
    """Regression guarded: the test author never told about `1.2a` or its
    declared oracle, so it writes nothing for the amended task."""

    def test_the_brief_lists_the_lettered_task_and_its_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, PLAN)
            r = _gates(root, "tests", "brief", CHANGE)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("  1.2a Handle the empty case", r.stdout)
            self.assertIn("1.2a: `unit`", r.stdout)


class TestTheApprovalDigest(unittest.TestCase):
    """Regression guarded: retagging `1.2a` leaving the approval sha
    unchanged -- the hole task-oracle D9 closed for `N.M` tasks."""

    def test_the_digest_carries_the_lettered_pair(self):
        self.assertIn(("1.2a", "[oracle: unit]"), gates._oracle_tag_pairs(PLAN))

    def test_retagging_the_lettered_task_moves_the_sha(self):
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            a = _gates(_project(tmp_a, PLAN), "approval", "sha", CHANGE)
            retagged = PLAN.replace("empty case [oracle: unit]",
                                    "empty case [oracle: integration]")
            b = _gates(_project(tmp_b, retagged), "approval", "sha", CHANGE)
            self.assertEqual(a.returncode, 0, a.stderr)
            self.assertEqual(b.returncode, 0, b.stderr)
            self.assertNotEqual(a.stdout.strip(), b.stdout.strip())


if __name__ == "__main__":
    unittest.main()
