"""`epic-linkage` task 3.1 (design D5): `gates epics [--json]` lists every
epic, active or archived, with each child's derived state and tasks done of
total. The ledger part starts from the outcomes classifier, so the state a
child gets here never contradicts `gates stats --outcomes`.

JSON shape fixed by these tests:
    {"epics": [{"epic", "archived", "drained",
                "children": [{"change", "state", "halt_cause",
                              "tasks": {"done", "total"}}]}]}
epics and children sorted by name.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epic_fixture import EpicRepo, row  # noqa: E402

EPIC = "autonomous-dev"

# child -> (expected state, expected halt cause, tasks, ledger rows, extra kwargs)
CHILDREN = {
    "a-archived": ("archived", None, (2, 2), [], {"archived": True}),
    "b-merged": ("merged", None, (2, 2), [
        row("task-start", 1, task="1.1"), row("ci", 2, task="1.1"), row("merge", 3, sha="abc"),
    ], {"approved": True}),
    "c-halted": ("halted", "weak-spec", (0, 2), [
        row("task-start", 1, task="1.1"), row("halt", 2, task="1.1", cause="weak-spec"),
    ], {"approved": True}),
    "d-ready": ("ready", None, (2, 2), [
        row("task-start", 1, task="1.2"), row("ready", 2),
    ], {"approved": True}),
    "e-implementing": ("implementing", None, (1, 3), [
        row("task-start", 1, task="1.1"), row("halt", 2, task="1.1", cause="stalled"),
        row("task-start", 3, task="1.1"),
    ], {"approved": True}),
    "f-approved": ("approved", None, (0, 2), [], {"approved": True}),
    "g-proposed": ("proposed", None, None, [], {}),
}

# Each ledger-derived state, and the `stats --outcomes` terminal it must sit under.
OUTCOME_OF = {"merged": ("merged", "accepted"), "halted": ("halted",),
              "ready": ("in-progress",), "implementing": ("in-progress",)}


class TestEpicsListing(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = EpicRepo(self._tmp.name)
        self.repo.change(EPIC)
        for child, (_state, _cause, tasks, rows, kw) in CHILDREN.items():
            self.repo.change(child, epic=EPIC, tasks=tasks, **kw)
            if rows:
                self.repo.ledger(child, *rows)
        # An active epic whose only child is archived, and an archived epic.
        self.repo.change("drained-epic")
        self.repo.change("drained-child", epic="drained-epic", archived=True)
        self.repo.change("older-epic", archived=True)
        self.repo.change("older-child", epic="older-epic", archived=True)
        self.repo.change("not-an-epic")
        self.repo.commit("changes")

    def tearDown(self):
        self._tmp.cleanup()

    def _epics(self) -> dict:
        return {e["epic"]: e for e in self.repo.gates_json("epics", "--json")["epics"]}

    def test_every_child_state_is_derived(self):
        epic = self._epics()[EPIC]
        got = {c["change"]: c for c in epic["children"]}
        self.assertEqual(sorted(got), sorted(CHILDREN))
        for child, (state, cause, tasks, _rows, _kw) in CHILDREN.items():
            with self.subTest(child):
                self.assertEqual(got[child]["state"], state)
                self.assertEqual(got[child]["halt_cause"], cause)
                done, total = tasks or (0, 0)
                self.assertEqual(got[child]["tasks"], {"done": done, "total": total})
        self.assertFalse(epic["drained"])
        self.assertFalse(epic["archived"])

    def test_only_named_changes_are_epics_and_drained_is_reported(self):
        epics = self._epics()
        self.assertEqual(sorted(epics), sorted([EPIC, "drained-epic", "older-epic"]))
        self.assertTrue(epics["drained-epic"]["drained"])
        self.assertFalse(epics["drained-epic"]["archived"])
        self.assertTrue(epics["older-epic"]["drained"])
        self.assertTrue(epics["older-epic"]["archived"])

    def test_ledger_states_agree_with_stats_outcomes(self):
        got = {c["change"]: c["state"] for c in self._epics()[EPIC]["children"]}
        for child, (_s, _c, _t, rows, _kw) in CHILDREN.items():
            if not rows:
                continue
            with self.subTest(child):
                doc = self.repo.gates_json("stats", "--outcomes", "--change", child, "--json")
                terminal = doc["changes"][0]["terminal"]
                self.assertIn(terminal, OUTCOME_OF[got[child]])

    def test_the_human_listing_names_each_child_and_its_state(self):
        r = self.repo.gates("epics")
        self.assertEqual(r.returncode, 0, r.stderr)
        for child, (state, *_rest) in CHILDREN.items():
            line = next((l for l in r.stdout.splitlines() if child in l), "")
            self.assertIn(state, line, r.stdout)

    def test_a_repository_with_no_epics_lists_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = EpicRepo(tmp)
            repo.change("solo")
            self.assertEqual(repo.gates_json("epics", "--json"), {"epics": []})


if __name__ == "__main__":
    unittest.main()
