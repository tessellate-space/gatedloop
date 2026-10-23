"""Recurring adoption items (openspec change `adoption-followups`, design D4;
the upgrade-adoption delta's "Undecided items are determined in code").

Stdlib only, per `zero-dep-shim`. Pure: the loader and `adoption_undecided`
are exercised on in-memory catalogues and facts.

Run with:  python3 -m unittest discover -s tests
"""

import copy
import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_adoption_recurs", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


ABSENT = object()  # `recurs` left out of the item, distinct from `"recurs": null`


def item(item_id, recurs=ABSENT, detector=None):
    data = {
        "id": item_id,
        "since": "0.5.0",
        "what": f"{item_id} what.",
        "question": f"{item_id}?",
        "options": [
            {"answer": "adopted", "label": "Yes (Recommended)"},
            {"answer": "declined", "label": "No"},
        ],
        "detector": detector or {"kind": "decision-only"},
        "applies_when": None,
        "action": {"kind": "confirm", "detail": "Confirm it."},
    }
    if recurs is not ABSENT:
        data["recurs"] = recurs
    return data


RECURRING = item("refresh", recurs=True)
ONE_TIME = item("setting")
MANIFEST_DETECTED = item("keyed", recurs=True,
                         detector={"kind": "manifest-key", "key": "gates.confirm"})


def facts(manifest=None):
    return {"manifest": manifest or {}, "rules_doc": None, "schemas": [],
            "existing_globs": set(), "hook": {"copy": False, "current": False}}


def decided(decision, version):
    return {"decision": decision, "by": "T <t@example.com>", "at": "2026-10-01T00:00:00Z",
            "version": version}


def listed(items, decisions, installed, f=None):
    return [i["id"] for i in gates.adoption_undecided(items, f or facts(), decisions, installed)]


class TestLoaderRecurs(unittest.TestCase):
    """D4: `recurs` is optional, and when present it is a boolean."""

    def test_true_false_and_absent_load(self):
        items = gates.load_adoption_catalog({"items": [
            item("a", recurs=True), item("b", recurs=False), item("c")]})
        self.assertEqual([i["id"] for i in items], ["a", "b", "c"])

    def test_non_boolean_is_refused_naming_the_item(self):
        # Fails if "yes" or 1 were read as truthy: a typo would silently turn
        # a one-time item into one that asks again on every release.
        for bad in ("yes", 1, 0, None, "true", []):
            with self.subTest(recurs=bad):
                with self.assertRaises(gates.AdoptionError) as ctx:
                    gates.load_adoption_catalog({"items": [item("odd", recurs=bad)]})
                self.assertIn("odd", str(ctx.exception))
                self.assertIn("recurs", str(ctx.exception))


class TestRecurringDecisions(unittest.TestCase):
    """D4: for a recurring item the detector is the truth; `declined` is
    version-scoped like `later`."""

    def test_adopted_at_an_earlier_release_does_not_hide_it(self):
        # Scenario "A recurring item was adopted at an earlier release".
        self.assertEqual(listed([RECURRING], {"refresh": decided("adopted", "0.5.0")}, "0.6.0"),
                         ["refresh"])

    def test_adopted_at_the_installed_release_does_not_hide_it(self):
        # `adopted` never applies: if the detector still says not acted, the
        # act was not done, whatever the record says.
        self.assertEqual(listed([RECURRING], {"refresh": decided("adopted", "0.5.0")}, "0.5.0"),
                         ["refresh"])

    def test_detector_acted_hides_it_whatever_the_record(self):
        acted = facts({"gates": {"confirm": "smoke"}})
        for record in ({}, {"keyed": decided("adopted", "0.5.0")},
                       {"keyed": decided("declined", "0.4.0")}):
            with self.subTest(record=record):
                self.assertEqual(listed([MANIFEST_DETECTED], record, "0.6.0", acted), [])

    def test_declined_at_an_earlier_release_lists_it_again(self):
        # Scenario "A recurring item was declined at an earlier release".
        self.assertEqual(listed([RECURRING], {"refresh": decided("declined", "0.5.0")}, "0.6.0"),
                         ["refresh"])

    def test_declined_at_the_installed_release_hides_it(self):
        self.assertEqual(listed([RECURRING], {"refresh": decided("declined", "0.6.0")}, "0.6.0"),
                         [])

    def test_later_is_unchanged(self):
        self.assertEqual(listed([RECURRING], {"refresh": decided("later", "0.6.0")}, "0.6.0"), [])
        self.assertEqual(listed([RECURRING], {"refresh": decided("later", "0.5.0")}, "0.6.0"),
                         ["refresh"])


class TestOneTimeItemsAreUnchanged(unittest.TestCase):
    """Scenario "The project declined an item" (not recurring), with `recurs`
    absent and explicitly `false`."""

    def test_adopted_and_declined_hide_at_any_version(self):
        for variant in (ONE_TIME, item("setting", recurs=False)):
            for decision in ("adopted", "declined"):
                with self.subTest(recurs=variant.get("recurs"), decision=decision):
                    record = {"setting": decided(decision, "0.5.0")}
                    self.assertEqual(listed([copy.deepcopy(variant)], record, "0.9.0"), [])

    def test_items_are_judged_independently(self):
        records = {"refresh": decided("declined", "0.5.0"), "setting": decided("declined", "0.5.0")}
        self.assertEqual(listed([RECURRING, ONE_TIME], records, "0.6.0"), ["refresh"])


if __name__ == "__main__":
    unittest.main()
