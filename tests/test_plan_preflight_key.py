"""`loop.plan-preflight` in `.gates.yaml` (openspec change `plan-preflight`,
design D12; task 4.1).

A scalar (`run` | `skip`) or a mapping with `mode`, `rounds`, `full-at`,
`classifier`, `classifier-timeout`, `classifier-input-limit` and
`dimensions`. Both forms must read the same under PyYAML and under the
zero-dependency `_mini_yaml` fallback (a conditional path: a defect there is
invisible wherever PyYAML is installed), and `on`, which the two parsers
read differently, is refused under both.

Stdlib only, per `zero-dep-shim`. Run with:
python3 -m unittest discover -s tests
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

_loader = importlib.machinery.SourceFileLoader("gates_shim_pf_key", str(GATES_SHIM))
gates = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(gates)

DEFAULTS = {
    "mode": "skip", "rounds": 3,
    "full-at": {"tasks": 20, "files": 12, "surfaces": 2, "oracles": []},
    "classifier": None, "classifier-timeout": 60, "classifier-input-limit": 48000,
    "dimensions": {},
}

FULL = MANIFEST + """\
loop:
  plan-preflight:
    mode: run
    rounds: 4
    full-at:
      tasks: 30
      files: 9
      surfaces: 3
      oracles: [e2e, integration]
    classifier: "python3 scripts/classify.py --fast"
    classifier-timeout: 15
    classifier-input-limit: 20000
    dimensions:
      persisted-data: 0.3
      irreversible: off
      overall-tier: full
"""


def parsers(text: str):
    """The manifest read by PyYAML and by `_mini_yaml` (the fallback forced)."""
    return (("pyyaml", gates._parse_yaml_text(text)), ("mini", gates._mini_yaml(text)))


def errors(m) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        return [e for e in gates._errors(m, Path(tmp)) if "plan-preflight" in e]


def loop(block: str) -> str:
    return MANIFEST + "loop:\n" + block


class PlanPreflightKeyTest(unittest.TestCase):
    def test_absent_is_every_default(self):
        for name, m in parsers(MANIFEST):
            with self.subTest(name):
                self.assertEqual(gates._plan_preflight_settings(m), DEFAULTS)
                self.assertEqual(errors(m), [])

    def test_scalar_forms(self):
        for value in ("run", "skip"):
            for name, m in parsers(loop(f"  plan-preflight: {value}\n")):
                with self.subTest(value=value, parser=name):
                    self.assertEqual(errors(m), [])
                    self.assertEqual(gates._plan_preflight_settings(m), {**DEFAULTS, "mode": value})

    def test_full_mapping_reads_identically(self):
        want = {
            "mode": "run", "rounds": 4,
            "full-at": {"tasks": 30, "files": 9, "surfaces": 3, "oracles": ["e2e", "integration"]},
            "classifier": "python3 scripts/classify.py --fast",
            "classifier-timeout": 15, "classifier-input-limit": 20000,
            "dimensions": {"persisted-data": 0.3, "irreversible": "off", "overall-tier": "full"},
        }
        for name, m in parsers(FULL):
            with self.subTest(name):
                self.assertEqual(errors(m), [])
                self.assertEqual(gates._plan_preflight_settings(m), want)

    def test_partial_mapping_fills_the_rest(self):
        text = loop("  plan-preflight:\n    mode: run\n    full-at:\n      files: 5\n")
        for name, m in parsers(text):
            with self.subTest(name):
                self.assertEqual(errors(m), [])
                got = gates._plan_preflight_settings(m)
                self.assertEqual(got["full-at"], {"tasks": 20, "files": 5, "surfaces": 2, "oracles": []})
                self.assertEqual(got["rounds"], 3)
                self.assertEqual(got["classifier-input-limit"], 48000)

    def test_on_is_refused_alike(self):
        for text in (loop("  plan-preflight: on\n"), loop("  plan-preflight:\n    mode: on\n")):
            results = []
            for name, m in parsers(text):
                errs = errors(m)
                self.assertEqual(len(errs), 1, (name, errs))
                self.assertIn("'run' or 'skip'", errs[0])
                results.append(gates._plan_preflight_settings(m)["mode"])
            self.assertEqual(results, ["skip", "skip"])

    def assert_refused(self, block: str, *needles: str):
        for name, m in parsers(loop(block)):
            with self.subTest(block=block, parser=name):
                errs = errors(m)
                self.assertEqual(len(errs), 1, errs)
                for n in needles:
                    self.assertIn(n, errs[0])

    def test_each_refusal(self):
        pp = "  plan-preflight:\n"
        self.assert_refused("  plan-preflight: always\n", "'run' or 'skip'")
        self.assert_refused(pp + "    mode: never\n", "loop.plan-preflight.mode")
        self.assert_refused(pp + "    budget: 3\n", "unknown key 'budget'")
        self.assert_refused(pp + "    full-at:\n      lines: 3\n", "full-at has an unknown key 'lines'")
        self.assert_refused(pp + "    rounds: 0\n", "loop.plan-preflight.rounds")
        self.assert_refused(pp + "    rounds: true\n", "loop.plan-preflight.rounds")
        self.assert_refused(pp + "    classifier-timeout: -5\n", "classifier-timeout")
        self.assert_refused(pp + "    classifier-input-limit: false\n", "classifier-input-limit")
        self.assert_refused(pp + "    full-at:\n      tasks: 0\n", "full-at.tasks")
        self.assert_refused(pp + "    full-at:\n      oracles: e2e\n", "full-at.oracles")
        self.assert_refused(pp + '    classifier: ""\n', "loop.plan-preflight.classifier")
        self.assert_refused(pp + "    dimensions:\n      reach: 0.5\n", "unknown dimension 'reach'")
        self.assert_refused(pp + "    dimensions:\n      persisted-data: 1.5\n", "persisted-data")
        self.assert_refused(pp + "    dimensions:\n      overall-tier: medium\n", "overall-tier")

    def test_run_with_an_inline_author_names_both_keys(self):
        for block in ("  test-author: inline\n  plan-preflight: run\n",
                      "  test-author: inline\n  plan-preflight:\n    mode: run\n"):
            self.assert_refused(block, "loop.plan-preflight", "loop.test-author")
        for name, m in parsers(loop("  test-author: inline\n  plan-preflight: skip\n")):
            self.assertEqual(errors(m), [], name)

    def test_gates_validate_refuses_on_a_real_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = PreflightRepo(tmp, manifest=loop("  plan-preflight: on\n"))
            out = r.gates("validate")
            self.assertEqual(out.returncode, 1)
            self.assertIn("loop.plan-preflight", out.stdout + out.stderr)

    def test_plan_check_reports_the_effective_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = PreflightRepo(tmp, manifest=loop("  plan-preflight:\n    mode: run\n"))
            out = r.gates("plan", "check", CHANGE, "--json")
            self.assertEqual(json.loads(out.stdout)["preflight"], "run", out.stderr)


if __name__ == "__main__":
    unittest.main()
