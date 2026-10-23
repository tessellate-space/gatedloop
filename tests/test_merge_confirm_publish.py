"""`gates merge` steps 5 and 6: confirm, then archive and publish (design
D2/D3 of `merge-step`, and the `confirm` gate of `gate-binding`).

The remote target must never see an unconfirmed tree: every local commit
goes out in one push at the very end. The regressions: a red or
precondition-failed `confirm` still publishing, its failure lost with the
discarded commits instead of recorded on the branch, more than one push, a
moved target published over or retried forever, a failed archive leaving a
half-published merge, and the primary left detached (or its `main` left
behind) after a success.

Real git with a bare remote, whose post-receive hook counts pushes: "one
push" and "the target moved" are remote-side facts.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from _merge_fixture import CHANGE, LEDGER_REL, MergeRepo, combined, git


class ConfirmAndPublishTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _ready(self, lane: bool, manifest_extra: str = "") -> MergeRepo:
        repo = MergeRepo(self.tmp, manifest_extra=manifest_extra)
        repo.start_change(lane=lane)
        repo.task_commit("feature.txt", "the thing\n", "add the thing")
        repo.prove_head()
        return repo

    def _mover(self, once: bool) -> str:
        """A `confirm` body that lands another integrator's commit on origin
        while the merge is in flight -- the first time only, or every time."""
        script = self.tmp / "move.sh"
        flag = self.tmp / "moved.flag"
        guard = f'[ -f "{flag}" ] && exit 0\ntouch "{flag}"\n' if once else ""
        script.write_text(
            "#!/bin/sh\n" + guard
            + f'cd "{self.tmp / "other"}" || exit 1\n'
            + "git pull -q --ff-only origin main\n"
            + "git commit -q --allow-empty -m moved\n"
            + "git push -q origin HEAD:main\n"
        )
        return f'  confirm: "sh {script}"\n'

    def test_every_step_passing_publishes_three_commits_in_one_push(self):
        repo = self._ready(lane=True, manifest_extra='  confirm: "true"\n')
        before = repo.origin_main()

        r = repo.merge()

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(repo.pushes(), 1)
        log = repo.origin_log(before)
        self.assertEqual(len(log), 3, log)
        (squash, _s1, _b1), (record, _s2, _b2), (archive, _s3, _b3) = log
        self.assertTrue(log[0][1].startswith(f"{CHANGE}: "), log[0][1])
        self.assertEqual(repo.files_in_commit(record, cwd=repo.bare), [LEDGER_REL])
        merge_rows = [row for row in repo.rows_at(archive, cwd=repo.bare) if row.get("gate") == "merge"]
        self.assertEqual([row.get("sha") for row in merge_rows], [squash])
        tree = git(repo.bare, "ls-tree", "-r", "--name-only", archive).splitlines()
        self.assertFalse(any(p.startswith(f"openspec/changes/{CHANGE}/") for p in tree))
        self.assertTrue(any(p.startswith("openspec/changes/archive/") and f"-{CHANGE}/" in p for p in tree))
        self.assertIn("openspec/specs/cap/spec.md", tree)
        branch, sha, status = repo.head_state()
        self.assertEqual((branch, sha, status), ("main", archive, ""),
                         "the primary is not back on a fast-forwarded, clean main")

    def test_an_undeclared_confirm_is_skipped_with_a_note(self):
        repo = self._ready(lane=True)

        r = repo.merge()

        self.assertEqual(r.returncode, 0, combined(r))
        notes = [line for line in combined(r).splitlines() if "confirm" in line and "skip" in line]
        self.assertTrue(notes, combined(r))

    def test_a_failing_confirm_publishes_nothing_and_records_the_failure_on_the_branch(self):
        # A precondition failure means `confirm` did not run: the merge exits
        # 75, not the step number (design D1 of `merge-lane-friction`).
        cases = (
            ("red", '  confirm: "false"\n', True, 5),
            ("precondition", '  confirm:\n    run: "true"\n    requires: "false"\n', False, 75),
        )
        for name, extra, lane, code in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                self.tmp = Path(tmp)
                repo = self._ready(lane=lane, manifest_extra=extra)
                origin_before = repo.origin_main()
                primary_branch_before = git(repo.primary, "branch", "--show-current")

                r = repo.merge()

                self.assertEqual(r.returncode, code, combined(r))
                if name == "precondition":
                    self.assertIn("precondition", combined(r))
                self.assertEqual(repo.origin_main(), origin_before)
                self.assertEqual(repo.pushes(), 0)
                branch, _sha, status = repo.head_state()
                self.assertEqual((branch, status), (primary_branch_before, ""))
                rows = repo.rows_at(CHANGE)
                self.assertTrue(rows and rows[-1].get("gate") == "confirm" and rows[-1].get("exit") != 0,
                                f"no confirm failure committed on the branch: {rows[-1:] if rows else rows}")
                self.assertEqual(repo.files_in_commit(CHANGE), [LEDGER_REL])
                self.assertEqual(git(repo.lane, "status", "--porcelain"), "")

    def test_a_target_that_moved_once_is_retried_from_step_2(self):
        repo = self._ready(lane=True, manifest_extra=self._mover(once=True))
        before = repo.origin_main()

        r = repo.merge()

        self.assertEqual(r.returncode, 0, combined(r))
        subjects = [s for _sha, s, _b in repo.origin_log(before)]
        self.assertEqual(subjects[0], "moved", subjects)
        self.assertEqual(len(subjects), 4, subjects)
        self.assertTrue(subjects[1].startswith(f"{CHANGE}: "), subjects)

    def test_a_target_that_moves_again_halts_at_step_6(self):
        repo = self._ready(lane=True, manifest_extra=self._mover(once=False))
        before = repo.origin_main()
        head_before = repo.head_state()

        r = repo.merge()

        self.assertEqual(r.returncode, 6, combined(r))
        subjects = [s for _sha, s, _b in repo.origin_log(before)]
        self.assertEqual(subjects, ["moved", "moved"])
        branch, _sha, status = repo.head_state()
        self.assertEqual((branch, status), (head_before[0], ""))

    def test_a_failed_archive_publishes_nothing(self):
        repo = self._ready(lane=True)
        before = repo.origin_main()
        head_before = repo.head_state()

        r = repo.merge(FAKE_OPENSPEC_ARCHIVE_FAILS="1")

        self.assertEqual(r.returncode, 6, combined(r))
        self.assertIn("archive refused", combined(r))
        self.assertEqual(repo.origin_main(), before)
        self.assertEqual(repo.head_state(), head_before)


if __name__ == "__main__":
    unittest.main()
