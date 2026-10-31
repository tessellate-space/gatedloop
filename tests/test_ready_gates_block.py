"""`gates ledger record-ready` prints the READY report's gate block from the
ledger (loop-hardening D11, #112).

The regression: the implementer's READY report carries `ci`, `review` and
`live_check` fields it filled in itself, and the schema allowed only
`clean|findings` for the review. A report once said `findings` for a change
no review had run on -- the agent had to pick one of two wrong values.
`record-ready` now prints `gatedloop: gates {...}` derived from the ledger
and the markers, and the report copies it:

- `ci`: `pass` when a green unscoped `ci` row names the head's tree;
- `review`: over each completed task's latest review row -- `none` with no
  review row at all, `findings` when any is, `partial` when a completed task
  has none, else `clean`;
- `live_check`: the head tree's marker; `na` when nothing declares one.

Real git and `_merge_fixture`'s repository; the gates are the fixture's.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, MergeRepo, combined, git

TASKS_REL = f"openspec/changes/{CHANGE}/tasks.md"
PREFIX = "gatedloop: gates "


def _gates_block(repo: MergeRepo) -> dict:
    r = repo.gates("ledger", "record-ready", CHANGE, cwd=repo.lane)
    if r.returncode != 0:
        raise AssertionError(f"record-ready failed: {combined(r)}")
    lines = [x for x in r.stdout.splitlines() if x.startswith(PREFIX)]
    if len(lines) != 1:
        raise AssertionError(f"expected one `{PREFIX}` line: {r.stdout}")
    return json.loads(lines[0][len(PREFIX):])


class ReadyGatesBlock(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = MergeRepo(Path(self._tmp.name))
        self.repo.start_change(lane=True)
        # The plan's one task, 1.1, is already ticked in tasks.md.
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")

    def tearDown(self):
        self._tmp.cleanup()

    def review(self, verdict: str, task: str) -> None:
        r = self.repo.gates("review", "record", verdict, "--task", task, cwd=self.repo.lane)
        self.assertEqual(r.returncode, 0, combined(r))

    def test_no_review_row_reads_none(self):
        block = _gates_block(self.repo)
        self.assertEqual(block["review"], "none")
        self.assertEqual(block["ci"], "pass")
        self.assertEqual(block["live_check"], "na")

    def test_a_clean_review_of_every_completed_task_reads_clean(self):
        self.review("clean", "1.1")
        self.assertEqual(_gates_block(self.repo)["review"], "clean")

    def test_a_latest_findings_verdict_reads_findings(self):
        self.review("clean", "1.1")
        self.review("findings", "1.1")
        self.assertEqual(_gates_block(self.repo)["review"], "findings")

    def test_a_completed_task_with_no_review_reads_partial(self):
        self.repo.task_commit(TASKS_REL, "## 1. Do it\n\n- [x] 1.1 Add the thing\n"
                              "- [x] 1.2 And its sibling\n", "add and tick 1.2")
        self.review("clean", "1.1")
        self.assertEqual(_gates_block(self.repo)["review"], "partial")

    def test_a_head_with_no_green_ci_reads_fail(self):
        (self.repo.lane / "late.txt").write_text("committed past ci\n")
        git(self.repo.lane, "add", "late.txt")
        git(self.repo.lane, "commit", "-q", "-m", "a commit no ci ran on")
        self.assertEqual(_gates_block(self.repo)["ci"], "fail")


if __name__ == "__main__":
    unittest.main()
