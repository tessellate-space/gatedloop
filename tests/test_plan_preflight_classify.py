"""`gates plan classify <change> --verdict <file> | --unavailable <cause>`
(openspec change `plan-preflight`, design D3 "Fallback is visible"; task
5.7).

The built-in `gatedloop.blast-radius` lens's JSON is validated against the
verdict contract and stored in the preflight store as `classifier.json`,
keyed on the plan's digests; an invalid one is refused, naming every error,
and stores nothing. `--unavailable` records that no verdict could be had, and
the tier is then the floor. `gates plan tier` uses a stored verdict only for
the plan it was stored for.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, PreflightRepo, write  # noqa: E402

FULL = {"tier": "light", "confidence": 0.9,
        "evidence": [{"dimension": "public-interface", "value": 0.7, "confidence": 0.8}],
        "reason": "changes the widget's public signature"}


class PlanClassifyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.r = PreflightRepo(self.tmp / "work")

    def tearDown(self):
        self._tmp.cleanup()

    def classify(self, obj) -> object:
        f = write(self.tmp, "verdict.json", obj if isinstance(obj, str) else json.dumps(obj))
        return self.r.gates("plan", "classify", CHANGE, "--verdict", str(f))

    def tier(self) -> dict:
        out = self.r.gates("plan", "tier", CHANGE, "--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_a_valid_verdict_is_stored_and_used(self):
        out = self.classify(FULL)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue((self.r.store / "classifier.json").is_file())
        doc = self.tier()
        c = doc["classifier"]
        self.assertEqual((c["provider"], c["cause"], c["raised_by"]),
                         ("builtin", "none-declared", "public-interface"))
        self.assertEqual(c["reason"], FULL["reason"])
        self.assertEqual((doc["floor"], doc["tier"]), ("light", "full"))
        self.assertEqual(self.r.status(), "")

    def test_an_invalid_verdict_is_refused_naming_every_error(self):
        out = self.classify({"tier": "medium", "confidence": 3, "evidence": []})
        self.assertEqual(out.returncode, 1)
        self.assertIn("tier must be", out.stderr)
        self.assertIn("confidence must be", out.stderr)
        self.assertFalse((self.r.store / "classifier.json").exists())
        self.assertEqual(self.classify("not json").returncode, 1)
        self.assertIsNone(self.tier()["classifier"]["tier"])

    def test_a_stale_verdict_is_ignored(self):
        self.assertEqual(self.classify(FULL).returncode, 0)
        self.r.edit(f"{self.r.rel_dir}/tasks.md", "Add the widget", "Add the small widget")
        doc = self.tier()
        self.assertIsNone(doc["classifier"]["tier"])
        self.assertEqual(doc["tier"], "light")

    def test_an_unavailable_cause_is_reported_and_the_tier_is_the_floor(self):
        out = self.r.gates("plan", "classify", CHANGE, "--unavailable", "lens returned invalid twice")
        self.assertEqual(out.returncode, 0, out.stderr)
        doc = self.tier()
        self.assertEqual(doc["classifier"]["unavailable"], "lens returned invalid twice")
        self.assertEqual(doc["tier"], doc["floor"])

    def test_exactly_one_mode(self):
        self.assertEqual(self.r.gates("plan", "classify", CHANGE).returncode, 1)


if __name__ == "__main__":
    unittest.main()
