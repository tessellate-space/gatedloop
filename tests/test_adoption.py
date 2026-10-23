"""The adoption catalogue, its evaluation, and `gates adoption status|record`
(openspec change `adoption-prompts`, design D1-D3).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import contextlib
import copy
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_adoption", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


# One catalogue shared by every test in this file: an item per detector kind,
# shaped like the shipped catalogue (design D1/D8).
CATALOG = {"items": [
    {
        "id": "approval.acceptance",
        "since": "0.5.0",
        "what": "Whether a human accepts the behaviour before merge.",
        "question": "Should a human accept each change's behaviour before it merges?",
        "options": [
            {"answer": "adopted", "label": "Yes, I accept my own (Recommended)", "value": "self"},
            {"answer": "adopted", "label": "Yes, a reviewer accepts on the PR", "value": "review"},
            {"answer": "declined", "label": "No acceptance step"},
        ],
        "detector": {"kind": "manifest-key", "key": "approval.acceptance"},
        "applies_when": None,
        "action": {"kind": "manifest-key", "key": "approval.acceptance"},
    },
    {
        "id": "test-conventions",
        "since": "0.5.0",
        "what": "Your project's test rules.",
        "question": "Capture this project's test conventions now?",
        "options": [
            {"answer": "adopted", "label": "Capture them now (Recommended)"},
            {"answer": "declined", "label": "No"},
        ],
        "detector": {"kind": "rules-target", "target": "tests"},
        "applies_when": None,
        "action": {"kind": "onboarding-step", "step": "gates-init step 6, test-conventions pass"},
    },
    {
        "id": "runner-strictness",
        "since": "0.5.0",
        "what": "Blocking gates' runners fail on undefined steps and never retry to green.",
        "question": "Have you checked your runners?",
        "options": [
            {"answer": "adopted", "label": "Confirmed (Recommended)"},
            {"answer": "declined", "label": "Not applicable"},
        ],
        "detector": {"kind": "decision-only"},
        "applies_when": {"kind": "any", "of": [
            {"kind": "manifest-key", "key": "gates.verify"},
            {"kind": "manifest-key", "key": "gates.integration"},
            {"kind": "surface-key", "key": "live-check"},
        ]},
        "action": {"kind": "confirm", "detail": "Check the runner."},
    },
    {
        "id": "schema-flow",
        "since": "0.5.0",
        "what": "Local schemas can declare gatedloop.flow.",
        "question": "Review your schemas now?",
        "options": [
            {"answer": "adopted", "label": "Review now (Recommended)"},
            {"answer": "declined", "label": "No"},
        ],
        "detector": {"kind": "schema-key", "key": "gatedloop"},
        "applies_when": {"kind": "path-exists", "glob": "openspec/schemas/*/schema.yaml"},
        "action": {"kind": "confirm", "detail": "Explain gatedloop.flow."},
    },
]}


def catalog(mutate=None):
    data = copy.deepcopy(CATALOG)
    if mutate:
        mutate(data["items"])
    return data


class TestCatalogLoader(unittest.TestCase):
    """Design D1: the loader is the one place the catalogue's shape is
    enforced; anything it lets through is evaluated as if it were valid."""

    def assertRefused(self, data, *needles):
        with self.assertRaises(gates.AdoptionError) as ctx:
            gates.load_adoption_catalog(data)
        for needle in needles:
            self.assertIn(needle, str(ctx.exception))

    def test_valid_catalog_loads_every_item(self):
        items = gates.load_adoption_catalog(catalog())
        self.assertEqual([i["id"] for i in items],
                         ["approval.acceptance", "test-conventions", "runner-strictness", "schema-flow"])

    def test_unknown_kind_is_refused_naming_item_and_kind(self):
        # Each kind field is its own closed set; an unknown value in any of
        # them must stop evaluation rather than be read as "not acted".
        for field, index in (("detector", 0), ("applies_when", 2), ("action", 1)):
            with self.subTest(field=field):
                def mutate(items, field=field, index=index):
                    items[index][field] = {"kind": "telepathy"}
                self.assertRefused(catalog(mutate), CATALOG["items"][index]["id"], "telepathy")

    def test_unknown_kind_nested_in_any_is_refused(self):
        def mutate(items):
            items[2]["applies_when"]["of"].append({"kind": "telepathy"})
        self.assertRefused(catalog(mutate), "runner-strictness", "telepathy")

    def test_missing_required_field_is_refused_naming_item(self):
        def mutate(items):
            del items[1]["question"]
        self.assertRefused(catalog(mutate), "test-conventions", "question")

    def test_recommended_option_must_come_first(self):
        def mutate(items):
            items[1]["options"].reverse()
        self.assertRefused(catalog(mutate), "test-conventions", "Recommended")

    def test_later_is_never_a_listed_option(self):
        # The walk always offers "Decide later" itself (design D1).
        def mutate(items):
            items[1]["options"].append({"answer": "later", "label": "Later"})
        self.assertRefused(catalog(mutate), "test-conventions", "later")

    def test_duplicate_id_is_refused(self):
        def mutate(items):
            items[2]["id"] = items[1]["id"]
        self.assertRefused(catalog(mutate), "test-conventions", "duplicate")

    def test_since_must_be_a_version(self):
        def mutate(items):
            items[0]["since"] = "next"
        self.assertRefused(catalog(mutate), "approval.acceptance", "since")

    def test_manifest_key_action_needs_a_value_per_adopted_option(self):
        def mutate(items):
            del items[0]["options"][1]["value"]
        self.assertRefused(catalog(mutate), "approval.acceptance", "value")


RULES_DOC_WITH_TESTS = (
    "### fixtures-first\nApplies to: tests\nRule: Build on tests/fixtures.\n\n"
    "### small-functions\nApplies to: code\nRule: Keep functions small.\n"
)
RULES_DOC_CODE_ONLY = "### small-functions\nApplies to: code\nRule: Keep functions small.\n"


def facts(manifest=None, rules_doc=None, schemas=(), existing_globs=()):
    return {"manifest": manifest or {}, "rules_doc": rules_doc,
            "schemas": list(schemas), "existing_globs": set(existing_globs)}


class TestShippedCatalog(unittest.TestCase):
    """The catalogue this plugin ships passes the same loader every adopter's
    `gates adoption status` runs; a malformed one would make that command
    fail for everyone on the next release."""

    def test_shipped_catalog_loads(self):
        data = json.loads((REPO / "adoption" / "catalog.json").read_text())
        self.assertTrue(gates.load_adoption_catalog(data))


class TestDetectors(unittest.TestCase):
    """Design D1: each detector kind answers "has the project already acted?"
    from already-loaded inputs. A wrong answer either nags a team about a
    setting they made or hides one they never saw."""

    CASES = (
        # (detector, facts, acted)
        ({"kind": "manifest-key", "key": "approval.acceptance"},
         facts({"approval": {"plan": "self", "acceptance": "review"}}), True),
        ({"kind": "manifest-key", "key": "approval.acceptance"},
         facts({"approval": {"plan": "self"}}), False),
        ({"kind": "manifest-key", "key": "loop.test-author"},
         facts({"loop": "inline"}), False),
        ({"kind": "rules-target", "target": "tests"}, facts(rules_doc=RULES_DOC_WITH_TESTS), True),
        ({"kind": "rules-target", "target": "tests"}, facts(rules_doc=RULES_DOC_CODE_ONLY), False),
        ({"kind": "rules-target", "target": "tests"}, facts(rules_doc=None), False),
        ({"kind": "schema-key", "key": "gatedloop"},
         facts(schemas=["name: a\n", "name: b\ngatedloop:\n  flow: regression-first\n"]), True),
        ({"kind": "schema-key", "key": "gatedloop"},
         facts(schemas=["name: a\napply:\n  gatedloop: nested\n"]), False),
        ({"kind": "decision-only"},
         facts({"approval": {"acceptance": "self"}}, RULES_DOC_WITH_TESTS, ["gatedloop:\n"]), False),
    )

    def test_each_kind_reports_acted_and_not_acted(self):
        for detector, f, acted in self.CASES:
            with self.subTest(detector=detector, acted=acted):
                self.assertIs(gates.adoption_detector_acted(detector, f), acted)

    def test_unknown_detector_kind_raises(self):
        with self.assertRaises(gates.AdoptionError) as ctx:
            gates.adoption_detector_acted({"kind": "telepathy"}, facts())
        self.assertIn("telepathy", str(ctx.exception))


class TestPredicates(unittest.TestCase):
    """Design D1: `applies_when` keeps an item away from projects it cannot
    concern (runner strictness without a blocking runner gate; schema flow
    without a local schema)."""

    ANY_OF = {"kind": "manifest-key", "any_of": ["gates.verify", "gates.live-check"]}
    GLOB = "openspec/schemas/*/schema.yaml"
    SURFACE = {"kind": "surface-key", "key": "live-check"}
    ANY = {"kind": "any", "of": [{"kind": "manifest-key", "key": "gates.verify"}, SURFACE]}

    def test_each_kind_holds_and_does_not_hold(self):
        cases = (
            (None, facts(), True),
            (self.ANY_OF, facts({"gates": {"ci": "true", "live-check": "probe"}}), True),
            (self.ANY_OF, facts({"gates": {"ci": "true"}}), False),
            ({"kind": "path-exists", "glob": self.GLOB}, facts(existing_globs=[self.GLOB]), True),
            ({"kind": "path-exists", "glob": self.GLOB}, facts(), False),
            (self.SURFACE, facts({"surfaces": [{"name": "a"}, {"name": "b", "live-check": "probe"}]}),
             True),
            (self.SURFACE, facts({"surfaces": [{"name": "a", "rules": ["r"]}]}), False),
            (self.ANY, facts({"surfaces": [{"name": "b", "live-check": "probe"}]}), True),
            (self.ANY, facts({"gates": {"ci": "true"}, "surfaces": [{"name": "a"}]}), False),
        )
        for pred, f, holds in cases:
            with self.subTest(pred=pred, holds=holds):
                self.assertIs(gates.adoption_applies(pred, f), holds)

    def test_unknown_predicate_kind_raises(self):
        with self.assertRaises(gates.AdoptionError) as ctx:
            gates.adoption_applies({"kind": "telepathy"}, facts())
        self.assertIn("telepathy", str(ctx.exception))


def decided(decision, version="0.5.0"):
    return {"decision": decision, "by": "T <t@example.com>", "at": "2026-10-01T00:00:00Z",
            "version": version}


class TestUndecided(unittest.TestCase):
    """Design D3: an item is listed exactly when it applies, the project has
    not acted, and no decision still applies."""

    ITEMS = CATALOG["items"]

    def ids(self, f, decisions=None, version="0.5.0", items=None):
        return [i["id"] for i in gates.adoption_undecided(
            items or self.ITEMS, f, decisions or {}, version)]

    def test_fresh_project_lists_only_items_that_apply(self):
        self.assertEqual(self.ids(facts()), ["approval.acceptance", "test-conventions"])
        everything = facts({"gates": {"ci": "true", "verify": "v"}},
                           existing_globs=["openspec/schemas/*/schema.yaml"])
        self.assertEqual(self.ids(everything), ["approval.acceptance", "test-conventions",
                                                "runner-strictness", "schema-flow"])

    def test_detector_beats_record(self):
        # The adopter set the key by hand: that is the decision, even over a
        # stale `later` from an older version.
        f = facts({"approval": {"acceptance": "self"}})
        self.assertNotIn("approval.acceptance",
                         self.ids(f, {"approval.acceptance": decided("later", "0.4.0")}))

    def test_adopted_and_declined_hide_at_any_version(self):
        for decision in ("adopted", "declined"):
            with self.subTest(decision=decision):
                record = {"test-conventions": decided(decision, "0.5.0")}
                self.assertNotIn("test-conventions", self.ids(facts(), record, version="0.9.0"))

    def test_later_hides_only_at_the_recorded_version(self):
        record = {"test-conventions": decided("later", "0.5.0")}
        self.assertNotIn("test-conventions", self.ids(facts(), record, version="0.5.0"))
        self.assertIn("test-conventions", self.ids(facts(), record, version="0.6.0"))

    def test_unreleased_item_is_not_listed_until_its_version_is_installed(self):
        # Design D1 "Unreleased items": on main between releases an item
        # carries the next version; nothing is asked about it until then.
        items = copy.deepcopy(self.ITEMS[:2])
        items[1]["since"] = "0.6.0"
        self.assertEqual(self.ids(facts(), version="0.5.0", items=items), ["approval.acceptance"])
        self.assertEqual(self.ids(facts(), version="0.6.0", items=items),
                         ["approval.acceptance", "test-conventions"])

    def test_listed_in_since_order_then_catalogue_order(self):
        items = copy.deepcopy(self.ITEMS[:2])
        items[1]["since"] = "0.4.0"
        self.assertEqual(self.ids(facts(), items=items), ["test-conventions", "approval.acceptance"])


# ---------- the CLI, end to end, against a fixture plugin --------------------
#
# The shim resolves the catalogue and plugin.json from its own location, so a
# copy of it in a scratch plugin directory reads that directory's fixtures:
# the "installed version" is whatever the fixture plugin.json says.

@contextlib.contextmanager
def fixture_install(version="0.5.0", manifest=None):
    with tempfile.TemporaryDirectory() as tmp:
        plugin, project = Path(tmp) / "plugin", Path(tmp) / "project"
        (plugin / "bin").mkdir(parents=True)
        shutil.copy(GATES_SHIM, plugin / "bin" / "gates")
        (plugin / "adoption").mkdir()
        (plugin / "adoption" / "catalog.json").write_text(json.dumps(CATALOG))
        (plugin / ".claude-plugin").mkdir()
        set_version(plugin, version)
        project.mkdir()
        for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Test"),
                     ("config", "user.email", "test@example.com")):
            subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)
        if manifest is not None:
            (project / ".gates.yaml").write_text(manifest)
        yield plugin, project


def set_version(plugin, version):
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))


def run_gates(plugin, project, *args):
    return subprocess.run([sys.executable, str(plugin / "bin" / "gates"), *args], cwd=project,
                          capture_output=True, text=True, timeout=60)


def record_file(project):
    return project / ".gatedloop" / "adoption.json"


class TestAdoptionRecord(unittest.TestCase):
    """Design D2: `gates adoption record` is the only writer of the record."""

    def test_records_decider_time_and_version_keeping_other_decisions(self):
        with fixture_install("0.5.0") as (plugin, project):
            first = run_gates(plugin, project, "adoption", "record", "test-conventions", "declined")
            self.assertEqual(first.returncode, 0, first.stderr)
            second = run_gates(plugin, project, "adoption", "record", "approval.acceptance", "later")
            self.assertEqual(second.returncode, 0, second.stderr)
            decisions = json.loads(record_file(project).read_text())["decisions"]
        self.assertEqual(decisions["test-conventions"]["decision"], "declined")
        later = decisions["approval.acceptance"]
        self.assertEqual((later["decision"], later["by"], later["version"]),
                         ("later", "Test <test@example.com>", "0.5.0"))
        self.assertRegex(later["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_unknown_id_or_decision_is_refused_without_writing(self):
        for args, named in ((("no-such-item", "adopted"), "no-such-item"),
                            (("test-conventions", "maybe"), "maybe")):
            with self.subTest(args=args), fixture_install() as (plugin, project):
                result = run_gates(plugin, project, "adoption", "record", *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(named, result.stderr)
                self.assertFalse(record_file(project).exists())


def status(plugin, project):
    result = run_gates(plugin, project, "adoption", "status", "--json")
    if result.returncode != 0:
        raise AssertionError(f"status exited {result.returncode}: {result.stderr}")
    return json.loads(result.stdout)


class TestAdoptionStatus(unittest.TestCase):
    """Design D3: status reports in code what is still undecided, and exits
    non-zero only when it cannot decide."""

    def test_reports_installed_version_and_undecided_items(self):
        with fixture_install("0.5.0") as (plugin, project):
            doc = status(plugin, project)
        self.assertEqual(doc["version"], "0.5.0")
        self.assertEqual([(i["id"], i["since"]) for i in doc["undecided"]],
                         [("approval.acceptance", "0.5.0"), ("test-conventions", "0.5.0")])

    def test_reads_project_facts_from_manifest_rules_doc_and_schemas(self):
        manifest = ('gatesVersion: 1\ngates:\n  ci: "true"\n  verify: "v"\n'
                    'approval:\n  acceptance: self\nconventions:\n  rules-doc: docs/rules.md\n')
        with fixture_install(manifest=manifest) as (plugin, project):
            (project / "docs").mkdir()
            (project / "docs" / "rules.md").write_text(RULES_DOC_WITH_TESTS)
            (project / "openspec" / "schemas" / "mine").mkdir(parents=True)
            (project / "openspec" / "schemas" / "mine" / "schema.yaml").write_text("name: mine\n")
            ids = [i["id"] for i in status(plugin, project)["undecided"]]
        self.assertEqual(ids, ["runner-strictness", "schema-flow"])

    def test_surface_live_check_alone_makes_runner_strictness_apply(self):
        # Design D8: live-checks are declared per surface, not under `gates`,
        # so a project whose only blocking runner is one must still be asked.
        manifest = ('gatesVersion: 1\ngates:\n  ci: "true"\nsurfaces:\n'
                    '  - name: app\n    match: "**"\n    live-check: "probe"\n')
        with fixture_install(manifest=manifest) as (plugin, project):
            ids = [i["id"] for i in status(plugin, project)["undecided"]]
        self.assertIn("runner-strictness", ids)

    def test_cannot_decide_exits_non_zero(self):
        def bad_catalog(plugin, project):
            broken = catalog(lambda items: items[3].update(detector={"kind": "telepathy"}))
            (plugin / "adoption" / "catalog.json").write_text(json.dumps(broken))

        def bad_record(plugin, project):
            record_file(project).parent.mkdir()
            record_file(project).write_text("{not json")

        for breaker, named in ((bad_catalog, "schema-flow"), (bad_record, "adoption.json")):
            with self.subTest(named=named), fixture_install() as (plugin, project):
                breaker(plugin, project)
                result = run_gates(plugin, project, "adoption", "status", "--json")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(named, result.stderr)
                self.assertEqual(result.stdout, "")


class TestAdoptionLifecycle(unittest.TestCase):
    """Task 2.3: the upgrade-adoption scenarios through the real CLI, across
    a plugin upgrade (the fixture plugin.json's version). A fresh project
    listing every applicable item is TestAdoptionStatus's first test."""

    def listed(self, plugin, project):
        return [i["id"] for i in status(plugin, project)["undecided"]]

    def record(self, plugin, project, item, decision):
        result = run_gates(plugin, project, "adoption", "record", item, decision)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_setting_the_manifest_key_hides_the_item(self):
        manifest = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  acceptance: review\n'
        with fixture_install(manifest=manifest) as (plugin, project):
            self.assertNotIn("approval.acceptance", self.listed(plugin, project))

    def test_declined_stays_hidden_across_an_upgrade(self):
        with fixture_install("0.5.0") as (plugin, project):
            self.record(plugin, project, "test-conventions", "declined")
            self.assertNotIn("test-conventions", self.listed(plugin, project))
            set_version(plugin, "0.6.0")
            self.assertNotIn("test-conventions", self.listed(plugin, project))

    def test_later_comes_back_when_the_plugin_version_changes(self):
        with fixture_install("0.5.0") as (plugin, project):
            self.record(plugin, project, "test-conventions", "later")
            self.assertNotIn("test-conventions", self.listed(plugin, project))
            set_version(plugin, "0.6.0")
            self.assertIn("test-conventions", self.listed(plugin, project))


if __name__ == "__main__":
    unittest.main()
