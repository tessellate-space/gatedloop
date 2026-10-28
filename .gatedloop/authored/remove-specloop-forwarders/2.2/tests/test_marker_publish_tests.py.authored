"""`gates marker publish tests` and `check-remote tests`: the authored-test
lock as a commit status (change `test-lock-remote-check`, task 2.2, design
D4).

`tests` is a computed status: no gate run leaves a marker for it, the
commit's own tree is the evidence. The regressions: a success posted on a
head whose lock is broken, a failure that does not name the offending path
or that exits 0 (so a CI step stays green), a status that does not carry
the tree `check-remote` compares, a pull request carrying no change that
cannot get the status branch protection requires, and a missing forge CLI
read as "nothing to publish".

The forge is the fake in `_forge_fixture` (no real API is ever called); the
repository is a real one, because the lock is a comparison of git blobs.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

from _forge_fixture import NO_CI, Forge, path_without
from _lock_fixture import TEST_EDITED, TEST_REL, LockRepo, finished_lane
from _merge_fixture import GATES_SHIM, combined, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_marker_publish_tests", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CONTEXT = f"{gates.NAME}/tests"


class MarkerPublishTestsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _tree(self, repo, sha: str) -> str:
        return gates._normalize_tree(repo.primary, git(repo.primary, "rev-parse", f"{sha}^{{tree}}"))

    def _with_forge(self, repo):
        return Forge(self.tmp / "forge.json").install(repo.bin)

    def test_an_intact_lock_publishes_success_carrying_the_tree(self):
        repo = finished_lane(self.tmp, lane=False)
        forge = self._with_forge(repo)
        head = repo.head()

        r = repo.gates("marker", "publish", "tests", **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        for context in (CONTEXT,):
            with self.subTest(context):
                status = forge.latest_status(head, context)
                self.assertIsNotNone(status, f"no {context} status on {head}")
                self.assertEqual(status["state"], "success")
                self.assertTrue(status["description"].startswith(f"tree {self._tree(repo, head)}"),
                                status["description"])

    def test_no_gate_marker_is_needed(self):
        # Nothing ran a gate on this exact tree: the head moved past every
        # marker with a commit that left the lock intact.
        repo = finished_lane(self.tmp, lane=False)
        forge = self._with_forge(repo)
        repo.write("NOTES.txt", "later\n")
        git(repo.lane, "add", "-A")
        git(repo.lane, "commit", "-q", "-m", "unproven but lock-clean")
        head = repo.head()

        r = repo.gates("marker", "publish", "tests", "--sha", head, **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(forge.latest_status(head, CONTEXT)["state"], "success")

    def test_a_broken_lock_publishes_failure_naming_the_path_and_exits_non_zero(self):
        repo = finished_lane(self.tmp, lane=False)
        forge = self._with_forge(repo)
        head = repo.edit_past_the_hooks(TEST_REL, TEST_EDITED)

        r = repo.gates("marker", "publish", "tests", **NO_CI)

        self.assertNotEqual(r.returncode, 0, combined(r))
        self.assertIn(TEST_REL, combined(r))
        for context in (CONTEXT,):
            with self.subTest(context):
                status = forge.latest_status(head, context)
                self.assertIsNotNone(status, f"no {context} status on {head}")
                self.assertEqual(status["state"], "failure")
                self.assertIn(TEST_REL, status["description"])
                self.assertLessEqual(len(status["description"]), 140)

    def test_a_change_with_no_authored_tests_publishes_success_saying_so(self):
        repo = LockRepo(self.tmp)
        repo.start_change(lane=False)
        repo.write("feature.txt", "the thing\n")
        repo.gated_commit("add the thing", "1.1")
        forge = self._with_forge(repo)
        head = repo.head()

        r = repo.gates("marker", "publish", "tests", **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        status = forge.latest_status(head, CONTEXT)
        self.assertEqual(status["state"], "success")
        self.assertTrue(status["description"].startswith(f"tree {self._tree(repo, head)}"))
        self.assertIn("no authored tests", status["description"])

    def test_a_commit_carrying_no_change_publishes_success(self):
        # A planning or docs pull request: published from main's head.
        repo = LockRepo(self.tmp)
        forge = self._with_forge(repo)
        head = git(repo.primary, "rev-parse", "HEAD")

        r = repo.gates("marker", "publish", "tests", **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(forge.latest_status(head, CONTEXT)["state"], "success")

    def test_check_remote_verifies_a_published_success_and_refuses_a_failure(self):
        repo = finished_lane(self.tmp, lane=False)
        self._with_forge(repo)
        good = repo.head()
        repo.gates("marker", "publish", "tests", **NO_CI)
        bad = repo.edit_past_the_hooks(TEST_REL, TEST_EDITED)
        repo.gates("marker", "publish", "tests", **NO_CI)

        verified = repo.gates("marker", "check-remote", "tests", good, **NO_CI)
        refused = repo.gates("marker", "check-remote", "tests", bad, **NO_CI)

        self.assertEqual(verified.returncode, 0, combined(verified))
        self.assertEqual(refused.returncode, 1, combined(refused))
        self.assertIn("failure", combined(refused))

    def test_a_missing_forge_cli_refuses_naming_it(self):
        repo = finished_lane(self.tmp, lane=False)

        r = repo.gates("marker", "publish", "tests", PATH=path_without(self.tmp), **NO_CI)

        self.assertEqual(r.returncode, 1, combined(r))
        self.assertIn("gh", r.stderr)


if __name__ == "__main__":
    unittest.main()
