"""The lock releases a voided path the approved plan moved out of the
authored set (change `release-voided-lock`, design D1-D3; the
test-discipline delta's "The lock releases a voided path the approved plan
moved out" requirement).

Task 2.1 declared `rewrites: scripts/check.sh`; its placement was voided by
a defect, which pins the script to its content before the change. The plan
is then amended on the merge target to tag 2.1 `[oracle: none]` and the
author re-hands it off `NO-TESTS`. From there the implementer's edit to the
script passes the lock -- unless one release condition is missing, and then
the refusal names the first one that is.

Real git, a bare `origin` and a lane worktree: the release reads the plan
from the merge target (`origin/HEAD`), and that boundary -- what a branch
can and cannot change -- is the behaviour under test, so no cheaper layer
can observe it. Every reader is covered: the staged index (the commit
hooks), `--task`, and `--ref` (the merge's remote check).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from _lock_fixture import LockRepo
from _merge_fixture import CHANGE, combined, git

SCRIPT = "scripts/check.sh"
SCRIPT_BASE = "#!/bin/sh\nexit 0\n"
SCRIPT_AUTHORED = "#!/bin/sh\n# the check, as the author rewrote it\nexit 0\n"
SCRIPT_EDITED = "#!/bin/sh\n# the check, as the amended plan has the implementer edit it\nexit 0\n"
OTHER_TEST = "tests/test_other.py"

TAGS_BEFORE = {"2.1": f"unit rewrites: {SCRIPT}", "3.1": "unit"}


def tasks_md(tags: dict[str, str]) -> str:
    return (
        "## 2. Check\n\n"
        f"- [ ] 2.1 Rewrite the check [oracle: {tags['2.1']}]\n\n"
        "## 3. Other\n\n"
        f"- [ ] 3.1 Add the other thing [oracle: {tags['3.1']}]\n"
    )


class VoidedScript:
    """The change at the point the lock is asked about: 2.1's placement of
    `SCRIPT` voided, the plan amended to tag 2.1 `none` on both the target
    and the branch, 2.1 re-handed off `NO-TESTS`, and (optionally) 3.1
    re-handed off holding `SCRIPT` itself."""

    def __init__(self, tmp: Path, third_holds_script: bool = False):
        self.repo = repo = LockRepo(tmp)
        self.tasks_rel = f"openspec/changes/{CHANGE}/tasks.md"
        repo_main = repo.primary
        (repo_main / "scripts").mkdir(parents=True, exist_ok=True)
        (repo_main / SCRIPT).write_text(SCRIPT_BASE)
        self.amend_target(TAGS_BEFORE, "plan: tag the tasks")
        repo.start_change(lane=True)
        self.lane = repo.lane

        self.hold("2.1", SCRIPT, SCRIPT_AUTHORED)
        self.hold("3.1", OTHER_TEST, "def test_other():\n    assert other()\n")
        repo.must("tests", "handoff", CHANGE)
        repo.gated_commit(f"author tests: {CHANGE}")

        repo.void("2.1")

        none_tags = dict(TAGS_BEFORE, **{"2.1": "none"})
        self.amend_target(none_tags, "plan: 2.1 adds no tests")
        self.amend_branch(none_tags, "sync the amended plan")

        holding = self.lane / ".gatedloop" / "authored" / CHANGE
        shutil.rmtree(holding / "2.1")
        (holding / "2.1").mkdir(parents=True)
        (holding / "2.1" / "NO-TESTS").write_text("the plan has the implementer edit the script\n")
        repo.must("tests", "handoff", CHANGE, "--task", "2.1")
        if third_holds_script:
            self.hold("3.1", SCRIPT, SCRIPT_AUTHORED + "# and 3.1's case\n")
            repo.must("tests", "handoff", CHANGE, "--task", "3.1")
        repo.gated_commit("re-hand off 2.1")

    # ---- arranging -------------------------------------------------------

    def hold(self, task: str, rel: str, content: str) -> None:
        p = self.lane / ".gatedloop" / "authored" / CHANGE / task / f"{rel}.authored"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    def amend_target(self, tags: dict[str, str], subject: str) -> None:
        """Amend and re-approve the plan on `main`, and push it to `origin`."""
        p = self.repo.primary
        (p / self.tasks_rel).write_text(tasks_md(tags))
        self.repo.approve_plan()
        git(p, "add", "-A")
        git(p, "commit", "-q", "-m", subject)
        git(p, "push", "-q", "origin", "HEAD:main")

    def amend_branch(self, tags: dict[str, str], subject: str) -> None:
        self.repo.write(self.tasks_rel, tasks_md(tags))
        self.repo.gated_commit(subject)

    def edit_script(self) -> None:
        self.repo.write(SCRIPT, SCRIPT_EDITED)
        git(self.lane, "add", "-A")

    # ---- the three readers -----------------------------------------------

    def check(self, *extra: str):
        return self.repo.gates("tests", "check", *extra, cwd=self.lane)

    def check_committed(self):
        sha = self.repo.gated_commit("edit the script")
        return self.repo.check_ref(sha, "--change", CHANGE)


class ReleasedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.change = VoidedScript(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_edit_passes_the_staged_check(self):
        self.change.edit_script()

        r = self.change.check()

        self.assertEqual(r.returncode, 0, combined(r))

    def test_the_merge_remote_check_agrees(self):
        self.change.edit_script()

        r = self.change.check_committed()

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertNotIn(SCRIPT, combined(r))


class StillPinnedTest(unittest.TestCase):
    """Each missing condition keeps the pin, and the refusal names it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def assert_pinned(self, r, clause: str):
        out = combined(r)
        self.assertEqual(r.returncode, 1, out)
        self.assertIn(f"{SCRIPT}: ", out)
        self.assertIn(clause, out)

    def test_the_tag_still_names_a_gate(self):
        change = VoidedScript(Path(self._tmp.name))
        unit_again = dict(TAGS_BEFORE, **{"2.1": "unit"})
        change.amend_target(unit_again, "plan: 2.1 is a unit task again")
        change.amend_branch(unit_again, "sync the plan")
        change.edit_script()

        self.assert_pinned(
            change.check(),
            "task 2.1 is not tagged [oracle: none] in the approved plan on origin/main",
        )

    def test_only_the_branch_tags_it_none_on_every_reader(self):
        change = VoidedScript(Path(self._tmp.name))
        change.amend_target(dict(TAGS_BEFORE, **{"2.1": "unit"}), "plan: 2.1 is a unit task again")
        change.edit_script()
        clause = "task 2.1 is not tagged [oracle: none] in the approved plan on origin/main"

        with self.subTest(reader="staged"):
            self.assert_pinned(change.check(), clause)
        with self.subTest(reader="--task of another task"):
            self.assert_pinned(change.check("--task", "3.1"), clause)
        with self.subTest(reader="--ref"):
            self.assert_pinned(change.check_committed(), clause)

    def test_only_the_target_tags_it_none(self):
        change = VoidedScript(Path(self._tmp.name))
        change.amend_branch(dict(TAGS_BEFORE, **{"2.1": "unit"}), "re-tag 2.1 on the branch")
        change.edit_script()

        self.assert_pinned(change.check(), "task 2.1 is not tagged [oracle: none] in this tree")

    def test_no_merge_target_resolves(self):
        change = VoidedScript(Path(self._tmp.name))
        git(change.lane, "remote", "set-head", "origin", "-d")
        git(change.repo.primary, "branch", "-m", "main", "trunk")
        change.edit_script()

        self.assert_pinned(change.check(), "could not be read")

    def test_the_target_does_not_hold_the_change(self):
        change = VoidedScript(Path(self._tmp.name))
        p = change.repo.primary
        git(p, "rm", "-q", "-r", f"openspec/changes/{CHANGE}")
        git(p, "commit", "-q", "-m", "drop the change from main")
        git(p, "push", "-q", "origin", "HEAD:main")
        change.edit_script()

        self.assert_pinned(change.check(), "the approved plan on origin/main could not be read")

    def test_another_task_handoff_holds_the_path(self):
        change = VoidedScript(Path(self._tmp.name), third_holds_script=True)
        change.edit_script()

        self.assert_pinned(change.check(), "task 3.1's handoff holds it")


if __name__ == "__main__":
    unittest.main()
