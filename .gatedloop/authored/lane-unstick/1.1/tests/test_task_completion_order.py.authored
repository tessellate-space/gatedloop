"""Task completion ordered by commits (change `unblock-authored-lock`,
design D2).

The lock learns whether a task was completed when a ledger row was written:
the commit that first checks the task in `tasks.md` must come strictly
before the first commit carrying the row. The regressions: a halt staged
together with the task's tick read as a halt at a completed task (so the
tick would carry a halt in flight past its void); a halt committed after
the tick read as in flight; an uncommitted row judged against anything but
the checked state at `HEAD`; a ledger that shrinks accepted with a guessed
order instead of refused naming the commit; and a walk whose cost grows
faster than two blob reads per commit.

A lane that syncs by merging the target (change `lane-unstick`, design D1;
issue #178): the walk compared the lane's first commit with the merge-base,
the target's copy of the ledger, so approval rows appended on the target
after the fork read as the lane losing rows. The regressions: such a lane
refused by the walk and by `gates tests check`, at the index and at `--ref`;
and a real shrink on the lane after a sync merge accepted, or blamed on the
wrong commit.

The evaluator is called in-process, on real repositories: what is under
test is how commits order two blobs, which only a real history has, and the
blob-read count, which only an in-process counter can see.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _lock_fixture import LockRepo
from _merge_fixture import CHANGE as LOCK_CHANGE
from _merge_fixture import LEDGER_REL as LOCK_LEDGER_REL
from _merge_fixture import combined
from _merge_fixture import git as lock_git

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_completion_order", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "demo"
TASKS_REL = f"openspec/changes/{CHANGE}/tasks.md"
LEDGER_REL = f".gatedloop/runs/{CHANGE}.jsonl"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def _row(gate, task):
    return {"gate": gate, "task": task, "change": CHANGE, "ts": "2026-10-27T00:00:00+00:00"}


class CompletionOrderTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text('gatesVersion: 1\ngates:\n  ci: "true"\n')
        self._tasks()
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "plan: demo")
        _git(self.root, "checkout", "-q", "-b", CHANGE)

    def tearDown(self):
        self._tmp.cleanup()

    # ---- arranging a history --------------------------------------------

    def _tasks(self, *checked):
        lines = [f"- [{'x' if t in checked else ' '}] {t} task {t}" for t in ("1.1", "1.2")]
        p = self.root / TASKS_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("## 1. Demo\n\n" + "\n".join(lines) + "\n")

    def _append(self, *rows):
        p = self.root / LEDGER_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def _commit(self, subject):
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", subject)
        return _git(self.root, "rev-parse", "HEAD")

    def _completion(self, ref="HEAD"):
        return gates._task_completion(self.root, CHANGE, ref)

    # ---- the cases ------------------------------------------------------

    def test_a_halt_committed_after_the_tick_is_at_a_completed_task(self):
        self._append(_row("task-start", "1.1"), _row("tests-placed", "1.1"))
        self._tasks("1.1")
        self._commit("task 1.1")
        self._append(_row("halt", "1.1"))
        self._commit("halt at 1.1")

        c = self._completion()

        self.assertTrue(c.completed("1.1", 2))
        self.assertFalse(c.completed("1.1", 1), "a row committed with the tick is not after it")

    def test_a_halt_committed_with_the_tick_is_not_at_a_completed_task(self):
        self._append(_row("task-start", "1.2"), _row("tests-placed", "1.2"))
        self._commit("start 1.2")
        self._append(_row("halt", "1.2"))
        self._tasks("1.2")
        self._commit("halt at 1.2, ticked in the same commit")

        self.assertFalse(self._completion().completed("1.2", 2))

    def test_a_halt_staged_with_the_tick_is_not_at_a_completed_task(self):
        self._append(_row("task-start", "1.2"), _row("tests-placed", "1.2"))
        self._commit("start 1.2")
        self._append(_row("halt", "1.2"))
        self._tasks("1.2")
        _git(self.root, "add", "-A")

        self.assertFalse(self._completion().completed("1.2", 2))

    def test_an_uncommitted_row_is_judged_against_the_checked_state_at_head(self):
        self._append(_row("task-start", "1.1"), _row("tests-placed", "1.1"))
        self._tasks("1.1")
        self._commit("task 1.1")
        self._append(_row("halt", "1.1"), _row("halt", "1.2"))

        c = self._completion()

        self.assertTrue(c.completed("1.1", 2))
        self.assertFalse(c.completed("1.2", 3))

    def test_a_ledger_that_shrinks_is_refused_naming_the_commit(self):
        self._append(_row("task-start", "1.1"), _row("tests-placed", "1.1"), _row("unit", "1.1"))
        self._commit("three rows")
        (self.root / LEDGER_REL).write_text(json.dumps(_row("task-start", "1.1")) + "\n")
        rewrite = self._commit("the ledger loses two rows")

        with self.assertRaises(gates._LedgerRewritten) as caught:
            self._completion()

        self.assertIn(rewrite[:12], str(caught.exception))

    def test_two_blob_reads_per_commit(self):
        for n in range(5):
            self._append(_row("task-start", f"1.{n % 2 + 1}"))
            if n == 2:
                self._tasks("1.1")
            self._commit(f"commit {n}")
        commits = int(_git(self.root, "rev-list", "--count", "--first-parent", "main..HEAD")) + 1
        reads = []
        original = gates._blob_at

        def counting(root, commit, path):
            reads.append((commit, path))
            return original(root, commit, path)

        gates._blob_at = counting
        try:
            c = self._completion()
        finally:
            gates._blob_at = original

        self.assertEqual(len(reads), 2 * commits)
        self.assertTrue(c.completed("1.1", 3))
        self.assertFalse(c.completed("1.1", 2))


    # ---- a lane that merged the target in (lane-unstick D1) -------------

    def _on_main(self, *rows):
        """Append `rows` to the change's ledger on `main` and commit there."""
        _git(self.root, "checkout", "-q", "main")
        self._append(*rows)
        self._commit("rows appended on main")
        _git(self.root, "checkout", "-q", CHANGE)

    def _sync_main(self):
        """Merge `main` into the lane, resolving the ledger as a union: the
        lane's rows, then the rows `main` appended since the merge-base."""
        base = _git(self.root, "merge-base", "main", "HEAD")
        subprocess.run(["git", "merge", "--no-commit", "--no-ff", "main"], cwd=self.root,
                       capture_output=True, text=True)
        ours = _git(self.root, "show", f"HEAD:{LEDGER_REL}").splitlines()
        theirs = _git(self.root, "show", f"main:{LEDGER_REL}").splitlines()
        before = _git(self.root, "show", f"{base}:{LEDGER_REL}").splitlines()
        (self.root / LEDGER_REL).write_text("\n".join(ours + theirs[len(before):]) + "\n")
        return self._commit("merge main")

    def _forked_then_synced(self):
        """The ledger on `main` at the fork; the lane's first commit adds
        three rows; `main` then appends six approval rows; the lane merges
        `main`. The lane's first commit carries fewer rows than `main` now."""
        _git(self.root, "checkout", "-q", "main")
        self._append(_row("approval-local", None))
        self._commit("approval on main")
        _git(self.root, "checkout", "-q", CHANGE)
        _git(self.root, "merge", "-q", "--ff-only", "main")
        self._append(_row("task-start", "1.1"), _row("tests-placed", "1.1"), _row("unit", "1.1"))
        first = self._commit("start 1.1")
        self._on_main(*[_row("approval-local", None) for _ in range(6)])
        self._sync_main()
        return first

    def test_rows_appended_on_the_target_after_the_fork_are_not_a_shrink(self):
        self._forked_then_synced()
        self._append(_row("halt", "1.1"))
        self._commit("halt at 1.1")
        self._tasks("1.1")
        _git(self.root, "add", "-A")

        c = self._completion()

        self.assertFalse(c.completed("1.1", 10), "a tick only staged does not complete 1.1")
        self._commit("task 1.1")
        self._append(_row("halt", "1.1"))
        self._commit("halt after the tick")
        self.assertTrue(self._completion().completed("1.1", 11))

    def test_a_shrink_on_the_lane_after_a_sync_merge_is_refused_naming_it(self):
        first = self._forked_then_synced()
        (self.root / LEDGER_REL).write_text(json.dumps(_row("task-start", "1.1")) + "\n")
        rewrite = self._commit("the lane's ledger loses rows")

        with self.assertRaises(gates._LedgerRewritten) as caught:
            self._completion()

        self.assertIn(rewrite[:12], str(caught.exception))
        self.assertNotIn(first[:12], str(caught.exception))


LOCK_TASKS_REL = f"openspec/changes/{LOCK_CHANGE}/tasks.md"


class LaneSyncedWithTheTargetTest(unittest.TestCase):
    """Issue #178 through the lock itself: a lane whose target gained
    approval rows after the fork, merged in, then a halt naming task 1.1
    and 1.1's tick staged."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = LockRepo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _append_on_main(self, n):
        p = self.repo.primary / LOCK_LEDGER_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            for _ in range(n):
                f.write(json.dumps({"gate": "approval-local", "change": LOCK_CHANGE, "task": None,
                                    "ts": "2026-11-09T00:00:00+00:00", "exit": 0}) + "\n")
        lock_git(self.repo.primary, "add", LOCK_LEDGER_REL)
        lock_git(self.repo.primary, "commit", "-q", "-m", "attest approval")
        lock_git(self.repo.primary, "push", "-q", "origin", "HEAD:main")

    def _tick(self, *done):
        lines = [f"- [{'x' if t in done else ' '}] {t} task {t}" for t in ("1.1", "1.2", "1.3")]
        self.repo.write(LOCK_TASKS_REL, "## 1. Do it\n\n" + "\n".join(lines) + "\n")

    def _sync_origin_main(self):
        lane = self.repo.lane
        lock_git(lane, "fetch", "-q", "origin")
        base = lock_git(lane, "merge-base", "origin/main", "HEAD")
        lock_git(lane, "merge", "--no-commit", "--no-ff", "origin/main", check=False)
        ours = lock_git(lane, "show", f"HEAD:{LOCK_LEDGER_REL}").splitlines()
        theirs = lock_git(lane, "show", f"origin/main:{LOCK_LEDGER_REL}").splitlines()
        before = lock_git(lane, "show", f"{base}:{LOCK_LEDGER_REL}").splitlines()
        (lane / LOCK_LEDGER_REL).write_text("\n".join(ours + theirs[len(before):]) + "\n")
        self.repo.gated_commit("merge origin/main")

    def _halt_and_discard(self, task):
        self.repo.must("halt", "record", "oracle-conflict", "--task", task,
                       "--detail", "waiting on an amended plan")
        ledger = self.repo.lane / LOCK_LEDGER_REL
        rows = ledger.read_bytes()
        lock_git(self.repo.lane, "checkout", "-q", "--", ".")
        ledger.write_bytes(rows)
        self.repo.gated_commit(f"halt at {task}")

    def test_tests_check_passes_at_the_index_and_at_the_commit(self):
        self._append_on_main(1)
        self.repo.start_change(lane=True)
        self.repo.author()
        self._append_on_main(8)
        self._sync_origin_main()
        self.repo.place("1.1")
        self.repo.red("1.1")
        self._halt_and_discard("1.1")
        self.repo.place("1.1")
        self.repo.red("1.1")
        self.repo.write("src/task_1_1.txt", "task 1.1\n")
        self._tick("1.1")
        lock_git(self.repo.lane, "add", "-A")

        staged = self.repo.gates("tests", "check", cwd=self.repo.lane)

        self.assertEqual(staged.returncode, 0, combined(staged))
        self.repo.gated_commit("task 1.1", "1.1")
        at_ref = self.repo.check_ref("HEAD")
        self.assertEqual(at_ref.returncode, 0, combined(at_ref))


if __name__ == "__main__":
    unittest.main()
