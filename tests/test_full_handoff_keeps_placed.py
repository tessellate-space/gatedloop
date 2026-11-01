"""A full handoff may not drop a placed task (loop-hardening D10, #111).

The regression: `gates tests handoff <change>` without `--task` rebuilt the
authoring state from the holding area alone. Placement empties a task's
holding directory, so a full handoff run after task 1.1 was placed dropped
1.1's tests -- and its CHARACTERIZATION declaration -- from the state the
lock reads, and 1.1's committed test then read as unauthored. A full handoff
is the author's statement of the whole set, so it now refuses, naming each
placed task it would drop and the `--task` route for the tasks being
re-authored, and writes nothing.

Real git with a bare remote (`_lock_fixture`'s repository).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _lock_fixture import TEST_REL, TEST_V1, TEST_V2, LockRepo
from _merge_fixture import CHANGE, LEDGER_REL, combined


class AFullHandoffAfterPlacement(unittest.TestCase):
    def test_refuses_naming_the_placed_task_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = LockRepo(Path(tmp))
            repo.start_change(lane=True)
            repo.write(TEST_REL, "# the thing's tests, before this change\n")
            repo.gated_commit("the thing's existing tests")
            holding = repo.lane / ".gatedloop" / "authored" / CHANGE
            repo.write(f".gatedloop/authored/{CHANGE}/1.1/{TEST_REL}.authored", TEST_V1)
            repo.write(f".gatedloop/authored/{CHANGE}/1.1/CHARACTERIZATION",
                       "pins what the thing already does\n")
            repo.write(f".gatedloop/authored/{CHANGE}/1.2/tests/test_more.py.authored",
                       TEST_V2)
            repo.must("tests", "handoff", CHANGE)
            repo.gated_commit(f"author tests: {CHANGE}")
            repo.place("1.1")
            self.assertFalse((holding / "1.1").exists())
            ledger_before = (repo.lane / LEDGER_REL).read_text()

            r = repo.gates("tests", "handoff", CHANGE, cwd=repo.lane)

            self.assertEqual(r.returncode, 1, combined(r))
            self.assertIn("1.1", r.stderr)
            self.assertIn(f"gates tests handoff {CHANGE} --task 1.2", r.stderr)
            self.assertIn("Nothing was written", r.stderr)
            self.assertEqual((repo.lane / LEDGER_REL).read_text(), ledger_before)
            shown = json.loads(repo.must("tests", "show", CHANGE, "--json").stdout)
            self.assertIn("1.1", json.dumps(shown))
            self.assertIn("characterization", json.dumps(shown).lower())

    def test_a_task_handoff_after_placement_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = LockRepo(Path(tmp))
            repo.start_change(lane=True)
            repo.author()
            repo.place("1.1")

            r = repo.gates("tests", "handoff", CHANGE, "--task", "1.2", cwd=repo.lane)

            self.assertEqual(r.returncode, 0, combined(r))


if __name__ == "__main__":
    unittest.main()
