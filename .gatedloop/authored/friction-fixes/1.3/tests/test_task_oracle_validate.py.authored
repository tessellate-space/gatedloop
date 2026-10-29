"""`gates validate` checks every oracle tag in the active changes (openspec
change `task-oracle`, design D1; the test-discipline delta's "A task may
declare its oracle in the plan" requirement and its scenarios).

A tag names a declared gate other than `ci`, `live-check`, `eval` and
`confirm`; an unknown gate, an excluded gate and a malformed tag each fail,
naming the change, the task and the tag. A lettered id (`1.2a`) is a task like
any other (change `friction-fixes`, D1 and D3); a tag on a line whose id is
outside the grammar is reported rather than silently ignored.

Stdlib only, per `zero-dep-shim`. Each case is a throwaway git repository and
the shim driven as a subprocess.

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
CHANGE = "tagged-plan"

MANIFEST = (
    'gatesVersion: 1\n'
    'gates:\n'
    '  ci: "true"\n'
    '  unit: "true"\n'
    '  integration: "true"\n'
    '  verify: "true"\n'
    '  eval: "true"\n'
    '  confirm: "true"\n'
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


def _project(tmp, tasks, change=CHANGE, extra=None):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, ".gates.yaml", MANIFEST)
    _write(root, f"openspec/changes/{change}/.openspec.yaml", "schema: spec-driven\n")
    _write(root, f"openspec/changes/{change}/tasks.md", tasks)
    for rel, text in (extra or {}).items():
        _write(root, rel, text)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return root


def _validate(root):
    return subprocess.run([sys.executable, str(GATES_SHIM), "validate"], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=60)


def _plan(*lines):
    return "## 1. Group\n\n" + "".join(f"{x}\n" for x in lines)


class TestAValidTaggedPlan(unittest.TestCase):
    """Regression guarded: a correct plan refused, so tagging is impossible."""

    def test_every_form_on_declared_gates_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, _plan(
                "- [ ] 1.1 Unit work [oracle: unit]",
                "- [ ] 1.2 E2e work [oracle: integration]",
                "- [ ] 1.3 Guard [oracle: verify characterization]",
                "- [ ] 1.4 Docs [oracle: none]",
                "- [ ] 1.5 Untagged work",
                "- [ ] 1.6 Mentions [oracle: ci] mid-line, which is no tag",
            ))
            result = _validate(root)
            self.assertEqual(result.returncode, 0, result.stderr)


class TestAnExcludedGate(unittest.TestCase):
    """Regression guarded: a task "judged" by a gate that cannot judge one
    task (green at every commit, a surface probe, an advisory score, or the
    merged tree only) -- an oracle that can never go red for it."""

    def test_each_excluded_gate_fails_naming_the_task_and_the_gates_that_can(self):
        for gate in ("ci", "live-check", "eval", "confirm"):
            with self.subTest(gate=gate), tempfile.TemporaryDirectory() as tmp:
                root = _project(tmp, _plan(f"- [ ] 2.3 Work [oracle: {gate}]"))
                result = _validate(root)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(CHANGE, result.stderr)
                self.assertIn("2.3", result.stderr)
                self.assertIn(f"[oracle: {gate}]", result.stderr)
                self.assertIn("cannot judge one task", result.stderr)
                for can in ("unit", "integration", "verify"):
                    self.assertIn(can, result.stderr)


class TestAnUndeclaredGate(unittest.TestCase):
    """Regression guarded: a tag naming a gate the project never declared,
    so the red step has nothing to run."""

    def test_fails_naming_the_gate_and_the_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, _plan("- [ ] 5.1 Work [oracle: contract]"))
            result = _validate(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(CHANGE, result.stderr)
            self.assertIn("5.1", result.stderr)
            self.assertIn("contract", result.stderr)


class TestAMalformedTag(unittest.TestCase):
    """Regression guarded: a typo in a tag read as no tag at all, so the
    plan's declaration is silently dropped."""

    def test_each_malformed_tag_fails_naming_it(self):
        for tag in ("[oracle: unit sometimes]", "[oracle: none characterization]",
                    "[oracle:]", "[oracle: unit integration]"):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as tmp:
                root = _project(tmp, _plan(f"- [ ] 1.1 Work {tag}"))
                result = _validate(root)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(CHANGE, result.stderr)
                self.assertIn("1.1", result.stderr)
                self.assertIn(tag, result.stderr)

    def test_every_problem_is_listed_at_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, _plan(
                "- [ ] 1.1 A [oracle: ci]",
                "- [ ] 1.2 B [oracle: contract]",
                "- [ ] 1.3 C [oracle: unit maybe]",
            ))
            result = _validate(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            for tid in ("1.1", "1.2", "1.3"):
                self.assertIn(tid, result.stderr)


class TestALetteredId(unittest.TestCase):
    """Regression guarded: a lettered task (#46) whose tag is warned about and
    then ignored, so a wrong gate on it is never caught."""

    def test_a_tagged_lettered_task_draws_no_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, _plan(
                "- [ ] 1.2 Work [oracle: unit]",
                "- [ ] 1.2a Lettered [oracle: unit]",
            ))
            result = _validate(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("1.2a", result.stderr)
            self.assertNotIn("1.2a", result.stdout)

    def test_an_unknown_gate_on_a_lettered_task_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, _plan("- [ ] 1.2a Lettered [oracle: contract]"))
            result = _validate(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("1.2a", result.stderr)
            self.assertIn("contract", result.stderr)


class TestAnUnparsedLine(unittest.TestCase):
    """Regression guarded: a tag on a line whose id the task parser does not
    read, silently ignored."""

    def test_an_unnumbered_tagged_line_is_reported_naming_the_grammar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, _plan(
                "- [ ] 1.2 Work [oracle: unit]",
                "- [ ] Update the docs [oracle: unit]",
            ))
            result = _validate(root)
            self.assertIn("Update", result.stderr)
            self.assertIn("N.M or N.Ma", result.stderr)
            self.assertNotIn("#46", result.stderr)


class TestOnlyActiveChanges(unittest.TestCase):
    """Regression guarded: an archived plan, which nothing will run again,
    failing every later validate."""

    def test_an_archived_change_is_not_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(
                tmp, _plan("- [ ] 1.1 Work [oracle: unit]"),
                extra={"openspec/changes/archive/2026-01-01-old/tasks.md":
                       _plan("- [x] 1.1 Old [oracle: ci]")},
            )
            result = _validate(root)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
