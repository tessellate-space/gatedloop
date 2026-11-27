"""A classifier verdict is combined by the shim, dimension by dimension
(openspec change `plan-preflight`, design D3 "Layer 2"; task 5.6).

`full` when the verdict's own tier is `full`, or when any evidence item for
a known, enabled dimension meets its threshold (`probability` at or above,
`choice` equal to the raising option); `light` otherwise. The manifest's
`dimensions` overrides change a threshold or turn a dimension `off`; an
unknown dimension is recorded and ignored; confidences are reported and
never lower the tier.

Stdlib only, per `zero-dep-shim`. Real git repositories, a fixture
classifier command, the shim driven as a subprocess. Run with:
python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, MANIFEST, PreflightRepo, write  # noqa: E402

ECHO_CLASSIFIER = "import os\nprint(os.environ['PF_VERDICT'])\n"


def verdict(tier="light", confidence=0.6, evidence=(), **extra) -> str:
    return json.dumps({"tier": tier, "confidence": confidence, "evidence": list(evidence), **extra})


def ev(dimension, value, confidence=0.5) -> dict:
    return {"dimension": dimension, "value": value, "confidence": confidence}


class CombineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.script = write(self.tmp, "fixture/classify.py", ECHO_CLASSIFIER)
        self.n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def classify(self, raw: str, dimensions: str = "") -> dict:
        self.n += 1
        cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(self.script))}"
        manifest = (MANIFEST + "loop:\n  plan-preflight:\n    classifier: " + json.dumps(cmd) + "\n"
                    + (("    dimensions:\n" + dimensions) if dimensions else ""))
        r = PreflightRepo(self.tmp / f"work{self.n}", manifest=manifest)
        out = r.gates("plan", "tier", CHANGE, "--json", PF_VERDICT=raw)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        doc = json.loads(out.stdout)
        self.assertEqual(doc["floor"], "light")
        return doc

    def test_dimension_answers_raise_a_light_verdict(self):
        doc = self.classify(verdict(evidence=[ev("persisted-data", 0.8), ev("security-path", 0.1)]))
        c = doc["classifier"]
        self.assertEqual((c["tier"], c["combined"], c["raised_by"], doc["tier"]),
                         ("light", "full", "persisted-data", "full"))

    def test_a_choice_dimension_raises_on_its_option(self):
        doc = self.classify(verdict(evidence=[ev("overall-tier", "full")]))
        self.assertEqual(doc["classifier"]["raised_by"], "overall-tier")

    def test_a_threshold_override_stops_the_raise(self):
        doc = self.classify(verdict(evidence=[ev("persisted-data", 0.8)]),
                            dimensions="      persisted-data: 0.9\n")
        self.assertEqual((doc["classifier"]["combined"], doc["tier"]), ("light", "light"))

    def test_a_dimension_turned_off(self):
        doc = self.classify(verdict(evidence=[ev("irreversible", 1.0)]),
                            dimensions="      irreversible: off\n")
        c = doc["classifier"]
        self.assertEqual((c["combined"], c["unknown_dimensions"]), ("light", []))

    def test_an_unknown_dimension_is_recorded_and_ignored(self):
        doc = self.classify(verdict(evidence=[ev("reach", 0.99)]))
        c = doc["classifier"]
        self.assertEqual((c["combined"], c["unknown_dimensions"]), ("light", ["reach"]))

    def test_a_verdict_with_no_reason_is_recorded_with_none(self):
        doc = self.classify(verdict())
        self.assertEqual((doc["classifier"]["provider"], doc["classifier"]["reason"]),
                         ("external", None))

    def test_confidences_are_reported(self):
        doc = self.classify(verdict(confidence=0.42, evidence=[ev("public-interface", 0.3, 0.77)]))
        c = doc["classifier"]
        self.assertEqual(c["confidence"], 0.42)
        self.assertEqual(c["evidence"], [ev("public-interface", 0.3, 0.77)])

    def test_a_low_confidence_full_verdict_still_raises(self):
        doc = self.classify(verdict(tier="full", confidence=0.05))
        self.assertEqual((doc["classifier"]["raised_by"], doc["tier"]), ("tier", "full"))


if __name__ == "__main__":
    unittest.main()
