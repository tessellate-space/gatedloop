"""An over-limit plan digest is trimmed from the bottom (openspec change
`plan-preflight`, design D3 "The digest"; task 5.3).

Decision headings go first, then "What Changes" bullets, then task lines,
each from its last entry up, until the compact JSON fits; `trimmed` names
each section and how many entries it lost, and `gates plan tier --json`
reports the trim in its classifier block.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import hashlib
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

_loader = importlib.machinery.SourceFileLoader("gates_shim_pf_trim", str(GATES_SHIM))
gates = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(gates)

TASKS = "".join(f"- [ ] 1.{i} Step number {i} of the long plan [oracle: unit]\n" for i in range(1, 11))
DESIGN = "# Design\n\n" + "".join(f"### D{i}. Decision number {i}\n\nBody.\n\n" for i in range(1, 11))
PROPOSAL = "# Proposal\n\n## Why\n\nBecause.\n"
WITH_CHANGES = PROPOSAL + ("\n## What Changes\n\n"
                           "- **One.** The first change, described at some length so it outweighs a trim record.\n"
                           "- **Two.** The second change, described at some length so it outweighs a trim record.\n")


def size(d: dict) -> int:
    return len(gates._compact_json(d).encode())


class DigestTrimTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def repo(self, manifest=MANIFEST, proposal=PROPOSAL) -> PreflightRepo:
        return PreflightRepo(self._tmp.name, manifest=manifest, tasks=TASKS, design=DESIGN,
                             proposal=proposal)

    def full(self, r) -> dict:
        return gates._plan_digest(gates._parse_yaml_text(MANIFEST), r.root, CHANGE)[0]

    def limit_for(self, full: dict, decisions: int, tasks: int) -> int:
        """The size of `full` after dropping its last `decisions` decision
        headings and `tasks` task lines, with the trim recorded."""
        d = json.loads(json.dumps(full))
        d["decisions"] = d["decisions"][:len(d["decisions"]) - decisions]
        d["tasks"] = d["tasks"][:len(d["tasks"]) - tasks]
        d["trimmed"] = [{"section": "decisions", "lost": decisions},
                        {"section": "tasks", "lost": tasks}]
        return size(d)

    def digest(self, r, limit: int) -> dict:
        out = r.gates("plan", "digest", CHANGE, "--json", "--limit", str(limit))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return json.loads(out.stdout)

    def test_decisions_and_some_task_lines_trimmed(self):
        r = self.repo()
        full = self.full(r)
        limit = self.limit_for(full, 10, 3)
        d = self.digest(r, limit)
        self.assertEqual(d["trimmed"], [{"section": "decisions", "lost": 10},
                                        {"section": "tasks", "lost": 3}])
        self.assertEqual(d["decisions"], [])
        self.assertEqual(d["tasks"], full["tasks"][:7])
        self.assertLessEqual(size(d), limit)

    def test_the_trim_is_in_gates_plan_tier_json(self):
        r = self.repo()
        limit = self.limit_for(self.full(r), 10, 3)
        (r.root / ".gates.yaml").write_text(
            MANIFEST + f"loop:\n  plan-preflight:\n    classifier-input-limit: {limit}\n")
        out = r.gates("plan", "tier", CHANGE, "--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        block = json.loads(out.stdout)["classifier"]
        self.assertEqual(block["trimmed"], [{"section": "decisions", "lost": 10},
                                            {"section": "tasks", "lost": 3}])
        printed = r.gates("plan", "digest", CHANGE, "--json", "--limit", str(limit)).stdout
        self.assertEqual(block["digest_sha"],
                         hashlib.sha256(printed.rstrip("\n").encode()).hexdigest())

    def test_the_trim_order(self):
        r = self.repo(proposal=WITH_CHANGES)
        full = self.full(r)
        one_decision = self.digest(r, size(full) - 1)
        self.assertEqual(one_decision["trimmed"][0]["section"], "decisions")
        kept = one_decision["decisions"]
        self.assertLess(len(kept), len(full["decisions"]))
        self.assertEqual(kept, full["decisions"][:len(kept)])
        self.assertEqual(one_decision["what_changes"], full["what_changes"])
        self.assertEqual(one_decision["tasks"], full["tasks"])
        one_bullet_left = dict(full, decisions=[], what_changes=full["what_changes"][:1],
                               trimmed=[{"section": "decisions", "lost": 10},
                                        {"section": "what_changes", "lost": 1}])
        d = self.digest(r, size(one_bullet_left))
        self.assertEqual([t["section"] for t in d["trimmed"]], ["decisions", "what_changes"])
        self.assertEqual(d["what_changes"], full["what_changes"][:1])
        self.assertEqual(d["tasks"], full["tasks"])

    def test_a_limit_exactly_at_the_untrimmed_size_trims_nothing(self):
        r = self.repo()
        full = self.full(r)
        d = self.digest(r, size(full))
        self.assertEqual(d, full)


if __name__ == "__main__":
    unittest.main()
