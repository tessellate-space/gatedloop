"""The matcher names the branch a switch-then-merge lands on (openspec change
`friction-fixes`, design D5; the loop-enforcement delta's "Only integration
merges are gated" requirement; issue #44).

`hooks/_gate_match.py`'s `git-merge` match reports `switch_branch`: the branch
named by the last `git checkout` / `git switch` that runs before the merge in
the same command. It is empty whenever that switch names no single branch (a
detached checkout, a path checkout, more than one positional, `-`), when it
runs in another directory than the merge (`git -C`, or a `cd` between the two),
and for an unparsable command, so the merge hook keeps such a merge gated.

The regressions guarded: a sync written as one command (`git checkout
my-change && git merge --ff-only origin/main`) refused because the hook cannot
see which branch the merge lands on, and a switch the hook misreads as a named
branch, letting an integration through.

Stdlib only, per `zero-dep-shim`. Pure-function tests against `match`, plus
the CLI's `eval` lines, which `hooks/gate-merge.sh` reads.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.util
import json
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MATCHER_PATH = REPO / "hooks" / "_gate_match.py"

_spec = importlib.util.spec_from_file_location("gate_match_switch", str(MATCHER_PATH))
gate_match = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate_match)

MERGE = "git merge --ff-only origin/main"


def _switch_branch(command):
    return gate_match.match("git-merge", command)["switch_branch"]


class TestANamedSwitch(unittest.TestCase):
    """Regression guarded: a sync into a change branch, written as one
    command, judged as if it might land on the target."""

    def test_each_shape_reports_its_branch(self):
        for switch, branch in (
            ("git checkout my-change", "my-change"),
            ("git switch my-change", "my-change"),
            ("git checkout -b x origin/main", "x"),
            ("git checkout -B x origin/main", "x"),
            ("git switch -c x", "x"),
            ("git switch -C x origin/main", "x"),
            ("git checkout -q my-change", "my-change"),
        ):
            with self.subTest(switch=switch):
                result = gate_match.match("git-merge", f"{switch} && {MERGE}")
                self.assertEqual(result["matched"], 1)
                self.assertEqual(result["switch_before"], "1")
                self.assertEqual(result["switch_branch"], branch)

    def test_the_last_switch_before_the_merge_wins(self):
        self.assertEqual(
            _switch_branch(f"git checkout main && git checkout my-change && {MERGE}"),
            "my-change")
        self.assertEqual(
            _switch_branch(f"git checkout my-change && git checkout main && {MERGE}"),
            "main")

    def test_a_switch_after_the_merge_is_not_counted(self):
        result = gate_match.match("git-merge", f"{MERGE} && git checkout other")
        self.assertEqual(result["switch_before"], "0")
        self.assertEqual(result["switch_branch"], "")


class TestASwitchThatNamesNoSingleBranch(unittest.TestCase):
    """Regression guarded: a detached, path or ambiguous checkout read as a
    named branch, so a merge onto the target slips through ungated."""

    def test_each_shape_reports_no_branch(self):
        for switch in (
            "git checkout --detach origin/main",
            "git switch --detach origin/main",
            "git checkout -- src/app.py",
            "git checkout my-change src/app.py",
            "git checkout main -- src/app.py",
            "git checkout -",
            "git switch -",
            "git checkout",
            "git -C ../lane checkout my-change",
            "git --git-dir=../lane/.git checkout my-change",
        ):
            with self.subTest(switch=switch):
                result = gate_match.match("git-merge", f"{switch} && git merge my-change")
                self.assertEqual(result["switch_before"], "1")
                self.assertEqual(result["switch_branch"], "")

    def test_an_unresolvable_switch_after_a_named_one_clears_it(self):
        self.assertEqual(
            _switch_branch(f"git checkout my-change && git checkout --detach HEAD && {MERGE}"),
            "")

    def test_a_directory_change_after_the_switch_clears_it(self):
        # The merge may then run in another checkout than the one switched.
        for between in ("cd ../primary", "pushd ../primary"):
            with self.subTest(between=between):
                self.assertEqual(
                    _switch_branch(f"git checkout my-change && {between} && git merge my-change"),
                    "")

    def test_a_directory_change_before_the_switch_keeps_it(self):
        self.assertEqual(_switch_branch(f"cd ../lane && git checkout my-change && {MERGE}"),
                         "my-change")

    def test_an_unparsable_command_reports_no_branch(self):
        result = gate_match.match("git-merge", "git checkout my-change && git merge 'oops")
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["switch_before"], "1")
        self.assertEqual(result["switch_branch"], "")


class TestNoSwitch(unittest.TestCase):
    def test_a_bare_merge_reports_no_branch(self):
        result = gate_match.match("git-merge", MERGE)
        self.assertEqual(result["switch_before"], "0")
        self.assertEqual(result["switch_branch"], "")


class TestTheCli(unittest.TestCase):
    """Regression guarded: the field computed but never emitted, so the hook
    always sees it empty."""

    def _eval_lines(self, command):
        payload = json.dumps({"tool_input": {"command": command}, "cwd": "/repo"})
        r = subprocess.run([sys.executable, str(MATCHER_PATH), "git-merge"],
                           input=payload, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = {}
        for line in r.stdout.splitlines():
            key, _, value = line.partition("=")
            parts = shlex.split(value)
            out[key] = parts[0] if parts else ""
        return out

    def test_the_switch_branch_is_emitted(self):
        out = self._eval_lines(f"git checkout my-change && {MERGE}")
        self.assertEqual(out.get("switch_branch"), "my-change")

    def test_an_empty_switch_branch_is_emitted_too(self):
        out = self._eval_lines(MERGE)
        self.assertIn("switch_branch", out)
        self.assertEqual(out["switch_branch"], "")


if __name__ == "__main__":
    unittest.main()
