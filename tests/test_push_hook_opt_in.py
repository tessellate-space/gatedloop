"""The push hook stays opt-in (change `git-layer-enforcement`, task 6.2;
requirement "The push hook is opt-in and a decline sticks").

`gates hook install` installs both git-layer hooks. A project that declined
the push hook must not get it back by re-running the install to refresh its
commit hook. The decline lives where adoption answers already live: the
`git-push-hook` item in `.gatedloop/adoption.json`.

The regressions caught here: `--commit-only` writing a `pre-push` hook or not
recording the decline; a plain re-install after a decline (recorded by the
upgrade walk or by `--commit-only`) silently installing the push hook, or
skipping it without saying how to add it; no way back in (`--push`, or the
item answered `adopted`); and `gates doctor` warning about a push hook the
project declined.

Black-box, the way gates-init and the upgrade walk call it: the shim runs as
a subprocess in throwaway git repositories, in an environment where nothing
but the hooks' recorded path resolves the shim.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import GATES_SHIM, default_hook, env_without_gates, init_repo  # noqa: E402

ITEM = "git-push-hook"


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=env_without_gates(), timeout=120)


def _decision(root):
    path = Path(root) / ".gatedloop" / "adoption.json"
    if not path.exists():
        return None
    return (json.loads(path.read_text())["decisions"].get(ITEM) or {}).get("decision")


def _installed(root):
    return {name for name in ("pre-commit", "pre-push") if default_hook(root, name).exists()}


class OptInTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        init_repo(self.root)

    def run_ok(self, *args):
        r = _gates(self.root, *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def decline(self, route):
        if route == "commit-only":
            self.run_ok("hook", "install", "--commit-only")
        else:
            self.run_ok("adoption", "record", ITEM, "declined")

    def test_commit_only_installs_the_commit_hook_and_records_the_decline(self):
        # Scenario "Installing the commit hook only".
        self.run_ok("hook", "install", "--commit-only")
        self.assertEqual(_installed(self.root), {"pre-commit"})
        self.assertEqual(_decision(self.root), "declined")

    def test_a_reinstall_after_a_decline_skips_the_push_hook_and_says_how_to_add_it(self):
        # Scenario "A re-install after a decline", for both ways a decline is
        # recorded: the upgrade walk's answer and an earlier `--commit-only`.
        for route in ("commit-only", "declined answer"):
            with self.subTest(declined_by=route), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                init_repo(self.root)
                self.decline(route)
                r = self.run_ok("hook", "install")
                self.assertEqual(_installed(self.root), {"pre-commit"})
                self.assertIn("--push", r.stdout + r.stderr)

    def test_opting_back_in(self):
        # Scenario "Opting back in": the flag, or the item answered `adopted`.
        for route in ("--push", "adopted answer"):
            with self.subTest(opt_in=route), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                init_repo(self.root)
                self.decline("commit-only")
                if route == "--push":
                    self.run_ok("hook", "install", "--push")
                else:
                    self.run_ok("adoption", "record", ITEM, "adopted")
                    self.run_ok("hook", "install")
                self.assertEqual(_installed(self.root), {"pre-commit", "pre-push"})
                self.assertEqual(_decision(self.root), "adopted")

    def test_the_two_flags_together_are_refused(self):
        # Fails if one silently won: the adopter asked for two opposite things.
        r = _gates(self.root, "hook", "install", "--commit-only", "--push")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(_installed(self.root), set())

    def test_the_doctor_respects_a_decline(self):
        # Scenario "The doctor respects a decline".
        self.decline("commit-only")
        r = self.run_ok("doctor")
        row = [line for line in r.stdout.splitlines() if "] git-push-hook:" in line]
        self.assertEqual(len(row), 1, r.stdout)
        self.assertIn("[ok  ]", row[0])
        self.assertIn("declined", row[0])


if __name__ == "__main__":
    unittest.main()
