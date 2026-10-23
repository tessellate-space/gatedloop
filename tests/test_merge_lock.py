"""The `merge` lock (design D4 of `merge-step`).

Two local merges into one target from one machine cannot both be right, so
`gates merge` holds a machine-wide `merge` lock through `_gate_lock`'s
mechanism -- always serialized, with no `concurrency.serialize` entry
needed, and bounded by `concurrency.max-wait-seconds` like every serialized
gate. Regressions these catch: the lock silently becoming a no-op because
`merge` is not declared serialized (the default `_gate_lock` behaviour), the
wait ignoring the declared bound, and `gates lock status` saying nothing
about a held merge lock that the busy message tells the reader to inspect.

The wait is driven by an injected clock (`gatedloop.test-quality` item 7);
the lock itself is real, held by this test process on its own handle.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import BASE_MANIFEST, GATES_SHIM, FakeTime, HeldLock, clean_env, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_merge_lock", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class MergeLockTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        self.held = None

    def tearDown(self):
        if self.held is not None:
            self.held.release()
        self._tmp.cleanup()

    def _manifest(self, extra: str = "") -> dict:
        m = gates._mini_yaml(BASE_MANIFEST + extra)
        m["__root__"] = str(self.root)
        return m

    def _hold(self) -> None:
        self.held = HeldLock(self.root / ".git", "merge", os.getpid())

    def test_a_second_merge_waits_although_nothing_declares_merge_serialized(self):
        self._hold()
        fake = FakeTime(release_at=3.0, on_release=self.held.release)
        err = io.StringIO()
        entered = False
        with contextlib.redirect_stderr(err):
            with gates._merge_lock(self.root, self._manifest(),
                                   clock=fake.clock, wall=fake.wall, sleep=fake.sleep):
                entered = True
        self.assertTrue(entered)
        self.assertGreaterEqual(fake.t, 3.0, "the lock was entered while another merge held it")
        self.assertIn("merge", err.getvalue())

    def test_the_wait_is_bounded_by_the_declared_max_wait(self):
        self._hold()
        fake = FakeTime()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(gates._LockBusy) as cm:
                with gates._merge_lock(
                    self.root, self._manifest("concurrency:\n  max-wait-seconds: 5\n"),
                    clock=fake.clock, wall=fake.wall, sleep=fake.sleep,
                ):
                    self.fail("entered a lock another merge holds")
        self.assertEqual(cm.exception.bound, 5)
        self.assertLess(fake.t, 6)
        self.assertTrue(cm.exception.message().startswith("gatedloop: lock busy"))

    def test_with_no_declared_bound_the_default_bound_applies(self):
        self._hold()
        fake = FakeTime()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(gates._LockBusy) as cm:
                with gates._merge_lock(self.root, self._manifest(),
                                       clock=fake.clock, wall=fake.wall, sleep=fake.sleep):
                    self.fail("entered a lock another merge holds")
        self.assertEqual(cm.exception.bound, gates._lock_max_wait(self._manifest()))

    def test_lock_status_names_the_holder_of_a_held_merge_lock(self):
        (self.root / ".gates.yaml").write_text(BASE_MANIFEST)
        self._hold()
        r = subprocess.run(
            [sys.executable, str(GATES_SHIM), "lock", "status"],
            cwd=self.root, capture_output=True, text=True, env=clean_env(),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        line = next((x for x in r.stdout.splitlines() if x.startswith("merge:")), None)
        self.assertIsNotNone(line, f"no merge line in: {r.stdout!r}")
        self.assertIn(f"pid {os.getpid()}", line)


if __name__ == "__main__":
    unittest.main()
