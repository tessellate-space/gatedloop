"""`gates plan tier <change> [--json]` (openspec change `plan-preflight`,
design D3; task 4.4).

The floor is `full` when any one of six signals is high (task lines, named
paths, hot surfaces, a spec delta changing existing requirements, an oracle
tag naming a declared costly gate, a hot `blast-radius: high` surface), and
`light` otherwise. The plan's `Plan tier: full` line raises it; a `Plan
tier: light — <reason>` line lowers it, and a light line with no reason is
a `gates plan check` finding.

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

from _preflight_fixture import CHANGE, GATES_SHIM, PreflightRepo  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("gates_shim_pf_tier", str(GATES_SHIM))
gates = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(gates)

BASE = ('gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
        '  integration: "true"\n  e2e: "true"\n')
SURFACES = ('surfaces:\n  - name: core\n    match: "src/**"\n'
            '  - name: docs\n    match: "docs/**"\n')
LIGHT_TASKS = "- [ ] 1.1 Add the widget in `src/widget.py` [oracle: unit]\n"
MODIFIED_SPEC = """\
# Spec Delta

## MODIFIED Requirements

### Requirement: Widgets widget

The system SHALL widget twice.
"""


def preflight(block: str) -> str:
    return "loop:\n  plan-preflight:\n" + block


class PlanTierTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def repo(self, manifest=BASE + SURFACES, tasks=LIGHT_TASKS, **kw) -> PreflightRepo:
        return PreflightRepo(self._tmp.name, manifest=manifest, tasks=tasks, **kw)

    def tier(self, r: PreflightRepo) -> dict:
        out = r.gates("plan", "tier", CHANGE, "--json")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return json.loads(out.stdout)

    def high(self, doc) -> list[str]:
        return [s["id"] for s in doc["signals"] if s["high"]]

    def test_a_light_floor(self):
        r = self.repo()
        doc = self.tier(r)
        self.assertEqual((doc["floor"], doc["tier"], self.high(doc)), ("light", "light", []))
        self.assertEqual([s["id"] for s in doc["signals"]],
                         ["tasks", "files", "surfaces", "existing-requirements",
                          "costly-oracle", "blast-radius"])
        self.assertEqual(set(doc), {"floor", "signals", "classifier", "override", "tier"})
        text = r.gates("plan", "tier", CHANGE)
        self.assertEqual(text.returncode, 0)
        self.assertIn("floor: light", text.stdout)

    def test_each_signal_alone_makes_the_floor_full(self):
        many = "".join(f"- [ ] 1.{i} Step {i} [oracle: unit]\n" for i in range(1, 4))
        cases = {
            "tasks": dict(manifest=BASE + SURFACES + preflight("    full-at:\n      tasks: 3\n"),
                          tasks=many),
            "files": dict(manifest=BASE + SURFACES + preflight("    full-at:\n      files: 2\n"),
                          tasks="- [ ] 1.1 Edit `notes/a.txt` and `notes/b.txt` [oracle: unit]\n"),
            "surfaces": dict(tasks="- [ ] 1.1 Edit `src/a.py` and `docs/a.md` [oracle: unit]\n"),
            "existing-requirements": dict(specs={"widget": MODIFIED_SPEC}),
            "costly-oracle": dict(manifest=BASE + SURFACES + preflight("    full-at:\n      oracles: [e2e]\n"),
                                  tasks="- [ ] 1.1 Drive the widget [oracle: e2e]\n"),
            "blast-radius": dict(manifest=BASE + SURFACES.replace(
                'match: "src/**"\n', 'match: "src/**"\n    blast-radius: high\n')),
        }
        for signal, kw in cases.items():
            with self.subTest(signal), tempfile.TemporaryDirectory() as tmp:
                kw.setdefault("manifest", BASE + SURFACES)
                kw.setdefault("tasks", LIGHT_TASKS)
                doc = self.tier(PreflightRepo(tmp, **kw))
                self.assertEqual(self.high(doc), [signal])
                self.assertEqual(doc["floor"], "full")

    def test_twelve_unit_tasks_on_one_surface_stay_light(self):
        tasks = "".join(f"- [ ] 1.{i} Step {i} in `src/mod{i % 3}.py` [oracle: unit]\n"
                        for i in range(1, 13))
        doc = self.tier(self.repo(tasks=tasks))
        self.assertEqual(doc["floor"], "light")
        self.assertEqual(doc["signals"][0]["value"], 12)

    def test_an_integration_tag_with_no_list_declared_stays_low(self):
        doc = self.tier(self.repo(tasks="- [ ] 1.1 Wire it [oracle: integration rewrites: tests/test_gadget.py]\n"))
        self.assertEqual(self.high(doc), [])

    def test_a_declared_list_makes_a_rewrite_costly(self):
        m = BASE + SURFACES + preflight("    full-at:\n      oracles: [e2e]\n")
        doc = self.tier(self.repo(manifest=m, tasks="- [ ] 1.2 Rework [oracle: unit rewrites: tests/test_gadget.py]\n"))
        self.assertEqual(self.high(doc), ["costly-oracle"])
        self.assertEqual(doc["signals"][4]["value"], ["1.2"])

    def test_the_oracles_list_reads_alike_under_both_parsers(self):
        text = BASE + SURFACES + preflight("    full-at:\n      oracles: [e2e, integration]\n")
        r = self.repo(manifest=text, tasks="- [ ] 1.1 Drive [oracle: integration]\n")
        docs = [gates._plan_tier_doc(m, r.root, CHANGE)
                for m in (gates._parse_yaml_text(text), gates._mini_yaml(text))]
        self.assertEqual(docs[0], docs[1])
        self.assertEqual(docs[0]["floor"], "full")

    def test_a_threshold_override_from_the_manifest(self):
        tasks = "- [ ] 1.1 Edit `src/a.py` and `docs/a.md` [oracle: unit]\n"
        m = BASE + SURFACES + preflight("    full-at:\n      surfaces: 3\n")
        doc = self.tier(self.repo(manifest=m, tasks=tasks))
        self.assertEqual(doc["floor"], "light")
        self.assertEqual(doc["signals"][2]["threshold"], 3)

    def test_the_plan_line_raises(self):
        r = self.repo(design="# Design\n\nPlan tier: full\n")
        doc = self.tier(r)
        self.assertEqual((doc["floor"], doc["tier"]), ("light", "full"))
        self.assertEqual(doc["override"], {"source": "raised-plan", "reason": None})

    def test_lowering_with_a_reason(self):
        r = self.repo(specs={"widget": MODIFIED_SPEC},
                      proposal="# Proposal\n\nPlan tier: light — a one-word rename of a heading\n")
        doc = self.tier(r)
        self.assertEqual((doc["floor"], doc["tier"]), ("full", "light"))
        self.assertEqual(doc["override"], {"source": "lowered-plan",
                                           "reason": "a one-word rename of a heading"})
        self.assertEqual(r.gates("plan", "check", CHANGE).returncode, 0)

    def test_lowering_without_a_reason_is_a_plan_check_finding(self):
        r = self.repo(specs={"widget": MODIFIED_SPEC}, design="# Design\n\nPlan tier: light\n")
        doc = self.tier(r)
        self.assertEqual(doc["tier"], "full")
        out = r.gates("plan", "check", CHANGE, "--json")
        self.assertEqual(out.returncode, 1)
        check = json.loads(out.stdout)
        self.assertEqual([f["kind"] for f in check["findings"]], ["tier-lower-unreasoned"])
        self.assertEqual(check["tier"], doc)

    def test_the_classifier_is_reported_as_not_yet_run(self):
        doc = self.tier(self.repo())
        self.assertIsNone(doc["classifier"]["tier"])


if __name__ == "__main__":
    unittest.main()
