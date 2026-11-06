"""The surface key `blast-radius` and the plan's hot surfaces (openspec
change `plan-preflight`, design D3 signal 6, D12; task 4.2).

`blast-radius: high | normal` (default `normal`) is the adopter's word for
"this surface matters"; `gates validate` refuses any other value, naming the
surface, and `gates surfaces` shows it on a hot surface that declares it.
`_plan_hot_surfaces` is the one selection the tier reads: the surfaces hot
for the paths the plan's proposal, design and task lines name, never the
change's own directory.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, GATES_SHIM, MANIFEST, PreflightRepo  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("gates_shim_pf_blast", str(GATES_SHIM))
gates = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(gates)


def manifest(radius: str | None) -> str:
    line = f"    blast-radius: {radius}\n" if radius is not None else ""
    return (MANIFEST + "surfaces:\n"
            "  - name: core\n    match: \"src/**\"\n" + line +
            "  - name: docs\n    match: \"docs/**\"\n")


class BlastRadiusKeyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def repo(self, radius, **kw) -> PreflightRepo:
        return PreflightRepo(self._tmp.name, manifest=manifest(radius), **kw)

    def test_each_value_validates_and_shows_on_a_hot_surface(self):
        for radius in ("high", "normal"):
            with self.subTest(radius), tempfile.TemporaryDirectory() as tmp:
                r = PreflightRepo(tmp, manifest=manifest(radius))
                self.assertEqual(r.gates("validate").returncode, 0)
                out = r.gates("surfaces", "--changed", "src/gadget.py").stdout
                self.assertIn(f"blast-radius={radius}", out)

    def test_a_misspelt_value_is_refused_naming_the_surface(self):
        r = self.repo("hihg")
        out = r.gates("validate")
        self.assertEqual(out.returncode, 1)
        self.assertIn("surface 'core'", out.stdout + out.stderr)
        self.assertIn("blast-radius", out.stdout + out.stderr)

    def test_the_default_is_normal_and_not_shown(self):
        r = self.repo(None)
        self.assertEqual(r.gates("validate").returncode, 0)
        out = r.gates("surfaces", "--changed", "src/gadget.py").stdout
        self.assertIn("core:", out)
        self.assertNotIn("blast-radius", out)
        self.assertEqual(gates._blast_radius({"name": "core"}), "normal")

    def test_plan_hot_surfaces_on_two_surfaces(self):
        design = ("# Design\n\n### D1. Touch `src/widget.py`\n\nAnd "
                  f"`openspec/changes/{CHANGE}/notes.md`.\n")
        tasks = "- [ ] 1.1 Document in `docs/widget.md` [oracle: none]\n"
        r = self.repo("high", design=design, tasks=tasks)
        m = gates._parse_yaml_text((r.root / ".gates.yaml").read_text())
        self.assertEqual(gates._plan_named_paths(r.root, CHANGE), ["src/widget.py", "docs/widget.md"])
        hot = gates._plan_hot_surfaces(m, r.root, CHANGE)
        self.assertEqual(sorted(s["name"] for s in hot), ["core", "docs"])

    def test_plan_hot_surfaces_on_none(self):
        r = self.repo("high", design="# Design\n\nNothing named.\n",
                      proposal="# Proposal\n\nNo paths.\n",
                      tasks="- [ ] 1.1 Think about `notes/idea.txt` [oracle: none]\n")
        m = gates._parse_yaml_text((r.root / ".gates.yaml").read_text())
        self.assertEqual(gates._plan_hot_surfaces(m, r.root, CHANGE), [])


if __name__ == "__main__":
    unittest.main()
