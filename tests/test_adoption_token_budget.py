"""The shipped `token-budget` adoption item, end to end through `gates adoption
status` (openspec change `token-ledger`, design D8).

The item offers `loop.token-budget` from 0.8.0, and its recommended answer is
deliberately the decline: usage is recorded either way, and a budget is the
adopter's number to choose. Declining records the decision and leaves the
manifest as it was.

Stdlib only, per `zero-dep-shim`. A copy of the shim runs from a scratch
plugin directory beside the shipped catalogue, reading exactly what an
adopter's install reads. Every project is a throwaway git repo.

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import GATES_SHIM, REPO, env  # noqa: E402

TEMPLATE = REPO / "templates" / "git-hooks" / "pre-commit"
BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
ITEM = "token-budget"


@contextlib.contextmanager
def installed(version, manifest):
    with tempfile.TemporaryDirectory() as tmp:
        plugin, project = Path(tmp) / "plugin", Path(tmp) / "project"
        (plugin / "bin").mkdir(parents=True)
        shutil.copy(GATES_SHIM, plugin / "bin" / "gates")
        (plugin / "adoption").mkdir()
        shutil.copy(REPO / "adoption" / "catalog.json", plugin / "adoption" / "catalog.json")
        (plugin / "templates" / "git-hooks").mkdir(parents=True)
        shutil.copy(TEMPLATE, plugin / "templates" / "git-hooks" / "pre-commit")
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


class TestTokenBudgetItem(unittest.TestCase):
    def test_listed_from_0_8_0_while_no_budget_is_declared(self):
        with installed("0.8.0", BASE) as (plugin, project):
            self.assertIn(ITEM, _listed(plugin, project))
        with installed("0.7.0", BASE) as (plugin, project):
            self.assertNotIn(ITEM, _listed(plugin, project))

    def test_not_listed_once_a_budget_is_declared(self):
        with installed("0.8.0", BASE + "loop:\n  token-budget: 5000000\n") as (plugin, project):
            self.assertNotIn(ITEM, _listed(plugin, project))

    def test_the_recommended_answer_records_only_and_leaves_the_manifest(self):
        items = json.loads((REPO / "adoption" / "catalog.json").read_text())["items"]
        item = next(i for i in items if i["id"] == ITEM)
        self.assertEqual(item["options"][0]["answer"], "declined",
                         "record only, no budget, is the recommended answer")
        with installed("0.8.0", BASE) as (plugin, project):
            r = _gates(plugin, project, "adoption", "record", ITEM, "declined")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn(ITEM, _listed(plugin, project))
            self.assertEqual((project / ".gates.yaml").read_text(), BASE)


if __name__ == "__main__":
    unittest.main()
