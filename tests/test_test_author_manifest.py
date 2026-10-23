"""`loop.test-author` manifest validation and the `Applies to: tests`
review-only target (split-test-author tasks 1.1, 1.2; design D6, D9).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_test_author_manifest", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

BASE_MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _parsers():
    """Both manifest parsers: the built-in fallback always, PyYAML when
    importable. A regression in either corrupts validation for someone."""
    out = [("mini", gates._mini_yaml)]
    try:
        import yaml
        out.append(("pyyaml", yaml.safe_load))
    except ImportError:
        pass
    return out


class TestLoopTestAuthorValidation(unittest.TestCase):
    def _errors(self, parse, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            return gates._errors(parse(text), Path(tmp))

    def test_declared_values_validate(self):
        for pname, parse in _parsers():
            for value in ("separate", "inline"):
                with self.subTest(parser=pname, value=value):
                    text = BASE_MANIFEST + f"loop:\n  test-author: {value}\n"
                    self.assertEqual(self._errors(parse, text), [])

    def test_unknown_value_fails_naming_key_and_allowed_values(self):
        for pname, parse in _parsers():
            with self.subTest(parser=pname):
                text = BASE_MANIFEST + "loop:\n  test-author: pair\n"
                errs = self._errors(parse, text)
                self.assertTrue(
                    any("loop.test-author" in e and "separate" in e and "inline" in e
                        and "pair" in e for e in errs),
                    f"expected a loop.test-author error naming both values, got: {errs}",
                )

    def test_misspelled_loop_key_fails_rather_than_defaulting(self):
        # A typo would otherwise silently leave the project on `separate`.
        for pname, parse in _parsers():
            with self.subTest(parser=pname):
                text = BASE_MANIFEST + "loop:\n  test_author: inline\n"
                errs = self._errors(parse, text)
                self.assertTrue(any("test_author" in e for e in errs), errs)


# A rules-doc with one project test rule and one surface rule.
RULES_DOC = """\
# Conventions

### tests-live-beside-code
Applies to: tests
Rule: Put each test beside the module it covers, named after it.

Prose.

### small-functions
Applies to: code, design
Rule: Keep functions small.
"""

MANIFEST_WITH_SURFACE = """\
gatesVersion: 1
gates:
  ci: "true"
surfaces:
  - name: shim
    match: "bin/**"
    rules:
      - small-functions
conventions:
  rules-doc: docs/conventions.md
"""


class TestTestsIsAReviewOnlyTarget(unittest.TestCase):
    """Regressions guarded: a `tests` rule leaking into OpenSpec's artifact
    instructions (a schema that happens to declare a `tests` artifact would
    otherwise receive it), `gates validate` rejecting the target, and review
    missing a project test rule because no surface that lists it is hot."""

    def test_sync_never_emits_a_tests_rule_even_for_a_tests_artifact(self):
        sections = gates.parse_conventions_doc(RULES_DOC)
        by_artifact = gates.build_rules_by_artifact(sections, ["design", "tests"])
        self.assertEqual(by_artifact, {"design": ["Keep functions small."]})

    def test_validate_accepts_the_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "docs").mkdir()
            (Path(tmp) / "docs" / "conventions.md").write_text(RULES_DOC)
            m = gates._mini_yaml(MANIFEST_WITH_SURFACE)
            self.assertEqual(gates._errors(m, Path(tmp)), [])

    def test_rules_lists_tests_rules_when_no_surface_is_hot(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "docs").mkdir()
            (project / "docs" / "conventions.md").write_text(RULES_DOC)
            (project / ".gates.yaml").write_text(MANIFEST_WITH_SURFACE)
            result = subprocess.run(
                [sys.executable, str(GATES_SHIM), "rules", "--changed", "README.md"],
                cwd=project, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("tests-live-beside-code", result.stdout)
        self.assertNotIn("small-functions", result.stdout)


if __name__ == "__main__":
    unittest.main()
