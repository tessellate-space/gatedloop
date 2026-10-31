"""`gates hook git-cwd` expands home, reads a leading subshell, and denies
an unresolved `cd` (loop-hardening D8, #110).

The regressions: `cd ~/lane && git commit` resolved to `<cwd>/~/lane`;
`cd $HOME/lane` and `( cd /lane && git commit )` fell through to the
session's checkout, so the commit hook judged a repository the command never
ran in -- allowing or denying on evidence about the wrong tree. Now:

- `~`, `~/…`, `$HOME/…` and `${HOME}/…` expand from the hook's `HOME`;
- a `cd` inside a leading `(` governs only that subshell's commands;
- `~user`, any other variable and a command substitution stay unresolved,
  and `git-cwd` exits 3, which every guarding hook turns into a denial
  naming the `cd` and the `git -C` route.

The resolver is driven with hook JSON on stdin and a `HOME` of the test's
own; the denial through the real `hooks/gate-commit.sh`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_hook_git_cwd import REPO, _git_cwd

COMMIT_HOOK = REPO / "hooks" / "gate-commit.sh"


class HomeExpands(unittest.TestCase):
    def test_each_home_form_resolves_under_home(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as session:
            lane = Path(home) / "lane"
            lane.mkdir()
            for target, want in (("~/lane", lane), ("$HOME/lane", lane), ("${HOME}/lane", lane),
                                 ("~", Path(home)), ("$HOME", Path(home))):
                with self.subTest(target):
                    r = _git_cwd("git-commit",
                                 {"tool_input": {"command": f"cd {target} && git commit -m x"},
                                  "cwd": session},
                                 env_overrides={"HOME": home})
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertEqual(Path(r.stdout.strip()).resolve(), want.resolve())


class LeadingSubshell(unittest.TestCase):
    def test_a_cd_inside_the_subshell_governs_its_git_command(self):
        with tempfile.TemporaryDirectory() as lane, tempfile.TemporaryDirectory() as session:
            r = _git_cwd("git-commit",
                         {"tool_input": {"command": f"( cd {lane} && git commit -m x )"},
                          "cwd": session})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(lane).resolve())

    def test_a_cd_in_a_closed_subshell_does_not_govern_what_follows(self):
        with tempfile.TemporaryDirectory() as lane, tempfile.TemporaryDirectory() as session:
            r = _git_cwd("git-commit",
                         {"tool_input": {"command": f"(cd {lane} && ls); git commit -m x"},
                          "cwd": session})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(session).resolve())


class UnresolvedCdExits3(unittest.TestCase):
    def test_other_targets_exit_3_naming_the_cd(self):
        with tempfile.TemporaryDirectory() as session:
            for target in ("~bob/lane", '"$LANE"', "$(pwd)/lane", "`pwd`"):
                with self.subTest(target):
                    r = _git_cwd("git-commit",
                                 {"tool_input": {"command": f"cd {target} && git commit -m x"},
                                  "cwd": session})
                    self.assertEqual(r.returncode, 3, r.stdout)
                    self.assertEqual(r.stdout.strip(), "")
                    self.assertIn("could not resolve the directory of `cd", r.stderr)

    def test_git_dash_c_still_wins_over_an_unresolved_cd(self):
        with tempfile.TemporaryDirectory() as lane, tempfile.TemporaryDirectory() as session:
            r = _git_cwd("git-commit",
                         {"tool_input": {"command": f"cd $LANE && git -C {lane} commit -m x"},
                          "cwd": session})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()).resolve(), Path(lane).resolve())

    def test_the_commit_hook_denies_naming_the_unresolved_cd(self):
        with tempfile.TemporaryDirectory() as session:
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=session, check=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            env.pop("CLAUDE_PLUGIN_ROOT", None)
            env["CLAUDE_PROJECT_DIR"] = session
            env["CLAUDECODE"] = "1"
            payload = json.dumps({"tool_input": {"command": 'cd "$LANE" && git commit -m x'},
                                  "cwd": session})
            r = subprocess.run(["bash", str(COMMIT_HOOK)], input=payload, cwd=session, env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("$LANE", r.stderr)
            self.assertIn("git -C <dir>", r.stderr)
            self.assertIn("commit denied", r.stderr)


if __name__ == "__main__":
    unittest.main()
