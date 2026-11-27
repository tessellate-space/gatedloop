"""The `plan-preflight` adoption item, end to end through `gates adoption
status` (openspec change `plan-preflight`, design D12; the upgrade-adoption
delta; task 8.1).

The model part of the plan loop spends usage, so it is opt-in, and an
adopter who is never asked never adopts it. The regressions: the item
missing on 0.12.0, listed before it or once `loop.plan-preflight` is
declared (in either form), an answer that cannot be recorded, a question
that states the cost as money or hides that an external classifier sends
the plan digest off the machine.

Stdlib only, per `zero-dep-shim`. A copy of the shim runs from a scratch
plugin directory beside the shipped catalogue, reading exactly what an
adopter's install reads. Every project is a throwaway git repo.

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import GATES_SHIM, REPO, env  # noqa: E402

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
ITEM = "plan-preflight"


@contextlib.contextmanager
def installed(version, manifest):
    with tempfile.TemporaryDirectory() as tmp:
        plugin, project = Path(tmp) / "plugin", Path(tmp) / "project"
        (plugin / "bin").mkdir(parents=True)
        shutil.copy(GATES_SHIM, plugin / "bin" / "gates")
        shutil.copytree(REPO / "adoption", plugin / "adoption")
        shutil.copytree(REPO / "rules", plugin / "rules")
        shutil.copytree(REPO / "templates", plugin / "templates")
        (plugin / ".claude-plugin").mkdir()
        (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))
        project.mkdir()
        for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Test"),
                     ("config", "user.email", "test@example.com")):
            subprocess.run(["git", *args], cwd=project, check=True, capture_output=True,
                           env=env())
        (project / ".gates.yaml").write_text(manifest)
        yield plugin, project


def _gates(plugin, project, *args):
    return subprocess.run([sys.executable, str(plugin / "bin" / "gates"), *args], cwd=project,
                          capture_output=True, text=True, env=env(), timeout=60)


def _listed(plugin, project):
    r = _gates(plugin, project, "adoption", "status", "--json")
    if r.returncode != 0:
        raise AssertionError(f"status exited {r.returncode}: {r.stderr}")
    return [i["id"] for i in json.loads(r.stdout)["undecided"]]


def _item():
    items = json.loads((REPO / "adoption" / "catalog.json").read_text())["items"]
    return next(i for i in items if i["id"] == ITEM)


class TestPlanPreflightItem(unittest.TestCase):
    def test_listed_on_0_12_0_while_the_key_is_absent(self):
        with installed("0.12.0", BASE) as (plugin, project):
            self.assertIn(ITEM, _listed(plugin, project))

    def test_not_listed_on_0_11_1(self):
        with installed("0.11.1", BASE) as (plugin, project):
            self.assertNotIn(ITEM, _listed(plugin, project))

    def test_not_listed_once_declared_in_either_form(self):
        for block in ("  plan-preflight: skip\n", "  plan-preflight: run\n",
                      "  plan-preflight:\n    mode: run\n"):
            with self.subTest(block=block), \
                    installed("0.12.0", BASE + "loop:\n" + block) as (plugin, project):
                self.assertNotIn(ITEM, _listed(plugin, project))

    def test_each_answer_is_recordable(self):
        for answer in ("adopted", "declined", "later"):
            with self.subTest(answer=answer), installed("0.12.0", BASE) as (plugin, project):
                r = _gates(plugin, project, "adoption", "record", ITEM, answer)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertNotIn(ITEM, _listed(plugin, project))

    def test_the_options_are_run_skip_and_declining_and_run_names_its_prerequisite(self):
        # The options are what `/gatedloop:upgrade` writes to the manifest; no
        # `gates adoption` call reads them, so they are pinned here.
        options = {(o["answer"], o.get("value")): o["label"] for o in _item()["options"]}
        self.assertEqual(set(options), {("adopted", "run"), ("adopted", "skip"), ("declined", None)})
        self.assertIn("test-author: separate", options[("adopted", "run")])

    def test_the_question_states_each_tiers_runs_as_usage_never_unlabelled_money(self):
        q = _item()["question"]
        self.assertIn("one plan-review run per plan", q)
        self.assertIn("one plan-review run per lens, one test-author run", q)
        # No money figure today; one added later must carry the label.
        for m in re.finditer(r"\$|\bUSD\b|dollar", q):
            self.assertIn("API-equivalent, if you pay per token", q[m.start():m.start() + 120])

    def test_the_question_discloses_what_an_external_classifier_receives(self):
        q = _item()["question"]
        self.assertIn("sends the plan digest (file paths, requirement titles, task lines and "
                      "decision headings) to that classifier's provider", q)
        self.assertIn("your own API key", q)


if __name__ == "__main__":
    unittest.main()
