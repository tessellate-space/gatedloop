"""The shipped `retry-budget` adoption item, end to end through `gates adoption
status` (openspec change `retry-budget`, design D7).

Stdlib only, per `zero-dep-shim`. What is under test is the shipped
catalogue's entry meeting the real fact gathering, so a copy of the shim runs
from a scratch plugin directory beside the shipped catalogue, reading exactly
what an adopter's install reads. Every project is a throwaway git repo.

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
TEMPLATE = REPO / "templates" / "git-hooks" / "pre-commit"

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


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
                           env=_env())
        (project / ".gates.yaml").write_text(manifest)
        yield plugin, project


def _gates(plugin, project, *args):
    return subprocess.run([sys.executable, str(plugin / "bin" / "gates"), *args], cwd=project,
                          capture_output=True, text=True, env=_env(), timeout=60)


def _listed(plugin, project):
    r = _gates(plugin, project, "adoption", "status", "--json")
    if r.returncode != 0:
        raise AssertionError(f"status exited {r.returncode}: {r.stderr}")
    return [i["id"] for i in json.loads(r.stdout)["undecided"]]


class TestRetryBudgetItem(unittest.TestCase):
    def test_the_item_is_shipped_since_0_6_0_with_the_defaults_recommended(self):
        items = json.loads((REPO / "adoption" / "catalog.json").read_text())["items"]
        item = next(i for i in items if i["id"] == "retry-budget")
        self.assertEqual(item["since"], "0.6.0")
        self.assertEqual(item["detector"], {"kind": "manifest-key", "key": "loop.attempts"})
        recommended = [o for o in item["options"] if "(Recommended)" in o["label"]]
        self.assertEqual(len(recommended), 1)
        self.assertIs(item["options"][0], recommended[0])

    def test_listed_at_0_6_0_when_no_budget_is_declared(self):
        with installed("0.6.0", BASE) as (plugin, project):
            self.assertIn("retry-budget", _listed(plugin, project))

    def test_not_listed_once_the_budget_is_declared(self):
        with installed("0.6.0", BASE + "loop:\n  attempts: 2\n") as (plugin, project):
            self.assertNotIn("retry-budget", _listed(plugin, project))

    def test_not_listed_before_0_6_0(self):
        with installed("0.5.0", BASE) as (plugin, project):
            self.assertNotIn("retry-budget", _listed(plugin, project))

    def test_declining_holds(self):
        with installed("0.6.0", BASE) as (plugin, project):
            r = _gates(plugin, project, "adoption", "record", "retry-budget", "declined")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("retry-budget", _listed(plugin, project))


if __name__ == "__main__":
    unittest.main()
