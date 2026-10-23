"""A waiting merge takes a serialized lock before other waiters (design D2
of `merge-lane-friction`, issue #43).

While `gates merge` waits on a serialized gate's lock it holds a priority
claim, `<lockfile>.priority` holding `{"pid", "ts"}`. Any other waiter that
sees a live claim does not try to acquire, even when the lock is free; a
claim whose pid is dead is ignored and removed. The regressions these catch:
a lane taking the lock ahead of a waiting merge (the merge queue stalling
behind lanes), a stale claim blocking every lane forever, a merge leaving
its claim behind after acquiring or giving up, and `gates lock status` not
showing who is waiting with priority.

Single-waiter cases run `_gate_lock` in process on an injected clock
(`FakeTime`, `gatedloop.test-quality` item 7); a claim from another process
is a file naming a live child pid. The ordering case needs two real
waiters in two processes, because a claim is told apart from a waiter's own
by pid: it is scripted, each step waiting on a line the waiter prints,
never on a sleep.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from _merge_fixture import GATES_SHIM, FakeTime, HeldLock, clean_env, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_lock_priority", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

MANIFEST = (
    'gatesVersion: 1\ngates:\n  ci: "true"\n'
    "concurrency:\n  serialize:\n    - ci\n"
)

# One waiter: take the `ci` lock (with or without the merge's priority),
# append its name to order.log once it holds it, say so, and hold until a
# line arrives on stdin.
WAITER = r"""
import importlib.machinery, importlib.util, sys
from pathlib import Path
shim, root, name, priority = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4] == "1"
loader = importlib.machinery.SourceFileLoader("gates_waiter", shim)
spec = importlib.util.spec_from_loader(loader.name, loader)
gates = importlib.util.module_from_spec(spec)
loader.exec_module(gates)
m = gates._mini_yaml((root / ".gates.yaml").read_text())
with gates._gate_lock(root, m, "ci", max_wait=120, priority=priority):
    with open(root / "order.log", "a") as f:
        f.write(name + "\n")
    print("acquired", flush=True)
    sys.stdin.readline()
"""

# A safety net against a hang, never a timing assumption: each step waits
# on a line the waiter prints.
LINE_DEADLINE_SECONDS = 60


class _Lines:
    """Lines from a child's stream, read on a thread so a missing line fails
    the test instead of hanging it."""

    def __init__(self, stream):
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._pump, args=(stream,), daemon=True).start()

    def _pump(self, stream):
        for line in stream:
            self.q.put(line)
        self.q.put(None)

    def next(self, what: str) -> str:
        try:
            line = self.q.get(timeout=LINE_DEADLINE_SECONDS)
        except queue.Empty:
            raise AssertionError(f"no line from {what}")
        if line is None:
            raise AssertionError(f"{what} exited before printing a line")
        return line


class LockPriorityTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        (self.root / ".gates.yaml").write_text(MANIFEST)
        self.m = gates._mini_yaml(MANIFEST)
        self.m["__root__"] = str(self.root)
        self.held = None
        self.children: list[subprocess.Popen] = []

    def tearDown(self):
        if self.held is not None:
            self.held.release()
        for p in self.children:
            if p.poll() is None:
                p.kill()
            p.wait()
            for s in (p.stdin, p.stdout, p.stderr):
                if s:
                    s.close()
        self._tmp.cleanup()

    # ---- helpers ------------------------------------------------------

    def _claim_path(self) -> Path:
        lock = gates._lock_path(self.root, "ci")
        return lock.with_name(lock.name + ".priority")

    def _live_pid(self) -> int:
        p = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                             stdin=subprocess.PIPE, env=clean_env())
        self.children.append(p)
        return p.pid

    def _dead_pid(self) -> int:
        p = subprocess.Popen([sys.executable, "-c", "pass"], env=clean_env())
        p.wait()
        return p.pid

    def _write_claim(self, pid: int) -> None:
        path = self._claim_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"pid": pid, "ts": "2026-10-21T00:00:00+00:00"}))

    def _waiter(self, name: str, priority: bool) -> tuple[subprocess.Popen, _Lines, _Lines]:
        p = subprocess.Popen(
            [sys.executable, "-c", WAITER, str(GATES_SHIM), str(self.root), name,
             "1" if priority else "0"],
            cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, env=clean_env(),
        )
        self.children.append(p)
        return p, _Lines(p.stdout), _Lines(p.stderr)

    def _order(self) -> list[str]:
        path = self.root / "order.log"
        return path.read_text().split() if path.exists() else []

    # ---- a claim from another process --------------------------------

    def test_a_free_lock_is_not_taken_while_a_live_merge_claims_it(self):
        self._write_claim(self._live_pid())
        fake = FakeTime(release_at=3.0, on_release=self._claim_path().unlink)
        entered = False
        with contextlib.redirect_stderr(io.StringIO()):
            with gates._gate_lock(self.root, self.m, "ci", max_wait=100,
                                  clock=fake.clock, wall=fake.wall, sleep=fake.sleep):
                entered = True
        self.assertTrue(entered)
        self.assertGreaterEqual(fake.t, 3.0, "a lane took the lock ahead of a waiting merge")

    def test_a_claim_with_a_dead_pid_is_ignored_and_removed(self):
        self._write_claim(self._dead_pid())
        fake = FakeTime()
        with contextlib.redirect_stderr(io.StringIO()):
            with gates._gate_lock(self.root, self.m, "ci", max_wait=100,
                                  clock=fake.clock, wall=fake.wall, sleep=fake.sleep):
                pass
        self.assertLess(fake.t, 1.0, "a stale claim held a free lock back")
        self.assertFalse(self._claim_path().exists())

    # ---- the merge's own claim ---------------------------------------

    def test_a_waiting_merge_claims_the_lock_and_drops_the_claim_once_it_holds_it(self):
        self.held = HeldLock(self.root / ".git", "ci", os.getpid())
        seen: list = []

        def release():
            path = self._claim_path()
            seen.append(json.loads(path.read_text()) if path.exists() else None)
            self.held.release()

        fake = FakeTime(release_at=2.0, on_release=release)
        with contextlib.redirect_stderr(io.StringIO()):
            with gates._gate_lock(self.root, self.m, "ci", max_wait=100, priority=True,
                                  clock=fake.clock, wall=fake.wall, sleep=fake.sleep):
                self.assertFalse(self._claim_path().exists(), "the claim outlived the wait")
        self.assertEqual(len(seen), 1)
        self.assertIsNotNone(seen[0], "no claim was written while the merge waited")
        self.assertEqual(seen[0].get("pid"), os.getpid())

    def test_a_merge_that_gives_up_drops_its_claim(self):
        self.held = HeldLock(self.root / ".git", "ci", os.getpid())
        fake = FakeTime()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(gates._LockBusy):
                with gates._gate_lock(self.root, self.m, "ci", max_wait=5, priority=True,
                                      clock=fake.clock, wall=fake.wall, sleep=fake.sleep):
                    self.fail("entered a lock another process holds")
        self.assertFalse(self._claim_path().exists())

    # ---- the scenario: a lane holds, a merge and a lane wait ---------

    def test_a_waiting_merge_acquires_before_a_waiting_lane(self):
        self.held = HeldLock(self.root / ".git", "ci", os.getpid())
        merge, merge_out, merge_err = self._waiter("merge", priority=True)
        merge_err.next("the merge waiter's first waiting line")
        self.assertTrue(self._claim_path().exists(), "the waiting merge wrote no claim")
        lane, lane_out, lane_err = self._waiter("lane", priority=False)
        lane_err.next("the lane waiter's first waiting line")

        self.held.release()
        self.assertEqual(merge_out.next("the merge waiter").strip(), "acquired")
        self.assertEqual(self._order(), ["merge"])

        merge.stdin.write("\n")
        merge.stdin.flush()
        self.assertEqual(lane_out.next("the lane waiter").strip(), "acquired")
        self.assertEqual(self._order(), ["merge", "lane"])
        lane.stdin.write("\n")
        lane.stdin.flush()

    # ---- lock status -------------------------------------------------

    def test_lock_status_shows_the_merge_waiting_with_priority(self):
        self.held = HeldLock(self.root / ".git", "ci", os.getpid())
        claimant = self._live_pid()
        self._write_claim(claimant)
        r = subprocess.run(
            [sys.executable, str(GATES_SHIM), "lock", "status"],
            cwd=self.root, capture_output=True, text=True, env=clean_env(),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        line = next((x for x in r.stdout.splitlines() if x.startswith("ci:")), None)
        self.assertIsNotNone(line, f"no ci line in: {r.stdout!r}")
        self.assertIn(f"pid {os.getpid()}", line)
        self.assertIn(f"merge pid {claimant} waiting with priority", line)


if __name__ == "__main__":
    unittest.main()
