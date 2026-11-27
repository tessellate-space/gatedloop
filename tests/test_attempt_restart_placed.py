"""`gates attempt restart` treats a task's placed tests as clean (change
`unblock-authored-lock`, design D7; issue #56, "seen at the same time").

A restart demanded a clean tree and named the task's placed tests partial
work to discard, while the implementer may never discard a placed test and
cannot commit it without a `ci` marker. The regressions: a restart refused
when the only differences are the task's placed tests at exactly their
placed content and the removal of their holding files (in the worktree or
staged); and a restart accepted when a placed test was edited after
placement, or when anything else differs.

A batch placed together (change `lane-unstick`, design D2; issue #173):
the exemption covered only the restarted task's active placement, so a
sibling's placement counted as dirt, and the halted task's own placement,
voided by its halt, did too. The regressions: a restart of the halted task
or of its sibling refused while every placement is at its placed content;
the halted task unable to place again after its restart, or placed again
without a red run wanted; a sibling's edited placed test accepted, or
refused without naming its task; and a placement voided by a `test-defect`
counted as clean.

Real git in throwaway repositories: what is under test is how the
working tree compares with the task's last commit.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

CHANGE = "my-change"
LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"
HOLDING = f".gatedloop/authored/{CHANGE}"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "false"\n'
TEST_REL = "tests/test_calc.py"
TEST_V1 = "def test_add():\n    assert add(2, 3) == 5\n"
TEST_V2 = TEST_V1 + "\ndef test_add_negative():\n    assert add(-2, 1) == -1\n"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env())


def _restarts(root):
    p = root / LEDGER
    rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
    return [r for r in rows if r.get("gate") == "restart"]


def _placed_repo(tmp) -> Path:
    """Tasks 1.1 and 1.2 authored and committed; 1.2's tests placed and run
    red, the ledger committed on its own, the placement left in the tree."""
    root = Path(tmp)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    change_dir = root / "openspec" / "changes" / CHANGE
    change_dir.mkdir(parents=True)
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "checkout", "-q", "-b", CHANGE)
    for task, content in (("1.1", TEST_V1), ("1.2", TEST_V2)):
        held = root / HOLDING / task / "tests" / "test_other.py.authored"
        if task == "1.2":
            held = root / HOLDING / task / f"{TEST_REL}.authored"
        held.parent.mkdir(parents=True, exist_ok=True)
        held.write_text(content)
    assert _gates(root, "tests", "handoff", CHANGE).returncode == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "author tests")
    for args in (("task", "start", "1.2"), ("tests", "place", "1.2"),
                 ("run", "unit", "--task", "1.2", "--attempt", "1")):
        _gates(root, *args)
    assert (root / TEST_REL).read_text() == TEST_V2
    _git(root, "add", LEDGER)
    _git(root, "commit", "-q", "-m", "ledger")
    return root


class RestartAcceptsPlacedTestsTest(unittest.TestCase):
    def test_only_the_placed_tests_and_their_holding_removal_differ(self):
        for staged in (False, True):
            with self.subTest(staged=staged), tempfile.TemporaryDirectory() as tmp:
                root = _placed_repo(tmp)
                if staged:
                    _git(root, "add", "-A", TEST_REL, HOLDING)

                r = _gates(root, "attempt", "restart", "1.2")

                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(len(_restarts(root)), 1)

    def test_a_placed_test_edited_after_placement_is_refused_naming_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _placed_repo(tmp)
            (root / TEST_REL).write_text(TEST_V2 + "# edited\n")

            r = _gates(root, "attempt", "restart", "1.2")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(TEST_REL, r.stderr)
            self.assertIn(f"{TEST_REL} (task 1.2)", r.stderr)
            self.assertEqual(_restarts(root), [])

    def test_an_unrelated_dirty_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _placed_repo(tmp)
            (root / "notes.txt").write_text("partial work\n")

            r = _gates(root, "attempt", "restart", "1.2")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("notes.txt", r.stderr)
            self.assertEqual(_restarts(root), [])

    def test_another_tasks_holding_removal_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _placed_repo(tmp)
            other = root / HOLDING / "1.1" / "tests" / "test_other.py.authored"
            other.unlink()

            r = _gates(root, "attempt", "restart", "1.2")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertEqual(_restarts(root), [])


OTHER_REL = "tests/test_other.py"


def _rows(root):
    p = root / LEDGER
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _commit_ledger(root, subject):
    _git(root, "add", LEDGER)
    _git(root, "commit", "-q", "-m", subject)


def _batch_repo(tmp) -> Path:
    """`_placed_repo`, with task 1.1's tests placed and run red in the same
    tree before 1.2's, then a `stalled` halt at 1.2 committed on its own:
    both placements uncommitted at their placed content."""
    root = _placed_repo(tmp)
    for args in (("task", "start", "1.1"), ("tests", "place", "1.1"),
                 ("run", "unit", "--task", "1.1", "--attempt", "1")):
        _gates(root, *args)
    assert (root / OTHER_REL).read_text() == TEST_V1
    r = _gates(root, "halt", "record", "stalled", "--task", "1.2", "--detail", "budget used")
    assert r.returncode == 0, r.stdout + r.stderr
    _commit_ledger(root, "halt at 1.2")
    return root


class RestartAcceptsABatchTest(unittest.TestCase):
    def test_the_halted_task_then_its_sibling_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _batch_repo(tmp)

            halted = _gates(root, "attempt", "restart", "1.2")
            self.assertEqual(halted.returncode, 0, halted.stdout + halted.stderr)
            _commit_ledger(root, "restart 1.2")
            sibling = _gates(root, "attempt", "restart", "1.1")

            self.assertEqual(sibling.returncode, 0, sibling.stdout + sibling.stderr)
            self.assertEqual(sorted(r["task"] for r in _restarts(root)), ["1.1", "1.2"])

    def test_after_the_restart_the_halted_task_places_again_and_wants_a_red_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _batch_repo(tmp)
            r = _gates(root, "attempt", "restart", "1.2")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            _commit_ledger(root, "restart 1.2")

            _gates(root, "task", "start", "1.2")
            placed = _gates(root, "tests", "place", "1.2")

            self.assertEqual(placed.returncode, 0, placed.stdout + placed.stderr)
            placements = [x for x in _rows(root)
                          if x.get("gate") == "tests-placed" and x.get("task") == "1.2"]
            self.assertEqual(len(placements), 2)
            _git(root, "add", "-A")
            self.assertEqual(_gates(root, "tests", "check").returncode, 1,
                             "no red run since the new placement")
            _gates(root, "run", "unit", "--task", "1.2", "--attempt", "1")
            _git(root, "add", "-A")
            after = _gates(root, "tests", "check")
            self.assertEqual(after.returncode, 0, after.stdout + after.stderr)

    def test_a_siblings_edited_placed_test_is_refused_naming_it_and_its_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _batch_repo(tmp)
            (root / OTHER_REL).write_text(TEST_V1 + "# edited\n")

            r = _gates(root, "attempt", "restart", "1.2")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(f"{OTHER_REL} (task 1.1)", r.stderr)
            self.assertEqual(_restarts(root), [])

    def test_a_defect_voided_placement_still_in_the_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _batch_repo(tmp)
            d = _gates(root, "tests", "defect", "1.1", "--kind", "assertion",
                       "--detail", "asserts the wrong sum")
            self.assertEqual(d.returncode, 0, d.stdout + d.stderr)
            _commit_ledger(root, "defect at 1.1")

            r = _gates(root, "attempt", "restart", "1.2")

            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(OTHER_REL, r.stderr)
            self.assertEqual(_restarts(root), [])


if __name__ == "__main__":
    unittest.main()
