"""`gates doctor` compares the OpenSpec CLI against a supported range
(stability-contract D7; the onboarding requirement "The OpenSpec contract
version is probed, not assumed").

The shim records `OPENSPEC_MIN` and `OPENSPEC_MAX_TESTED`. The regressions:
- a version inside a widened range still warned, because the check compares
  against one exact version, so widening the range takes a code change the
  constants were meant to replace;
- a version below the minimum or above the highest tested passing silently;
- the warning naming one version instead of the range an adopter can act on;
- an unparseable `openspec --version` crashing the doctor, or passing.

The range is patched onto the shim for each test, so the tests pin the
comparison rather than today's values (both are "1.14.3" until ci proves
another version). Stdlib only, per `zero-dep-shim`. Run with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_openspec_range", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

LOW, HIGH = "1.14.0", "1.16.2"


def _version_row(installed):
    with unittest.mock.patch.object(gates, "OPENSPEC_MIN", LOW, create=True), \
            unittest.mock.patch.object(gates, "OPENSPEC_MAX_TESTED", HIGH, create=True):
        checks = gates.doctor_checks(installed, 1, "/p")
    rows = [(level, detail) for level, title, detail in checks if title == "openspec-version"]
    if len(rows) != 1:
        raise AssertionError(f"expected one openspec-version row, got {rows}")
    return rows[0]


class DoctorRangeTest(unittest.TestCase):
    def test_a_version_inside_the_range_is_ok(self):
        for installed in (LOW, "1.15.7", HIGH):
            level, _detail = _version_row(installed)
            self.assertEqual(level, "ok", installed)

    def test_a_version_above_the_range_warns_naming_it_and_the_range(self):
        level, detail = _version_row("1.17.0")
        self.assertEqual(level, "warn")
        self.assertIn("1.17.0", detail)
        self.assertIn(LOW, detail)
        self.assertIn(HIGH, detail)

    def test_a_version_below_the_range_warns_naming_it_and_the_range(self):
        level, detail = _version_row("1.13.9")
        self.assertEqual(level, "warn")
        self.assertIn("1.13.9", detail)
        self.assertIn(LOW, detail)
        self.assertIn(HIGH, detail)

    def test_numeric_not_lexical_comparison(self):
        # "1.9.0" sorts after "1.14.0" as text; it is below the minimum.
        level, _detail = _version_row("1.9.0")
        self.assertEqual(level, "warn")

    def test_a_prerelease_of_a_version_in_range_is_compared_by_its_numbers(self):
        level, _detail = _version_row("1.15.0-rc.1")
        self.assertEqual(level, "ok")

    def test_an_unparseable_version_warns_and_never_raises(self):
        level, detail = _version_row("nightly")
        self.assertEqual(level, "warn")
        self.assertIn("nightly", detail)

    def test_the_doctor_stays_advisory(self):
        for installed in ("0.1.0", LOW, "9.9.9", "nightly"):
            level, _detail = _version_row(installed)
            self.assertIn(level, ("ok", "warn"), installed)


if __name__ == "__main__":
    unittest.main()
