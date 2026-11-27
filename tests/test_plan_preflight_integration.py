"""The plan loop end to end, from the shim's side (openspec change
`plan-preflight`; task 8.3, a characterization over tasks 1.1 to 7.1).

On a plan branch in a real repository, a full-tier loop runs the way the
propose path drives it: a fixture classifier raises a light floor to full
through one dimension, a round opens, both lenses are recorded, the test
author's work lands in the preflight store, the dry run is recorded once
refused and once clean, the authored-set review is recorded, an amendment to
one task line opens a second round that re-authors only that task, and the
plan is committed through both commit hooks with its ledger. The store is
then saved, pushed with the plan branch to a bare remote, cloned and
restored, and the clone's brief keeps the same tasks.

Regressions guarded: a step of the loop refusing what the next one needs, a
round re-authoring tasks it should keep, the real holding area created by a
preflight, the store reaching git or a plan commit, a restore that does not
reproduce the kept set, and a green loop not reported green.

This is the slowest layer on purpose: what it guards lives at the seams
between the shim's commands, both commit hooks, git and a remote, which no
per-command test observes.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim and both
hooks driven as subprocesses, `CLAUDECODE` set explicitly. Run with:
python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import (CHANGE, MANIFEST, PreflightRepo, git,  # noqa: E402
                                git_hook, tool_denied, tool_hook, write)

LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"
SNAPSHOT = f"gatedloop/preflight/{CHANGE}"
LENSES = ("lens:gatedloop.implementability", "lens:gatedloop.zero-decision")

# Answers the dimensions with a light overall tier, and one dimension over
# its threshold: the combined verdict raises the light floor to full.
CLASSIFIER = """\
import json, sys
sys.stdin.buffer.read()
print(json.dumps({"tier": "light", "confidence": 0.6, "reason": "fixture",
                  "evidence": [{"dimension": "persisted-data", "value": 0.9, "confidence": 0.8},
                               {"dimension": "security-path", "value": 0.1, "confidence": 0.9}]}))
"""

WIDGET_TEST = "def test_widget():\n    assert False\n"
GADGET_TEST = "def test_gadget():\n    assert 2\n"


def section(stdout: str, label: str) -> str:
    for line in stdout.splitlines():
        if line.startswith(label):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"no {label!r} line in:\n{stdout}")


class PlanLoopEndToEndTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        script = write(self.tmp, "fixture/classify.py", CLASSIFIER)
        cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
        manifest = MANIFEST + "loop:\n  plan-preflight:\n    mode: run\n    classifier: " \
            + json.dumps(cmd) + "\n"
        self.r = PreflightRepo(self.tmp / "work", manifest=manifest)
        self.reports = self.tmp / "reports"

    def tearDown(self):
        self._tmp.cleanup()

    def ok(self, *args, cwd=None):
        out = self.r.gates(*args, cwd=cwd)
        self.assertEqual(out.returncode, 0, f"gates {' '.join(args)}\n{out.stdout}{out.stderr}")
        return out

    def record(self, checker: str, verdict: str = "clean"):
        report = write(self.reports, f"{checker.replace(':', '_')}.md", f"{checker}: {verdict}\n")
        return self.ok("plan", "record", CHANGE, "--checker", checker, "--verdict", verdict,
                       "--report", str(report))

    def lenses(self):
        listed = [ln.strip()[2:] for ln in self.ok("plan", "brief", CHANGE).stdout.splitlines()
                  if ln.startswith("  - ")]
        self.assertEqual(["lens:" + x for x in listed], list(LENSES))
        for lens in LENSES:
            self.ok("plan", "brief", CHANGE, "--lens", lens[len("lens:"):])
            self.record(lens)

    def authored_stage(self):
        self.record("test-author")
        self.ok("plan", "record", CHANGE, "--checker", "dry-run")
        self.ok("tests", "show", CHANGE, "--preflight", "--diff")
        self.record("authored-review")

    def test_a_full_loop_amended_once_then_saved_committed_pushed_and_restored(self):
        r = self.r
        tier = json.loads(self.ok("plan", "tier", CHANGE, "--json").stdout)
        self.assertEqual((tier["floor"], tier["classifier"]["provider"],
                          tier["classifier"]["raised_by"], tier["tier"]),
                         ("light", "external", "persisted-data", "full"))

        # Round 1: both lenses, then the author; the first dry run is refused.
        self.ok("plan", "round", CHANGE)
        self.lenses()
        brief = self.ok("tests", "brief", CHANGE, "--preflight").stdout
        self.assertEqual(section(brief, "Stale"), "1.1, 1.2, 2.1")
        r.hold("1.1", "tests/test_widget.py.authored", WIDGET_TEST)
        refused = r.gates("plan", "record", CHANGE, "--checker", "dry-run")
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        r.hold("1.2", "tests/test_gadget.py.authored", GADGET_TEST)
        r.hold("2.1", "NO-TESTS", "docs only\n")
        self.authored_stage()
        self.assertEqual(json.loads(self.ok("plan", "status", CHANGE, "--json").stdout)["state"],
                         "green")

        # An amendment to one task line: round 2 re-authors only that task.
        r.edit(f"{r.rel_dir}/tasks.md", "Document the widget", "Document the widget's limits")
        self.assertTrue(json.loads(self.ok("plan", "status", CHANGE, "--json").stdout)
                        ["green_round_moved"])
        self.ok("plan", "round", CHANGE)
        self.lenses()
        brief = self.ok("tests", "brief", CHANGE, "--preflight").stdout
        self.assertEqual((section(brief, "Stale"), section(brief, "Kept")), ("2.1", "1.1, 1.2"))
        r.hold("2.1", "NO-TESTS", "docs only, limits included\n")
        self.authored_stage()
        diff = self.ok("tests", "show", CHANGE, "--preflight", "--diff").stdout
        self.assertIn("tests/test_gadget.py", diff)
        self.ok("plan", "status", CHANGE, "--markdown")

        # Save the store; commit the plan with its ledger through both hooks.
        self.ok("plan", "save", CHANGE)
        git(r.root, "add", r.rel_dir, LEDGER)
        tool = tool_hook(r.root)
        self.assertFalse(tool_denied(tool), tool.stdout + tool.stderr)
        hook = git_hook(r.root)
        self.assertEqual(hook.returncode, 0, hook.stdout + hook.stderr)
        git(r.root, "commit", "-m", f"propose: {CHANGE}")
        committed = git(r.root, "log", "--name-only", "--format=", f"main..plan/{CHANGE}").stdout
        paths = {p for p in committed.splitlines() if p}
        self.assertTrue(paths and all(p.startswith(r.rel_dir + "/") or p == LEDGER for p in paths),
                        paths)
        self.assertEqual(r.status(), "")
        self.assertEqual(git(r.root, "check-ignore", "-q", str(r.store), check=False).returncode, 0)

        # Push both branches, clone, restore: the clone keeps the same tasks.
        kept_here = section(self.ok("tests", "brief", CHANGE, "--preflight").stdout, "Kept")
        bare = self.tmp / "remote.git"
        git(self.tmp, "init", "--bare", str(bare))
        git(r.root, "remote", "add", "origin", str(bare))
        git(r.root, "push", "origin", f"plan/{CHANGE}", SNAPSHOT)
        clone = self.tmp / "clone"
        git(self.tmp, "clone", "-b", f"plan/{CHANGE}", str(bare), str(clone))
        self.ok("plan", "restore", CHANGE, cwd=clone)
        brief = self.ok("tests", "brief", CHANGE, "--preflight", cwd=clone).stdout
        self.assertEqual(section(brief, "Kept"), kept_here)
        self.assertEqual(kept_here, "1.1, 1.2, 2.1")
        self.assertEqual(json.loads(self.ok("plan", "status", CHANGE, "--json", cwd=clone).stdout)
                         ["state"], "green")

        for root in (r.root, clone):
            self.assertFalse((root / ".gatedloop" / "authored").exists(), root)


if __name__ == "__main__":
    unittest.main()
