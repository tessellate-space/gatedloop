"""`epic-linkage` task 3.3 (design D7): the session brief prints one line per
active epic above the flat change list, and omits that epic's children from
the list. A repository with no epics gets a brief byte-identical to the one
before this change: `NO_EPICS_BRIEF` was captured from `hooks/_session_brief.py`
as it stood at 557122c, before any edit, over the same fixture and payload.

Feeds the helper a synthesized `openspec list --json` payload on stdin, in a
real throwaway repository (`tests/_epic_fixture.py`), with every adoption item
decided so no version-dependent adoption line appears.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _epic_fixture import EpicRepo, row  # noqa: E402

NO_EPICS_PAYLOAD = {"changes": [
    {"name": "solo", "status": "in-progress", "completedTasks": 1, "totalTasks": 3},
    {"name": "shipped", "status": "complete", "completedTasks": 2, "totalTasks": 2},
]}

NO_EPICS_BRIEF = (
    "1 change(s) underway (most-complete first):\n"
    "  - solo (1/3)\n"
    "1 complete & ready to archive: shipped\n"
)


class TestBriefWithoutEpics(unittest.TestCase):
    def test_a_repository_with_no_epics_gets_todays_brief_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = EpicRepo(tmp)
            repo.change("solo", tasks=(1, 3))
            repo.change("shipped", tasks=(2, 2))
            repo.commit("changes")
            repo.decide_all_adoption_items()
            self.assertEqual(repo.brief(NO_EPICS_PAYLOAD), NO_EPICS_BRIEF)


class TestBriefWithAnEpic(unittest.TestCase):
    def test_one_epic_line_above_the_list_and_no_repeated_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = EpicRepo(tmp)
            repo.change("autonomous-dev")
            repo.change("ledger-rollup", epic="autonomous-dev", archived=True, tasks=(2, 2))
            repo.change("lane-permissions", epic="autonomous-dev", approved=True, tasks=(1, 3))
            repo.ledger("lane-permissions", row("task-start", 1, task="1.2"))
            repo.change("not-started", epic="autonomous-dev", approved=True, tasks=(0, 2))
            repo.change("other-change", tasks=(1, 2))
            repo.commit("changes")
            repo.decide_all_adoption_items()

            out = repo.brief({"changes": [
                {"name": "autonomous-dev", "status": "no-tasks", "completedTasks": 0, "totalTasks": 0},
                {"name": "lane-permissions", "status": "in-progress", "completedTasks": 1, "totalTasks": 3},
                {"name": "not-started", "status": "in-progress", "completedTasks": 0, "totalTasks": 2},
                {"name": "other-change", "status": "in-progress", "completedTasks": 1, "totalTasks": 2},
            ]})
            lines = out.splitlines()

            epic_lines = [i for i, l in enumerate(lines) if l.startswith("Epic autonomous-dev:")]
            self.assertEqual(len(epic_lines), 1, out)
            epic_line = lines[epic_lines[0]]
            for part in ("1 archived", "1 implementing", "lane-permissions 1/3", "1 approved"):
                self.assertIn(part, epic_line)

            listed = [l for l in lines if l.startswith("  - ")]
            self.assertIn("  - other-change (1/2)", listed, out)
            for child in ("lane-permissions", "not-started"):
                self.assertFalse(any(l.startswith(f"  - {child}") for l in listed), out)
            self.assertLess(epic_lines[0], lines.index("  - other-change (1/2)"))


if __name__ == "__main__":
    unittest.main()
