"""The forge CLI as a prerequisite (design D1 of `merge-pull-request`).

`marker publish` and `marker check-remote` reach the forge only through `gh`,
an optional dependency. The regressions: either command treating a missing
or unauthenticated `gh` as "nothing to publish" or "status absent" instead of
failing loud and naming it, and `gates doctor` either staying silent about
`gh` where pull-request mode depends on it, or nagging a local-squash-merge
project that never needs it.

"Not installed" has to be real: a developer machine usually has a `gh`, and a
PATH prefix cannot hide it, so those cases run on a PATH holding only `git`
(`_forge_fixture.path_without`).

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import re
import tempfile
import unittest
from pathlib import Path

from _forge_fixture import Forge, NO_CI, PR_MODE, path_without
from _merge_fixture import MergeRepo, combined, git

GH_ROW = re.compile(r"\[(ok  |WARN)\] gh:")


class ForgeCommandsNeedGhTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.repo = MergeRepo(self.tmp)
        self.forge = Forge(self.tmp / "forge.json").install(self.repo.bin)
        self.repo.start_change(lane=False)
        self.repo.task_commit("feature.txt", "the thing\n", "add the thing")
        self.repo.prove_head()
        self.head = git(self.repo.primary, "rev-parse", "HEAD")

    def tearDown(self):
        self._tmp.cleanup()

    def test_both_commands_fail_loud_naming_gh(self):
        commands = (
            ("publish", ("marker", "publish", "ci")),
            ("check-remote", ("marker", "check-remote", "ci", self.head)),
        )
        for prerequisite in ("not installed", "not authenticated"):
            for name, argv in commands:
                with self.subTest(prerequisite=prerequisite, command=name):
                    env = dict(NO_CI)
                    if prerequisite == "not installed":
                        env["PATH"] = path_without(self.tmp)
                    else:
                        self.forge.set_unauthenticated()

                    r = self.repo.gates(*argv, **env)

                    self.assertEqual(r.returncode, 1, combined(r))
                    self.assertIn("gh", combined(r))
                    word = "install" if prerequisite == "not installed" else "auth"
                    self.assertIn(word, combined(r).lower())
        self.assertEqual(self.forge.statuses(self.head), [])


class DoctorGhRowTest(unittest.TestCase):
    def test_gh_is_reported_only_where_pull_request_mode_is_declared(self):
        cases = (
            ("pull-request, gh missing", PR_MODE, "missing", "WARN"),
            ("pull-request, gh unauthenticated", PR_MODE, "unauth", "WARN"),
            ("pull-request, gh ready", PR_MODE, "ready", "ok  "),
            ("local-squash-merge, gh missing", "", "missing", None),
        )
        for name, extra, gh, expected in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                repo = MergeRepo(tmp, manifest_extra=extra)
                env = {}
                if gh == "missing":
                    env["PATH"] = path_without(tmp)
                else:
                    forge = Forge(tmp / "forge.json").install(repo.bin)
                    if gh == "unauth":
                        forge.set_unauthenticated()

                r = repo.gates("doctor", **env)

                self.assertEqual(r.returncode, 0, combined(r))
                rows = GH_ROW.findall(r.stdout)
                if expected is None:
                    self.assertEqual(rows, [], r.stdout)
                else:
                    self.assertEqual(rows, [expected], r.stdout)


if __name__ == "__main__":
    unittest.main()
