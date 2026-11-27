"""`gates plan brief <change> [--lens <id>]` and `rules/plan-lenses.md`
(openspec change `plan-preflight`, design D6; task 7.1).

Without `--lens` the brief lists the lenses the effective tier runs:
`gatedloop.implementability` under light, and both judging lenses under
full. With `--lens` it prints the lens, the plugin path its checks resolve
against, the plan's artifacts and each path the plan names with whether it
exists at `HEAD`; for `gatedloop.blast-radius` it adds the unlimited digest,
the effective dimensions, the signals and the floor as JSON. The lenses
resolve from the plugin, and a missing file or section fails loud.

`scripts/release docs` reporting no gap is pinned once, in
`test_plan_preflight_show.py`.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import (CHANGE, GATES_SHIM, PROPOSAL, REPO,  # noqa: E402
                                PreflightRepo, env)

LENSES_FILE = REPO / "rules" / "plan-lenses.md"
JUDGING = ["gatedloop.implementability", "gatedloop.zero-decision"]
NAMING_TASKS = """\
# Tasks

## 1. Widget

- [ ] 1.1 Add the widget in `src/widget.py`, called from `src/gadget.py` [oracle: unit]
"""


def listed(stdout: str) -> list[str]:
    return [ln.strip()[2:] for ln in stdout.splitlines() if ln.startswith("  - ")]


def labelled(stdout: str, label: str) -> str:
    hits = [ln[len(label):] for ln in stdout.splitlines() if ln.startswith(label)]
    assert len(hits) == 1, stdout
    return hits[0]


class PlanBriefTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def brief(self, r: PreflightRepo, *extra):
        return r.gates("plan", "brief", CHANGE, *extra)

    def test_a_light_plan_runs_the_implementability_lens_only(self):
        r = PreflightRepo(self._tmp.name)
        out = self.brief(r)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(listed(out.stdout), JUDGING[:1])

    def test_a_full_plan_runs_both_judging_lenses(self):
        r = PreflightRepo(self._tmp.name, proposal=PROPOSAL + "\nPlan tier: full\n")
        out = self.brief(r)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(listed(out.stdout), JUDGING)

    def test_a_judging_lens_brief_names_its_rules_artifacts_and_paths_at_head(self):
        r = PreflightRepo(self._tmp.name, tasks=NAMING_TASKS)
        out = self.brief(r, "--lens", "gatedloop.zero-decision")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(labelled(out.stdout, "lens: "), "gatedloop.zero-decision")
        self.assertEqual(Path(labelled(out.stdout, "Resolve against: ")).resolve(),
                         LENSES_FILE.resolve())
        for name in ("proposal.md", "design.md", "tasks.md", "specs/widget/spec.md"):
            self.assertIn(f"  {r.rel_dir}/{name}", out.stdout.splitlines())
        self.assertIn("  src/widget.py — absent at HEAD", out.stdout.splitlines())
        self.assertIn("  src/gadget.py — exists at HEAD", out.stdout.splitlines())
        self.assertNotIn("{", out.stdout)

    def test_the_blast_radius_brief_carries_the_unlimited_digest_signals_and_floor(self):
        r = PreflightRepo(self._tmp.name, tasks=NAMING_TASKS)
        out = self.brief(r, "--lens", "gatedloop.blast-radius")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        doc = json.loads(out.stdout[out.stdout.index("\n{") + 1:])
        digest = json.loads(r.gates("plan", "digest", CHANGE, "--json").stdout)
        tier = json.loads(r.gates("plan", "tier", CHANGE, "--json").stdout)
        self.assertEqual(doc["digest"], digest)
        self.assertEqual((doc["signals"], doc["floor"]), (tier["signals"], tier["floor"]))
        self.assertEqual([d["id"] for d in doc["dimensions"]],
                         [d["id"] for d in json.loads(
                             (REPO / "rules" / "plan-tier-dimensions.json").read_text())["dimensions"]])

    def test_an_unknown_lens_exits_1_naming_the_known_ones(self):
        r = PreflightRepo(self._tmp.name)
        out = self.brief(r, "--lens", "gatedloop.nope")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("gatedloop.nope", out.stderr)
        self.assertIn("gatedloop.blast-radius", out.stderr)


@contextlib.contextmanager
def installed_plugin(lenses_text):
    """The plugin laid out as an install cache holds it, with this
    `rules/plan-lenses.md` (None ships none), and a plan to brief."""
    with tempfile.TemporaryDirectory() as tmp:
        plugin = Path(tmp) / "plugin-cache" / "gatedloop"
        (plugin / "bin").mkdir(parents=True)
        shutil.copy(GATES_SHIM, plugin / "bin" / "gates")
        shutil.copytree(REPO / "rules", plugin / "rules")
        (plugin / "rules" / "plan-lenses.md").unlink()
        if lenses_text is not None:
            (plugin / "rules" / "plan-lenses.md").write_text(lenses_text)
        r = PreflightRepo(Path(tmp) / "project")
        yield plugin, r


def run_brief(plugin, r, *extra):
    return subprocess.run([sys.executable, str(plugin / "bin" / "gates"), "plan", "brief",
                           CHANGE, *extra], cwd=r.root, capture_output=True, text=True,
                          env=env(), timeout=120)


class PlanLensesFailLoudTest(unittest.TestCase):
    """Regression guarded: a plugin that lost its lenses file or a lens's
    section still naming the lens, so plan review judges through checks it
    cannot read (fail-loud-gates)."""

    def test_a_missing_lenses_file_exits_non_zero_naming_it(self):
        with installed_plugin(None) as (plugin, r):
            out = run_brief(plugin, r)
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertIn("plan-lenses.md", out.stderr)

    def test_a_missing_section_exits_non_zero_naming_the_lens(self):
        text = LENSES_FILE.read_text().replace("### gatedloop.zero-decision", "### gatedloop.other")
        with installed_plugin(text) as (plugin, r):
            out = run_brief(plugin, r, "--lens", "gatedloop.implementability")
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertIn("gatedloop.zero-decision", out.stderr)


if __name__ == "__main__":
    unittest.main()
