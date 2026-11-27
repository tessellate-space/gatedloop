"""The `ci-at` and `ci-scope` adoption items, end to end through `gates
adoption status` (openspec change `ci-at`, design D9; the upgrade-adoption
delta).

Both keys are opt-in, so an adopter who is never told about them never
adopts them. The regressions: either item missing on 0.12.0, listed before
it or once its key is set, `ci-scope` offered to a project with no surface
scoping `ci` (or missed for one that does, because the `surface-key`
predicate read only flat keys), an answer that cannot be recorded, and a
flat `live-check` predicate breaking.

Stdlib only, per `zero-dep-shim`. A copy of the shim runs from a scratch
plugin directory beside the shipped catalogue, reading exactly what an
adopter's install reads. Every project is a throwaway git repo.

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _usage_fixture import GATES_SHIM, REPO, env  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("gates_shim_adoption_ci_at", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

TEMPLATE = REPO / "templates" / "git-hooks" / "pre-commit"
BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
SCOPED_CI = BASE + 'surfaces:\n  - name: api\n    match: "api/**"\n    gates:\n      ci: "true"\n'
SCOPED_UNIT_ONLY = BASE + 'surfaces:\n  - name: api\n    match: "api/**"\n    gates:\n      unit: "true"\n'


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


def _item(item_id):
    items = json.loads((REPO / "adoption" / "catalog.json").read_text())["items"]
    return next(i for i in items if i["id"] == item_id)


class TestCiAtItem(unittest.TestCase):
    def test_listed_on_0_12_0_while_the_key_is_absent(self):
        with installed("0.12.0", BASE) as (plugin, project):
            self.assertIn("ci-at", _listed(plugin, project))

    def test_not_listed_on_0_11_1(self):
        with installed("0.11.1", BASE) as (plugin, project):
            self.assertNotIn("ci-at", _listed(plugin, project))

    def test_not_listed_once_declared(self):
        for value in ("task", "ready"):
            with self.subTest(value=value), \
                    installed("0.12.0", BASE + f"loop:\n  ci-at: {value}\n") as (plugin, project):
                self.assertNotIn("ci-at", _listed(plugin, project))

    def test_the_item_offers_both_values_and_recommends_leaving_it_unset(self):
        item = _item("ci-at")
        self.assertEqual(item["since"], "0.12.0")
        self.assertIsNone(item["applies_when"])
        self.assertEqual(item["detector"], {"kind": "manifest-key", "key": "loop.ci-at"})
        self.assertEqual(item["action"], {"kind": "manifest-key", "key": "loop.ci-at"})
        adopted = sorted(o.get("value") for o in item["options"] if o["answer"] == "adopted")
        self.assertEqual(adopted, ["ready", "task"])
        self.assertEqual(item["options"][0]["answer"], "declined")
        self.assertIn("Recommended", item["options"][0]["label"])
        text = item["what"] + " ".join(o["label"] for o in item["options"])
        self.assertIn("unit", text)
        self.assertIn("READY", text)

    def test_each_answer_is_recordable(self):
        for answer in ("adopted", "declined", "later"):
            with self.subTest(answer=answer), installed("0.12.0", BASE) as (plugin, project):
                r = _gates(plugin, project, "adoption", "record", "ci-at", answer)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertNotIn("ci-at", _listed(plugin, project))


class TestCiScopeItem(unittest.TestCase):
    def test_listed_when_a_surface_declares_a_ci_override(self):
        with installed("0.12.0", SCOPED_CI) as (plugin, project):
            self.assertIn("ci-scope", _listed(plugin, project))

    def test_not_listed_when_no_surface_scopes_ci(self):
        for manifest in (BASE, SCOPED_UNIT_ONLY):
            with self.subTest(manifest=manifest), installed("0.12.0", manifest) as (plugin, project):
                self.assertNotIn("ci-scope", _listed(plugin, project))

    def test_not_listed_on_0_11_1_or_once_declared(self):
        with installed("0.11.1", SCOPED_CI) as (plugin, project):
            self.assertNotIn("ci-scope", _listed(plugin, project))
        with installed("0.12.0", SCOPED_CI + "loop:\n  ci-scope: union\n") as (plugin, project):
            self.assertNotIn("ci-scope", _listed(plugin, project))

    def test_each_answer_is_recordable(self):
        for answer in ("adopted", "declined", "later"):
            with self.subTest(answer=answer), installed("0.12.0", SCOPED_CI) as (plugin, project):
                r = _gates(plugin, project, "adoption", "record", "ci-scope", answer)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertNotIn("ci-scope", _listed(plugin, project))

    def test_the_item_shape(self):
        item = _item("ci-scope")
        self.assertEqual(item["since"], "0.12.0")
        self.assertEqual(item["applies_when"], {"kind": "surface-key", "key": "gates.ci"})
        self.assertEqual(item["detector"], {"kind": "manifest-key", "key": "loop.ci-scope"})


class TestSurfaceKeyPredicate(unittest.TestCase):
    def facts(self, surfaces):
        return {"manifest": {"surfaces": surfaces}}

    def test_a_dotted_key_reads_a_path_into_each_surface(self):
        pred = {"kind": "surface-key", "key": "gates.ci"}
        self.assertTrue(gates.adoption_applies(pred, self.facts([{"gates": {"ci": "x"}}])))
        self.assertFalse(gates.adoption_applies(pred, self.facts([{"gates": {"unit": "x"}}])))
        self.assertFalse(gates.adoption_applies(pred, self.facts([{"gates": "x"}])))
        self.assertFalse(gates.adoption_applies(pred, self.facts([{"name": "a"}])))

    def test_a_flat_key_behaves_as_before(self):
        pred = {"kind": "surface-key", "key": "live-check"}
        self.assertTrue(gates.adoption_applies(pred, self.facts([{"live-check": "probe"}])))
        self.assertFalse(gates.adoption_applies(pred, self.facts([{"name": "a"}])))
        self.assertFalse(gates.adoption_applies(pred, self.facts([{"live-check": None}])))
        self.assertFalse(gates.adoption_applies(pred, {"manifest": {}}))


if __name__ == "__main__":
    unittest.main()
