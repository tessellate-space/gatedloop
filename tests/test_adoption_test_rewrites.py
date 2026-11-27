"""The shipped `test-rewrites` adoption item, end to end through `gates adoption
status` (openspec change `test-rewrites`, design D7).

From 0.11.1 a project that declares `loop.task-oracle` is asked whether its
planner should declare the existing tests a task rewrites. "Yes" prints the
amended `rules.tasks` line (or the rules-doc rule where `gates conventions sync`
generates the block); "Not yet" is an answer. The shim edits no adopter file.
A project that never tags is not asked. The same amended line is the one this
repo's rules-doc and the shipped rules-doc template carry.

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

TEMPLATE = REPO / "templates" / "git-hooks" / "pre-commit"
BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
TAGGING = BASE + "loop:\n  task-oracle: optional\n"
ITEM = "test-rewrites"
SINCE = "0.11.1"


def _item():
    items = json.loads((REPO / "adoption" / "catalog.json").read_text())["items"]
    return next(i for i in items if i["id"] == ITEM)


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


def _rule_line(path):
    text = path.read_text()
    section = text[text.index("### task-oracle-tags"):]
    return re.search(r"^Rule: (.*)$", section, re.M).group(1)


class TestTheDetector(unittest.TestCase):
    """Regressions guarded: a tagging project never told its planner may now
    declare rewrites, a project that never tags asked about a clause it cannot
    use, and an older shim offering a clause it reads as malformed."""

    def test_the_item_is_decision_only_and_applies_when_tagging(self):
        item = _item()
        self.assertEqual(item["since"], SINCE)
        self.assertEqual(item["detector"], {"kind": "decision-only"})
        self.assertEqual(item["applies_when"], {"kind": "manifest-key", "key": "loop.task-oracle"})

    def test_listed_for_a_tagging_project(self):
        with installed(SINCE, TAGGING) as (plugin, project):
            self.assertIn(ITEM, _listed(plugin, project))

    def test_not_listed_for_a_project_that_never_tags(self):
        with installed(SINCE, BASE) as (plugin, project):
            self.assertNotIn(ITEM, _listed(plugin, project))

    def test_not_listed_before_its_version(self):
        with installed("0.11.0", TAGGING) as (plugin, project):
            self.assertNotIn(ITEM, _listed(plugin, project))


class TestTheAnswers(unittest.TestCase):
    """Regressions guarded: a "yes" that gives the adopter nothing to paste, the
    shim editing the adopter's OpenSpec config, and no way to say "not yet"."""

    def test_yes_prints_the_amended_rules_tasks_line(self):
        item = _item()
        self.assertEqual(item["action"]["kind"], "confirm")
        text = item["what"] + "\n" + item["action"]["detail"]
        self.assertIn("rules.tasks", text)
        self.assertIn("openspec/config.yaml", text)
        self.assertIn(_rule_line(REPO / "templates" / "rules-doc.template.md"),
                      item["action"]["detail"])
        self.assertEqual(item["options"][0]["answer"], "adopted")

    def test_the_line_names_the_clause(self):
        line = _rule_line(REPO / "templates" / "rules-doc.template.md")
        self.assertIn("rewrites: <path>", line)
        self.assertIn("existing test", line)

    def test_this_repo_and_the_template_carry_the_same_line(self):
        self.assertEqual(_rule_line(REPO / "docs" / "conventions.md"),
                         _rule_line(REPO / "templates" / "rules-doc.template.md"))

    def test_not_yet_is_an_answer_and_holds(self):
        self.assertIn("declined", [o["answer"] for o in _item()["options"]])
        with installed(SINCE, TAGGING) as (plugin, project):
            r = _gates(plugin, project, "adoption", "record", ITEM, "declined")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn(ITEM, _listed(plugin, project))
            self.assertEqual((project / ".gates.yaml").read_text(), TAGGING)
            self.assertFalse((project / "openspec" / "config.yaml").exists(),
                             "the shim never writes the adopter's OpenSpec config")


if __name__ == "__main__":
    unittest.main()
