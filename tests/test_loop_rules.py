"""Tests for the plugin's built-in loop rules (`test-quality-rule`).

Stdlib only, per `zero-dep-shim`. `rules/loop-rules.md` ships inside the
plugin and every adopter's convention review reads it, so a stack name in it
breaks `stack-agnostic-prompts` for every project at once (design D3).

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import importlib.machinery
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
LOOP_RULES = REPO / "rules" / "loop-rules.md"

_loader = importlib.machinery.SourceFileLoader("gates_shim_loop_rules", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class TestLoopRulesNameNoStack(unittest.TestCase):
    """Regression guarded: an audit example (a framework, runner or library
    name) pasted into the shipped rule text. This is a lint over shipped
    prose, deliberately — the same tool-name scan `gates schema inspect`
    runs over a pack."""

    def test_shipped_rule_text_names_no_tool(self):
        self.assertEqual(gates.scan_tool_names(LOOP_RULES.read_text()), set())


# A manifest whose one surface the changed path below never matches, so no
# surface is hot: the built-in rule must still be listed.
COLD_MANIFEST = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: shim
    match: "bin/**"
    rules:
      - zero-dep-shim
"""
BUILTIN_PATH_LABEL = "Resolve built-in rule-ids against: "


@contextlib.contextmanager
def installed_plugin(rules_text):
    """A copy of the plugin laid out as an install cache holds it (the shim
    under `bin/`, the rules file under `rules/`), plus a separate project
    directory to run it from. `rules_text=None` ships no rules file.
    Yields (plugin_root, project_root)."""
    with tempfile.TemporaryDirectory() as tmp:
        plugin = Path(tmp) / "plugin-cache" / "gatedloop"
        (plugin / "bin").mkdir(parents=True)
        shutil.copy(GATES_SHIM, plugin / "bin" / "gates")
        if rules_text is not None:
            (plugin / "rules").mkdir()
            (plugin / "rules" / "loop-rules.md").write_text(rules_text)
        project = Path(tmp) / "project"
        project.mkdir()
        (project / ".gates.yaml").write_text(COLD_MANIFEST)
        yield plugin, project


def run_rules(plugin, project):
    return subprocess.run(
        [sys.executable, str(plugin / "bin" / "gates"), "rules", "--changed", "docs/x.md"],
        cwd=project, capture_output=True, text=True,
    )


class TestRulesListsBuiltInRule(unittest.TestCase):
    """Regression guarded: the built-in rule silently absent from review
    because `gates rules` only lists hot surfaces' rules, or resolves the
    rules file against the project instead of the installed plugin."""

    def test_cold_diff_lists_the_rule_and_a_plugin_path_that_defines_it(self):
        with installed_plugin(LOOP_RULES.read_text()) as (plugin, project):
            result = run_rules(plugin, project)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("gatedloop.test-quality", result.stdout)
            printed = [line[len(BUILTIN_PATH_LABEL):] for line in result.stdout.splitlines()
                       if line.startswith(BUILTIN_PATH_LABEL)]
            self.assertEqual(len(printed), 1, result.stdout)
            self.assertEqual(Path(printed[0]).resolve(),
                             (plugin / "rules" / "loop-rules.md").resolve())


class TestRulesFailsLoudWithoutTheBuiltInRule(unittest.TestCase):
    """Regression guarded: a plugin that lost its rules file or the rule's
    section still printing the id, so review cites a rule it cannot read
    and silently judges tests against nothing (fail-loud-gates, design D1).
    The present case is the test above."""

    def test_missing_rules_file_exits_non_zero_naming_the_file(self):
        with installed_plugin(None) as (plugin, project):
            result = run_rules(plugin, project)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("loop-rules.md", result.stderr)

    def test_missing_section_exits_non_zero_naming_the_rule(self):
        with installed_plugin("# gatedloop loop rules\n\n### gatedloop.other\n") as (plugin, project):
            result = run_rules(plugin, project)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("gatedloop.test-quality", result.stderr)


if __name__ == "__main__":
    unittest.main()
