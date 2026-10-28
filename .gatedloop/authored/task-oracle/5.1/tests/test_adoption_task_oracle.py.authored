"""The shipped `task-oracle` adoption item, end to end through `gates adoption
status` (openspec change `task-oracle`, design D7).

From 0.9.0 the item asks whether the plan should declare each task's oracle.
Its recommended answer prints one line for the adopter's own
`openspec/config.yaml` `rules.tasks` and sets `loop.task-oracle: required`;
"Not yet" is an answer too. The shim writes nothing into the adopter's
OpenSpec config. The detector is `loop.task-oracle` present in the manifest.

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
ITEM = "task-oracle"


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


class TestTheDetector(unittest.TestCase):
    """Regressions guarded: the item never offered to a project that has not
    decided, offered again to one that has declared the key, or offered on a
    version that cannot honour the tag."""

    def test_listed_from_0_9_0_while_the_key_is_absent(self):
        with installed("0.9.0", BASE) as (plugin, project):
            self.assertIn(ITEM, _listed(plugin, project))

    def test_not_listed_before_0_9_0(self):
        with installed("0.8.0", BASE) as (plugin, project):
            self.assertNotIn(ITEM, _listed(plugin, project))

    def test_not_listed_once_the_key_is_declared(self):
        for value in ("required", "optional"):
            with self.subTest(value=value), \
                    installed("0.9.0", BASE + f"loop:\n  task-oracle: {value}\n") as (plugin, project):
                self.assertNotIn(ITEM, _listed(plugin, project))


class TestTheAnswers(unittest.TestCase):
    """Regressions guarded: an adopter told to tag plans without the line that
    makes `/opsx:propose` write the tags, a recommended answer that sets
    nothing, and no way to say "not yet"."""

    def test_the_item_is_shipped_since_0_9_0_on_the_key(self):
        item = _item()
        self.assertEqual(item["since"], "0.9.0")
        self.assertEqual(item["detector"], {"kind": "manifest-key", "key": "loop.task-oracle"})
        self.assertEqual(item["action"], {"kind": "manifest-key", "key": "loop.task-oracle"})

    def test_the_recommended_answer_requires_the_tag(self):
        first = _item()["options"][0]
        self.assertIn("(Recommended)", first["label"])
        self.assertEqual(first["answer"], "adopted")
        self.assertEqual(first["value"], "required")

    def test_the_rules_tasks_line_is_printed_for_the_adopter(self):
        item = _item()
        text = item["what"] + "\n" + "\n".join(o["label"] for o in item["options"])
        self.assertIn("rules.tasks", text)
        self.assertIn("openspec/config.yaml", text)
        for form in ("[oracle: <gate>]", "[oracle: <gate> characterization]", "[oracle: none]"):
            self.assertIn(form, text)

    def test_not_yet_is_an_answer_and_holds(self):
        self.assertIn("declined", [o["answer"] for o in _item()["options"]])
        with installed("0.9.0", BASE) as (plugin, project):
            r = _gates(plugin, project, "adoption", "record", ITEM, "declined")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn(ITEM, _listed(plugin, project))
            self.assertEqual((project / ".gates.yaml").read_text(), BASE)
            self.assertFalse((project / "openspec" / "config.yaml").exists(),
                             "the shim never writes the adopter's OpenSpec config")


if __name__ == "__main__":
    unittest.main()
