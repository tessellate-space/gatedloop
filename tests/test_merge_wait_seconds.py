"""`concurrency.merge-wait-seconds` (design D3 of `merge-lane-friction`).

An optional positive integer bounding `gates merge`'s own waits on a
serialized gate's lock, defaulting to `concurrency.max-wait-seconds`. A
project whose full `ci` outlasts the general bound raises this one alone.
The regressions these catch: a bad value accepted silently (the merge then
waits on the default and nobody knows why), the merge's wait ignoring the
key, and an absent key no longer falling back to `max-wait-seconds`.

The waits run in process on an injected clock (`FakeTime`,
`gatedloop.test-quality` item 7), against a `ci` lock this test process
holds (`HeldLock`); the merge itself needs real git, as in the other merge
tests.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _merge_fixture import CHANGE, GATES_SHIM, FakeTime, HeldLock, MergeRepo, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_merge_wait", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\nconcurrency:\n  serialize:\n    - ci\n'


class MergeWaitValidationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q", "-b", "main")

    def tearDown(self):
        self._tmp.cleanup()

    def _errors_naming_the_key(self, value: str) -> list[str]:
        m = gates._mini_yaml(BASE + f"  merge-wait-seconds: {value}\n")
        m["__root__"] = str(self.root)
        return [e for e in gates._errors(m, self.root) if "merge-wait-seconds" in e]

    def test_a_positive_integer_is_valid(self):
        self.assertEqual(self._errors_naming_the_key("900"), [])

    def test_anything_but_a_positive_integer_is_refused(self):
        for value in ("0", "-5", "soon", "true"):
            with self.subTest(value=value):
                self.assertTrue(self._errors_naming_the_key(value),
                                f"merge-wait-seconds: {value} was accepted")


class MergeWaitBoundTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.held = None

    def tearDown(self):
        if self.held is not None:
            self.held.release()
        self._tmp.cleanup()

    def _merge_against_a_held_ci_lock(self, concurrency_extra: str) -> tuple[int, float, str]:
        repo = MergeRepo(self.tmp, manifest=BASE + concurrency_extra)
        repo.start_change(lane=True)
        repo.task_commit("one.txt", "1\n", "add the thing")
        repo.prove_head()
        self.held = HeldLock(repo.primary / ".git", "ci", os.getpid())
        m = gates._mini_yaml(repo.manifest)
        m["__root__"] = str(repo.primary)
        fake = FakeTime()
        out = io.StringIO()
        with mock.patch.dict(os.environ, repo.env(), clear=True), \
                mock.patch.object(gates.time, "monotonic", fake.clock), \
                mock.patch.object(gates.time, "time", fake.wall), \
                mock.patch.object(gates.time, "sleep", fake.sleep), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = gates.cmd_merge(m, repo.primary, argparse.Namespace(change=CHANGE))
        return rc, fake.t, out.getvalue()

    def test_the_merge_waits_for_merge_wait_seconds_not_max_wait_seconds(self):
        rc, waited, text = self._merge_against_a_held_ci_lock(
            "  max-wait-seconds: 300\n  merge-wait-seconds: 5\n")
        self.assertEqual(rc, gates.PRECONDITION_EXIT_CODE, text)
        self.assertGreaterEqual(waited, 5)
        self.assertLess(waited, 300, "the merge waited for max-wait-seconds")

    def test_without_merge_wait_seconds_the_merge_waits_for_max_wait_seconds(self):
        rc, waited, text = self._merge_against_a_held_ci_lock("  max-wait-seconds: 7\n")
        self.assertEqual(rc, gates.PRECONDITION_EXIT_CODE, text)
        self.assertGreaterEqual(waited, 7)
        self.assertLess(waited, 8)


if __name__ == "__main__":
    unittest.main()
