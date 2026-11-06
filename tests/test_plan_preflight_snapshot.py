"""`gates plan save` and `gates plan restore` (openspec change
`plan-preflight`, design D7; task 1.4).

The preflight store's durable copy is the branch `gatedloop/preflight/
<change>`. `save` snapshots the store into a new commit on it with git
plumbing only, so the working tree, the index and `HEAD` never move; each
save parents on the last. `restore` rebuilds the store from a snapshot (the
local branch, else `origin/…`), refusing to overwrite a store that differs
unless given `--force`, and prints the kept tasks from the restored digests.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, PreflightRepo, git  # noqa: E402

BRANCH = f"gatedloop/preflight/{CHANGE}"
REF = f"refs/heads/{BRANCH}"


def kept_line(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("Kept"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(stdout)


class PlanSnapshotTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.r = PreflightRepo(self.tmp / "work")

    def tearDown(self):
        self._tmp.cleanup()

    def author_round(self):
        """A preflight round: the brief, held files for every task, a clean
        dry run that writes `digests.json`."""
        self.assertEqual(self.r.gates("tests", "brief", CHANGE, "--preflight").returncode, 0)
        self.r.hold("1.1", "tests/test_widget.py.authored", "def test_widget():\n    assert False\n")
        self.r.hold("1.2", "tests/test_gadget.py.authored", "def test_gadget():\n    assert 2\n")
        self.r.hold("2.1", "NO-TESTS", "docs only\n")
        dry = self.r.gates("tests", "handoff", CHANGE, "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)

    def tip(self, root=None) -> str:
        return git(root or self.r.root, "rev-parse", "--verify", "-q", REF, check=False).stdout.strip()

    def test_save_moves_only_the_branch(self):
        self.author_round()
        head = git(self.r.root, "rev-parse", "HEAD").stdout
        index = git(self.r.root, "ls-files", "-s").stdout
        status = self.r.status()
        out = self.r.gates("plan", "save", CHANGE)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        tip = self.tip()
        self.assertTrue(tip)
        self.assertIn(tip, out.stdout)
        self.assertIn(f"git push origin {BRANCH}", out.stdout)
        self.assertEqual(git(self.r.root, "rev-parse", "HEAD").stdout, head)
        self.assertEqual(git(self.r.root, "ls-files", "-s").stdout, index)
        self.assertEqual(self.r.status(), status)
        self.assertEqual(git(self.r.root, "branch", "--show-current").stdout.strip(), f"plan/{CHANGE}")
        files = git(self.r.root, "ls-tree", "-r", "--name-only", tip).stdout.split()
        self.assertIn("authored/1.1/tests/test_widget.py.authored", files)
        self.assertIn("digests.json", files)
        msg = git(self.r.root, "log", "-1", "--format=%B", tip).stdout
        self.assertIn(CHANGE, msg)
        self.assertRegex(msg, r"\bloop 1, round 0\b")
        self.assertRegex(msg, r"(?m)^plan_sha: [0-9a-f]{64}$")
        self.assertRegex(msg, r"(?m)^tasks_sha: [0-9a-f]{64}$")

    def test_second_save_parents_on_the_first(self):
        self.author_round()
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 0)
        first = self.tip()
        self.r.hold("1.1", "tests/test_widget.py.authored", "def test_widget():\n    assert None\n")
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 0)
        second = self.tip()
        self.assertNotEqual(first, second)
        self.assertEqual(git(self.r.root, "rev-parse", f"{second}^").stdout.strip(), first)

    def test_save_refuses_an_absent_or_empty_store(self):
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 1)
        self.assertEqual(self.tip(), "")
        self.assertEqual(self.r.gates("tests", "brief", CHANGE, "--preflight").returncode, 0)
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 1)
        self.assertEqual(self.tip(), "")

    def test_push_clone_restore_keeps_the_same_tasks(self):
        self.author_round()
        kept_here = kept_line(self.r.gates("tests", "brief", CHANGE, "--preflight").stdout)
        self.assertEqual(kept_here, "1.1, 1.2, 2.1")
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 0)
        bare = self.tmp / "remote.git"
        git(self.tmp, "init", "--bare", str(bare))
        git(self.r.root, "remote", "add", "origin", str(bare))
        git(self.r.root, "push", "origin", f"plan/{CHANGE}", BRANCH)
        clone = self.tmp / "clone"
        git(self.tmp, "clone", "-b", f"plan/{CHANGE}", str(bare), str(clone))
        out = self.r.gates("plan", "restore", CHANGE, cwd=clone)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("1.1, 1.2, 2.1", out.stdout)
        store = clone / ".gatedloop" / "out" / "preflight" / CHANGE
        self.assertEqual((store / "authored" / "1.1" / "tests" / "test_widget.py.authored").read_text(),
                         "def test_widget():\n    assert False\n")
        self.assertEqual(git(clone, "status", "--porcelain", "--untracked-files=all").stdout, "")
        brief = self.r.gates("tests", "brief", CHANGE, "--preflight", cwd=clone)
        self.assertEqual(kept_line(brief.stdout), kept_here)

    def test_restore_from_an_explicit_ref(self):
        self.author_round()
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 0)
        first = self.tip()
        self.r.hold("1.1", "tests/test_widget.py.authored", "changed\n")
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 0)
        shutil.rmtree(self.r.store)
        out = self.r.gates("plan", "restore", CHANGE, "--from", first)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("assert False",
                      (self.r.store / "authored" / "1.1" / "tests" / "test_widget.py.authored").read_text())

    def test_restore_refuses_a_differing_store_and_force_overrides(self):
        self.author_round()
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 0)
        held = self.r.store / "authored" / "1.1" / "tests" / "test_widget.py.authored"
        held.write_text("edited after the save\n")
        extra = self.r.hold("1.2", "tests/test_extra.py.authored", "x\n")
        out = self.r.gates("plan", "restore", CHANGE)
        self.assertEqual(out.returncode, 1)
        self.assertIn("authored/1.1/tests/test_widget.py.authored", out.stderr)
        self.assertIn("authored/1.2/tests/test_extra.py.authored", out.stderr)
        self.assertIn("--force", out.stderr)
        self.assertEqual(held.read_text(), "edited after the save\n")
        out = self.r.gates("plan", "restore", CHANGE, "--force")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(held.read_text(), "def test_widget():\n    assert False\n")
        self.assertFalse(extra.exists())

    def test_restore_with_no_snapshot_refuses(self):
        out = self.r.gates("plan", "restore", CHANGE)
        self.assertEqual(out.returncode, 1)
        self.assertIn(BRANCH, out.stderr)

    def test_pre_push_check_passes_the_snapshot_branch(self):
        self.author_round()
        self.assertEqual(self.r.gates("plan", "save", CHANGE).returncode, 0)
        out = self.r.gates("discipline", "check-push", self.tip(), "--remote-ref", REF)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
