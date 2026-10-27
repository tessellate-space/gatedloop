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


if __name__ == "__main__":
    unittest.main()
