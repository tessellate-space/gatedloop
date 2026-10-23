"""The serialized gate's wait (design D1/D2 of `lock-and-ledger-hygiene`,
#33 items 5 and 6).

A lane waiting on another lane's `ci` lock used to print "still waiting..."
on every 0.2 s poll: a five-minute wait overflowed the agent's tool-output
cap and killed the gate run, and the notice never said how long the lock had
been held, so a hung holder looked exactly like a busy one. The notice is
now printed once at once, then at most every 30 s, and names the holder's
pid, its liveness, its hold age and this run's wait.

The wait is driven by an injected clock and sleep (`gatedloop.test-quality`
item 7: no real timers in a unit test). The lock itself is real: this test
process holds it through its own file handle, exactly as another lane would.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import argparse
import contextlib
import datetime
import fcntl
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_lock_wait", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

MANIFEST_SERIALIZED_CI = (
    'gatesVersion: 1\n'
    'gates:\n  ci: "true"\n'
    'concurrency:\n  serialize:\n    - ci\n'
)
WALL_BASE = 1_800_000_000.0  # an arbitrary fixed epoch for the fake wall clock


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _iso(epoch: float) -> str:
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()


def _dead_pid() -> int:
    """The pid of a process that has already exited and been reaped."""
    p = subprocess.Popen([sys.executable, "-c", ""])
    p.wait()
    return p.pid


class _FakeTime:
    """A clock the wait loop reads and a sleep that advances it, releasing
    the held lock once `release_at` seconds have passed."""

    def __init__(self, release_at: float, on_release):
        self.t = 0.0
        self.release_at = release_at
        self.on_release = on_release
        self.released = False

    def clock(self) -> float:
        return self.t

    def wall(self) -> float:
        return WALL_BASE + self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds
        if self.t > 3600:
            raise AssertionError("the wait never ended: an hour of fake time passed")
        if not self.released and self.t >= self.release_at:
            self.released = True
            self.on_release()


class _HeldLock:
    """Another lane holding the `ci` lock: a real flock on a separate file
    handle, with the holder metadata that lane would have written."""

    def __init__(self, root: Path, pid: int, held_since: float):
        path = root / ".git" / "gatedloop" / "locks" / "ci.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "a+")
        fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.fh.seek(0)
        self.fh.truncate()
        self.fh.write(json.dumps({"pid": pid, "ts": _iso(held_since)}))
        self.fh.flush()

    def release(self) -> None:
        fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        self.fh.close()


def _wait_for_lock(root: Path, holder_pid: int, wait_seconds: float) -> list[str]:
    """Run `_gate_lock` against a lock held since 192 s before the wait
    started, released after `wait_seconds`; return the stderr lines."""
    held = _HeldLock(root, holder_pid, held_since=WALL_BASE - 192)
    fake = _FakeTime(wait_seconds, held.release)
    m = gates._mini_yaml(MANIFEST_SERIALIZED_CI)
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            with gates._gate_lock(root, m, "ci", clock=fake.clock, wall=fake.wall, sleep=fake.sleep):
                pass
    finally:
        if not fake.released:
            held.release()
    return [line for line in err.getvalue().splitlines() if line.strip()]


class TestWaitNotice(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _git(self.root, "init", "-b", "main")

    def tearDown(self):
        self._tmp.cleanup()

    def test_five_minute_wait_prints_at_most_eleven_informative_lines(self):
        lines = _wait_for_lock(self.root, os.getpid(), wait_seconds=300)
        self.assertGreaterEqual(len(lines), 2, lines)
        self.assertLessEqual(len(lines), 11, f"{len(lines)} lines: {lines[:3]}...")
        self.assertIn(f"held by pid {os.getpid()} (alive) for 3m12s", lines[0])
        later = lines[-1]
        self.assertIn(f"pid {os.getpid()} (alive)", later)
        self.assertRegex(later, r"waited 4m[3-5]\ds")

    def test_a_dead_holder_is_named_as_such(self):
        pid = _dead_pid()
        lines = _wait_for_lock(self.root, pid, wait_seconds=1)
        self.assertIn(f"held by pid {pid} (dead?)", lines[0])


class TestWaitBound(unittest.TestCase):
    """D2: a wait that outlives the host's tool timeout gets the gate
    backgrounded (#33 item 6). The bound ends it first, below that cap: exit
    75 with the stable `gatedloop: lock busy` prefix and a `lock-busy` ledger
    row, and the gate command never runs. Driven through `cmd_run` -- the
    exit code, message and row are all produced there -- with the module's
    clock and sleep replaced, so no real time passes."""

    def _run_ci_against_held_lock(self, manifest: str):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        _git(root, "init", "-b", "main")
        held = _HeldLock(root, os.getpid(), held_since=WALL_BASE)
        self.addCleanup(held.release)
        fake = _FakeTime(release_at=float("inf"), on_release=lambda: None)
        args = argparse.Namespace(
            gate="ci", gate_args=[], changed=None, all=False,
            change="lane", task="1.2", attempt=1, verbose=False,
        )
        err = io.StringIO()
        cwd = os.getcwd()
        os.chdir(root)
        try:
            with mock.patch.object(gates.time, "monotonic", fake.clock), \
                 mock.patch.object(gates.time, "sleep", fake.sleep), \
                 contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = gates.cmd_run(gates._mini_yaml(manifest), root, args)
        finally:
            os.chdir(cwd)
        rows = [json.loads(line) for line in
                (root / ".gatedloop" / "runs" / "lane.jsonl").read_text().splitlines()]
        return rc, err.getvalue(), rows, fake.t, root

    def test_the_bound_ends_the_wait_without_running_the_gate(self):
        ran = "ran.txt"
        base = f'gatesVersion: 1\ngates:\n  ci: "touch {ran}"\nconcurrency:\n  serialize:\n    - ci\n'
        for label, extra, bound in (("default", "", 480), ("declared", "  max-wait-seconds: 60\n", 60)):
            with self.subTest(bound=label):
                rc, err, rows, waited, root = self._run_ci_against_held_lock(base + extra)
                self.assertEqual(rc, 75, err)
                self.assertTrue(
                    any(line.startswith("gatedloop: lock busy") for line in err.splitlines()), err,
                )
                self.assertFalse((root / ran).exists(), "the gate command ran despite the busy lock")
                self.assertGreaterEqual(waited, bound)
                self.assertLess(waited, bound + 1)
                self.assertEqual(rows[-1]["gate"], "ci")
                self.assertEqual(rows[-1]["exit"], 75)
                self.assertEqual(rows[-1]["precondition"], "lock-busy")
                self.assertIsNone(rows[-1]["tree"])


if __name__ == "__main__":
    unittest.main()
