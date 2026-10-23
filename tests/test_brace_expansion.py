"""Brace-expansion tests for the `gates` shim's `match` glob patterns
(design D2, `expand-brace-globs`).

Stdlib only, per `zero-dep-shim`: `bin/gates` has no `.py` suffix, so it is
loaded by path through SourceFileLoader rather than imported, matching the
pattern in test_manifest.py / test_selection.py.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_brace_expansion", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class TestNoBraces(unittest.TestCase):
    def test_pattern_with_no_brace_passes_through_unchanged(self):
        self.assertEqual(gates._expand_braces("bin/**"), ["bin/**"])

    def test_empty_string_passes_through(self):
        self.assertEqual(gates._expand_braces(""), [""])


class TestSingleGroup(unittest.TestCase):
    def test_two_alternatives(self):
        self.assertEqual(
            sorted(gates._expand_braces("{bin,tests}/**")),
            sorted(["bin/**", "tests/**"]),
        )

    def test_group_not_at_start(self):
        self.assertEqual(
            sorted(gates._expand_braces("docs/{a,b}/*.md")),
            sorted(["docs/a/*.md", "docs/b/*.md"]),
        )

    def test_single_alternative_group_is_not_an_error(self):
        # No comma inside the braces is still one well-formed alternative,
        # not a reason to reject the pattern.
        self.assertEqual(gates._expand_braces("{bin}/**"), ["bin/**"])


class TestMultipleGroups(unittest.TestCase):
    def test_two_groups_expand_to_the_full_cross_product(self):
        self.assertEqual(
            sorted(gates._expand_braces("{a,b}/{c,d}")),
            sorted(["a/c", "a/d", "b/c", "b/d"]),
        )


class TestNestedGroups(unittest.TestCase):
    def test_group_nested_inside_another(self):
        self.assertEqual(
            sorted(gates._expand_braces("{a,b{c,d}}/x")),
            sorted(["a/x", "bc/x", "bd/x"]),
        )


class TestUnbalancedBraceIsAnError(unittest.TestCase):
    def test_missing_close_brace_raises(self):
        with self.assertRaises(gates.BraceExpansionError):
            gates._expand_braces("{bin,tests/**")

    def test_missing_open_brace_is_not_an_error(self):
        # A stray '}' with no preceding unmatched '{' isn't a group at all;
        # only unresolvable '{' constructs are rejected.
        self.assertEqual(gates._expand_braces("bin}/**"), ["bin}/**"])


class TestEmptyGroupOrAlternativeIsAnError(unittest.TestCase):
    def test_empty_group_raises(self):
        with self.assertRaises(gates.BraceExpansionError):
            gates._expand_braces("{}/**")

    def test_empty_alternative_raises(self):
        with self.assertRaises(gates.BraceExpansionError):
            gates._expand_braces("{a,,b}/**")

    def test_leading_comma_empty_alternative_raises(self):
        with self.assertRaises(gates.BraceExpansionError):
            gates._expand_braces("{,a}/**")


class TestExpansionCapExceeded(unittest.TestCase):
    def test_pathological_pattern_raises_rather_than_hangs_or_blows_up(self):
        # 10 consecutive two-way groups is 2**10 = 1024 alternatives, over
        # the 512 cap.
        pattern = "{a,b}" * 10
        with self.assertRaises(gates.BraceExpansionError):
            gates._expand_braces(pattern)


if __name__ == "__main__":
    unittest.main()
