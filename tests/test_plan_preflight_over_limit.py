"""A plan digest still over the limit after trimming is `full`, with no
classifier call (openspec change `plan-preflight`, design D3; task 5.5).

When the signals, floor, named paths and spec delta headers alone exceed
`classifier-input-limit`, no classifier runs and no built-in fallback is
asked for: the most a classifier could do is raise the tier to `full`, so
the shim takes `full` and records `classifier: skipped, cause: digest over
limit`.

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

MARKER_CLASSIFIER = """\
import os, sys
open(os.environ["PF_RAN_FILE"], "w").write("ran")
print('{"tier": "light", "confidence": null, "evidence": []}')
"""


class OverLimitTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        script = write(self.tmp, "fixture/classify.py", MARKER_CLASSIFIER)
        self.ran = self.tmp / "ran.txt"
        cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
        self.manifest = (MANIFEST + "loop:\n  plan-preflight:\n    classifier: " + json.dumps(cmd)
                         + "\n    classifier-input-limit: {limit}\n")

    def tearDown(self):
        self._tmp.cleanup()

    def tier(self, limit: int) -> tuple[dict, str]:
        r = PreflightRepo(self.tmp / f"work-{limit}", manifest=self.manifest.format(limit=limit))
        doc = r.gates("plan", "tier", CHANGE, "--json", PF_RAN_FILE=str(self.ran))
        text = r.gates("plan", "tier", CHANGE, PF_RAN_FILE=str(self.ran))
        self.assertEqual((doc.returncode, text.returncode), (0, 0), doc.stderr + text.stderr)
        return json.loads(doc.stdout), text.stdout

    def test_over_the_limit_skips_the_classifier_and_is_full(self):
        doc, text = self.tier(50)
        self.assertFalse(self.ran.exists())
        self.assertEqual(doc["floor"], "light")
        self.assertEqual(doc["tier"], "full")
        c = doc["classifier"]
        self.assertEqual((c["provider"], c["cause"], c["combined"]),
                         ("skipped", "digest over limit", "full"))
        self.assertIn("classifier: skipped, cause: digest over limit", text)

    def test_within_the_limit_the_classifier_runs(self):
        doc, _text = self.tier(48000)
        self.assertTrue(self.ran.exists())
        self.assertEqual((doc["classifier"]["provider"], doc["tier"]), ("external", "light"))


if __name__ == "__main__":
    unittest.main()
