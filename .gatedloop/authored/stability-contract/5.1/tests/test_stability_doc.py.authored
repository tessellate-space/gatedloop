"""`docs/stability.md` and the code state the same supported environment
(stability-contract D7, D8).

The page declares the supported environment, and the shim's range constants
are what `gates doctor` compares against. The regressions:
- the shim's OpenSpec range moves and the page still states the old one, so
  adopters read a range nobody tests (the spec's "The page and the code
  drift" scenario);
- README.md or SETUP.md state a different minimum Python or OpenSpec range
  from the page;

The page states the range on one line of this form, which the test reads:

    - **OpenSpec CLI:** `<min>` (minimum) to `<max>` (highest tested)

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
PAGE = REPO / "docs" / "stability.md"

_loader = importlib.machinery.SourceFileLoader("gates_shim_stability_doc", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

RANGE_LINE = re.compile(
    r"^- \*\*OpenSpec CLI:\*\* `(\d+\.\d+\.\d+)` \(minimum\) to `(\d+\.\d+\.\d+)` \(highest tested\)",
    re.MULTILINE,
)
PYTHON_LINE = re.compile(r"^- \*\*Python:\*\* (\d+\.\d+) or later", re.MULTILINE)


def _page() -> str:
    if not PAGE.is_file():
        raise AssertionError(f"{PAGE.relative_to(REPO)} does not exist")
    return PAGE.read_text()


class SupportedEnvironmentTest(unittest.TestCase):
    def test_the_pages_openspec_range_is_the_shims(self):
        found = RANGE_LINE.findall(_page())
        self.assertEqual(len(found), 1, "the page must state the OpenSpec range on exactly one line")
        (low, high), = found
        self.assertEqual((low, high), (gates.OPENSPEC_MIN, gates.OPENSPEC_MAX_TESTED),
                         f"docs/stability.md states {low}..{high}; the shim declares "
                         f"{gates.OPENSPEC_MIN}..{gates.OPENSPEC_MAX_TESTED}")

    def test_readme_and_setup_state_the_same_minimum_python_and_range(self):
        page = _page()
        python = PYTHON_LINE.findall(page)
        self.assertEqual(len(python), 1, "the page must state the minimum Python on exactly one line")
        (minimum,) = python
        for rel in ("README.md", "SETUP.md"):
            text = (REPO / rel).read_text()
            self.assertIn(f"Python {minimum}+", text, rel)
            self.assertIn(gates.OPENSPEC_MIN, text, rel)
            self.assertIn(gates.OPENSPEC_MAX_TESTED, text, rel)
            self.assertIn("docs/stability.md", text, f"{rel} does not point at the stability page")



if __name__ == "__main__":
    unittest.main()
