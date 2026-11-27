"""`gates tests handoff <change> --dry-run` runs the handoff's refusals
against the preflight store and records nothing (openspec change
`plan-preflight`, design D9; task 1.2).

Each refusal's message and exit status match a real handoff's for the same
files (the holding area's own path aside). A dry run writes no ledger row and
no git object, skips only the tag comparison with the merge target (saying
so), needs no approval, and on success writes the per-task digests to the
store's `digests.json`.

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

from _preflight_fixture import CHANGE, MANIFEST, TASKS, PreflightRepo, git, write  # noqa: E402

WIDGET_TEST = "def test_widget():\n    assert False\n"
GADGET_REWRITE = "def test_gadget():\n    assert 1 == 1\n"


class DryRunTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.r = PreflightRepo(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def clean_set(self, where=None):
        self.r.hold("1.1", "tests/test_widget.py.authored", WIDGET_TEST, where)
        self.r.hold("1.2", "tests/test_gadget.py.authored", GADGET_REWRITE, where)
        self.r.hold("2.1", "NO-TESTS", "docs only\n", where)

    def dry(self, *extra):
        return self.r.gates("tests", "handoff", CHANGE, "--dry-run", *extra)

    def real(self, *extra):
        return self.r.gates("tests", "handoff", CHANGE, *extra)

    def mirror(self):
        """Copy the store's held set into the real holding area."""
        shutil.copytree(self.r.store / "authored", self.r.holding)

    def assert_same_refusal(self, *extra):
        d = self.dry(*extra)
        self.mirror()
        r = self.real(*extra)
        self.assertEqual(d.returncode, 1, d.stdout + d.stderr)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        store_rel = f".gatedloop/out/preflight/{CHANGE}/authored"
        real_rel = f".gatedloop/authored/{CHANGE}"
        self.assertEqual(d.stderr.replace(store_rel, real_rel), r.stderr)
        return d

    def test_a_clean_dry_run_on_an_unapproved_plan_records_nothing(self):
        self.clean_set()
        before = self.r.count_objects()
        out = self.dry()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Nothing was recorded", out.stdout)
        self.assertIn("not compared with the merge target", out.stdout)
        self.assertEqual(self.r.rows(), [])
        self.assertFalse(self.r.ledger.exists())
        self.assertEqual(self.r.count_objects(), before)
        self.assertTrue((self.r.store / "digests.json").is_file())
        self.assertFalse(self.r.holding.exists())

    def test_a_contradicting_characterization_is_refused_alike(self):
        self.clean_set()
        self.r.hold("1.1", "CHARACTERIZATION", "pins today\n")
        before = self.r.count_objects()
        d = self.dry()
        self.assertEqual(self.r.count_objects(), before)
        self.assertFalse((self.r.store / "digests.json").exists())
        self.assertFalse(self.r.ledger.exists())
        self.assertIn("cannot be declared CHARACTERIZATION", d.stderr)
        self.assert_same_refusal()

    def test_a_file_without_the_suffix_is_refused_alike(self):
        self.clean_set()
        self.r.hold("1.1", "tests/test_extra.py", "x\n")
        self.assert_same_refusal()

    def test_an_empty_area_is_refused_alike(self):
        (self.r.store / "authored").mkdir(parents=True)
        d = self.dry()
        self.r.holding.mkdir(parents=True)
        r = self.real()
        self.assertEqual((d.returncode, r.returncode), (1, 1))
        self.assertEqual(d.stderr.replace(f".gatedloop/out/preflight/{CHANGE}/authored",
                                          f".gatedloop/authored/{CHANGE}"), r.stderr)

    def test_a_task_holding_nothing_is_refused_alike_under_task(self):
        self.clean_set()
        self.assert_same_refusal("--task", "3.9")

    def test_a_declared_rewrite_not_held_is_refused_alike(self):
        self.r.hold("1.1", "tests/test_widget.py.authored", WIDGET_TEST)
        self.r.hold("2.1", "NO-TESTS", "docs only\n")
        d = self.assert_same_refusal()
        self.assertIn("rewrites: tests/test_gadget.py", d.stderr)

    def test_untagged_tasks_under_required_are_refused_alike(self):
        self._tmp.cleanup()
        self._tmp = tempfile.TemporaryDirectory()
        self.r = PreflightRepo(
            self._tmp.name,
            manifest=MANIFEST + "loop:\n  task-oracle: required\n",
            tasks=TASKS + "- [ ] 3.1 Untagged work\n")
        self.clean_set()
        self.r.hold("3.1", "NO-TESTS", "nothing\n")
        d = self.assert_same_refusal()
        self.assertIn("3.1", d.stderr)

    def test_a_clean_task_dry_run_writes_that_tasks_digest(self):
        self.clean_set()
        out = self.dry("--task", "1.1")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('"1.1"', (self.r.store / "digests.json").read_text())
        self.assertNotIn('"2.1"', (self.r.store / "digests.json").read_text())

    def test_a_retag_against_the_target_passes_the_dry_run_only(self):
        # The plan is merged on main; the plan branch retags 1.1.
        git(self.r.root, "checkout", "-q", "main")
        git(self.r.root, "merge", "-q", "--ff-only", f"plan/{CHANGE}")
        git(self.r.root, "checkout", "-q", "-b", f"plan/{CHANGE}-amend")
        self.r.edit(f"{self.r.rel_dir}/tasks.md", "[oracle: none]", "[oracle: unit]")
        git(self.r.root, "commit", "-qam", "retag 2.1")
        self.r.hold("1.1", "tests/test_widget.py.authored", WIDGET_TEST)
        self.r.hold("1.2", "tests/test_gadget.py.authored", GADGET_REWRITE)
        self.r.hold("2.1", "tests/test_docs.py.authored", WIDGET_TEST)
        d = self.dry()
        self.assertEqual(d.returncode, 0, d.stderr)
        self.mirror()
        r = self.real()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("task 2.1: its oracle tag here", r.stderr)

    def test_an_undeclared_overwrite_is_advised_without_hashing(self):
        self.clean_set()
        write(self.r.root, "src/widget_test_target.py", "x\n")
        git(self.r.root, "add", "-A")
        git(self.r.root, "commit", "-qm", "add file")
        self.r.hold("1.1", "src/widget_test_target.py.authored", WIDGET_TEST)
        before = self.r.count_objects()
        out = self.dry()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("advisory: task 1.1 overwrites existing src/widget_test_target.py",
                      out.stdout)
        self.assertEqual(self.r.count_objects(), before)


if __name__ == "__main__":
    unittest.main()
