"""`gates marker publish <gate> [--sha]` (design D1 of `merge-pull-request`).

A gate marker lives under `.git/` on the machine that ran the gate; this
command turns one into a `gatedloop/<gate>` commit status the forge and a CI
job can read. The regressions: a status posted for a tree that never passed
(no marker, or only a surface-scoped `ci` run, which is not the whole
oracle), a status that does not carry the ledger-normalized tree a remote
check compares against, a skip verdict indistinguishable from a real pass,
and a CI-posted status that does not link back to its run.

The forge is the fake in `_forge_fixture` (no real API is ever called); the
repository is a real one with a bare remote, carried through the loop's own
gates by `_merge_fixture`, because the marker is keyed on what git says the
tree is.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

from _forge_fixture import Forge, NO_CI
from _merge_fixture import GATES_SHIM, MergeRepo, combined, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_marker_publish", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


SCOPED_SURFACE = (
    "surfaces:\n"
    "  - name: feat\n"
    '    match: "feature.txt"\n'
    "    gates:\n"
    '      ci: "true"\n'
)


class MarkerPublishTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _repo(self, manifest_extra: str = "", **prove) -> tuple:
        repo = MergeRepo(self.tmp, manifest_extra=manifest_extra)
        forge = Forge(self.tmp / "forge.json").install(repo.bin)
        repo.start_change(lane=False)
        repo.task_commit("feature.txt", "the thing\n", "add the thing")
        repo.prove_head(**prove)
        head = git(repo.primary, "rev-parse", "HEAD")
        return repo, forge, head

    def _normalized_head_tree(self, repo: MergeRepo) -> str:
        return gates._normalize_tree(repo.primary, git(repo.primary, "rev-parse", "HEAD^{tree}"))

    def test_a_green_marker_becomes_a_success_status_carrying_its_tree(self):
        # ci passes outright; live-check has no hot surface here, so its
        # marker is a skip verdict, and the status must say so.
        repo, forge, head = self._repo()
        tree = self._normalized_head_tree(repo)
        for gate, description in (
            ("ci", f"tree {tree}"),
            ("live-check", f"tree {tree} (skip: no hot surface)"),
        ):
            with self.subTest(gate):
                r = repo.gates("marker", "publish", gate, **NO_CI)

                self.assertEqual(r.returncode, 0, combined(r))
                status = forge.latest_status(head, f"gatedloop/{gate}")
                self.assertIsNotNone(status, f"no gatedloop/{gate} status on {head}")
                self.assertEqual(status["state"], "success")
                self.assertEqual(status["description"], description)
                self.assertIsNone(status["target_url"])

    def test_sha_names_the_commit_to_publish_on(self):
        repo, forge, head = self._repo()
        git(repo.primary, "commit", "-q", "--allow-empty", "-m", "later")

        r = repo.gates("marker", "publish", "ci", "--sha", head, **NO_CI)

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertIsNotNone(forge.latest_status(head, "gatedloop/ci"))

    def test_a_status_posted_in_ci_links_to_the_run(self):
        repo, forge, head = self._repo()

        r = repo.gates(
            "marker", "publish", "ci", GITHUB_RUN_ID="4242",
            GITHUB_SERVER_URL="https://github.example", GITHUB_REPOSITORY="acme/widget",
        )

        self.assertEqual(r.returncode, 0, combined(r))
        self.assertEqual(
            forge.latest_status(head, "gatedloop/ci")["target_url"],
            "https://github.example/acme/widget/actions/runs/4242",
        )

    def test_no_green_marker_for_the_tree_refuses_and_posts_nothing(self):
        cases = (
            # The head moved past the tree ci passed on.
            ("no marker", "", {}, True),
            # Only a surface-scoped ci ran on this tree -- the task commit's
            # own run, its staged diff hot on `feat` alone -- and no unscoped
            # ci after it: not the whole oracle.
            ("scoped only", SCOPED_SURFACE, {"ci": False}, False),
        )
        for name, extra, prove, move_head in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                self.tmp = Path(tmp)
                repo, forge, head = self._repo(manifest_extra=extra, **prove)
                if move_head:
                    (repo.primary / "feature.txt").write_text("changed\n")
                    git(repo.primary, "commit", "-q", "-am", "unproven")
                    head = git(repo.primary, "rev-parse", "HEAD")

                r = repo.gates("marker", "publish", "ci", **NO_CI)

                self.assertEqual(r.returncode, 1, combined(r))
                self.assertEqual(forge.statuses(head), [])


if __name__ == "__main__":
    unittest.main()
