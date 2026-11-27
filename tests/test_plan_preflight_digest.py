"""`gates plan digest <change> [--json] [--limit N]` (openspec change
`plan-preflight`, design D3 "The digest"; task 5.2).

The digest is built deterministically, in priority order: signals and
floor; named paths with surface and `blast-radius`; spec delta section
headers with requirement titles; task lines without tags or checkboxes;
"What Changes" bullets (first lines); decision headings. Its compact JSON is
exactly what an external classifier receives as `digest`.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, GATES_SHIM, MANIFEST, PreflightRepo  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("gates_shim_pf_digest", str(GATES_SHIM))
gates = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(gates)

SURFACED = MANIFEST + 'surfaces:\n  - name: core\n    match: "src/**"\n    blast-radius: high\n'
SPEC = """\
# Spec Delta

## ADDED Requirements

### Requirement: Widgets widget

#### Scenario: Widgeting

## MODIFIED Requirements

### Requirement: Gadgets gadget
### Requirement: Gadgets rest
"""


class PlanDigestTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.r = PreflightRepo(self._tmp.name, manifest=SURFACED, specs={"widget": SPEC})

    def tearDown(self):
        self._tmp.cleanup()

    def digest(self, *extra) -> tuple[str, dict]:
        out = self.r.gates("plan", "digest", CHANGE, "--json", *extra)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return out.stdout, json.loads(out.stdout)

    def test_a_digest_that_fits_has_every_section_and_nothing_trimmed(self):
        _raw, d = self.digest("--limit", "48000")
        self.assertEqual(list(d), ["change", "floor", "signals", "paths", "spec_deltas", "tasks",
                                   "what_changes", "decisions", "trimmed"])
        self.assertEqual(d["trimmed"], [])
        self.assertEqual(d["floor"], "full")
        self.assertEqual(d["paths"][0], {"path": "src/widget.py", "surfaces": ["core"],
                                         "blast_radius": "high"})
        self.assertEqual(d["spec_deltas"], [
            {"file": "specs/widget/spec.md", "section": "ADDED", "requirements": ["Widgets widget"]},
            {"file": "specs/widget/spec.md", "section": "MODIFIED",
             "requirements": ["Gadgets gadget", "Gadgets rest"]}])
        self.assertEqual(d["tasks"], ["1.1 Add the widget in `src/widget.py`",
                                      "1.2 Rework the gadget test",
                                      "2.1 Document the widget in `docs/widget.md`"])
        self.assertEqual(d["what_changes"], ["**Add a widget.** It widgets.", "**Document it.**"])
        self.assertEqual(d["decisions"], ["D1. The widget lives in `src/widget.py`",
                                          "D2. The gadget test moves"])

    def test_the_same_plan_gives_the_same_bytes(self):
        self.assertEqual(self.digest()[0], self.digest()[0])

    def test_the_classifier_input_carries_the_printed_bytes_verbatim(self):
        raw, d = self.digest("--limit", "48000")
        m = gates._parse_yaml_text(SURFACED)
        dims = gates._plan_tier_dimensions()
        stdin = gates._plan_classifier_input(gates._plan_digest(m, self.r.root, CHANGE, 48000)[0], dims)
        printed = raw.rstrip("\n").encode()
        self.assertTrue(stdin.startswith(b'{"digest":' + printed + b',"dimensions":'))
        self.assertEqual(json.loads(stdin), {"digest": d, "dimensions": dims})

    def test_the_text_form_names_every_section(self):
        out = self.r.gates("plan", "digest", CHANGE)
        self.assertEqual(out.returncode, 0, out.stderr)
        for title in ("paths:", "spec deltas:", "tasks:", "what changes:", "decisions:"):
            self.assertIn(title, out.stdout)
        self.assertIn("1.2 Rework the gadget test", out.stdout)


if __name__ == "__main__":
    unittest.main()
