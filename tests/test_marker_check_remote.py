"""`gates marker check-remote <gate> <sha>` (design D1 of `merge-pull-request`).

The remote half of a published marker: it passes only when the LATEST
`gatedloop/<gate>` status on `<sha>` is a success and names `<sha>`'s own
ledger-normalized tree. The regressions: an older success hiding a newer
failure, a status copied from another commit (its tree is not this one's)
accepted, a mismatch reported without saying which trees disagree, and a
commit with no status at all treated as passing.

Fake forge from `_forge_fixture`; a real repository from `_merge_fixture`,
since the tree a sha names is git's answer.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

from _forge_fixture import Forge, NO_CI
from _merge_fixture import GATES_SHIM, MergeRepo, combined, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_check_remote", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

OTHER_TREE = "0123456789abcdef0123456789abcdef01234567"


class CheckRemoteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repo = MergeRepo(self.tmp)
        self.forge = Forge(self.tmp / "forge.json").install(self.repo.bin)
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        self.repo.prove_head()
        self.head = git(self.repo.primary, "rev-parse", "HEAD")
        self.tree = gates._normalize_tree(
            self.repo.primary, git(self.repo.primary, "rev-parse", "HEAD^{tree}"),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _check(self) -> "object":
        return self.repo.gates("marker", "check-remote", "ci", self.head, **NO_CI)

    def test_a_published_marker_verifies(self):
        published = self.repo.gates("marker", "publish", "ci", **NO_CI)
        self.assertEqual(published.returncode, 0, combined(published))

        r = self._check()

        self.assertEqual(r.returncode, 0, combined(r))

    def test_a_status_for_a_different_tree_fails_naming_both_trees(self):
        self.forge.add_status(self.head, "gatedloop/ci", "success", f"tree {OTHER_TREE}")

        r = self._check()

        self.assertNotEqual(r.returncode, 0, combined(r))
        self.assertIn(OTHER_TREE, combined(r))
        self.assertIn(self.tree, combined(r))

    def test_no_success_as_the_latest_status_fails(self):
        cases = (
            ("no status", []),
            ("a failing status", [("failure", f"tree {self.tree}")]),
            ("a failure after a success", [
                ("success", f"tree {self.tree}"), ("failure", f"tree {self.tree}"),
            ]),
        )
        for name, statuses in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as state_dir:
                self.forge = Forge(Path(state_dir) / "forge.json").install(self.repo.bin)
                for state, description in statuses:
                    self.forge.add_status(self.head, "gatedloop/ci", state, description)

                r = self._check()

                self.assertNotEqual(r.returncode, 0, combined(r))
                self.assertIn("gatedloop/ci", combined(r))


if __name__ == "__main__":
    unittest.main()
