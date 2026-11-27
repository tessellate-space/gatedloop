"""Plan-loop rows decide nothing (openspec change `plan-preflight`, design
D5 "Record-only"; task 6.3, a characterization).

Two repositories are built the same way, except that one's change ledger
holds `plan-round` and `plan-review` rows, committed on the plan branch and
merged with the plan. `gates handoff`, `check-implement`, `gates tests
handoff`, `gates tests show`, attempt counting, `gates usage record`,
`gates stats` and `gates merge` must give the same verdicts and output in
both (paths, hashes and timestamps normalized; every count exact).
Writing this test found that `gates stats` counted plan rows (a gate-table
line and unattributed active time); the shim now drops them before it
aggregates, as it drops usage rows. A ledger holding only
plan-loop rows still reads as having no handoff.

The older shim: the `v0.11.1` shim, run over a ledger holding plan-loop
rows, reads it without error. `gates stats` and `gates tests show` exit as
they do over the same ledger without them, and print no traceback: its
readers select rows by `gate` and skip the kinds they do not know, so an
adopter on 0.11.1 who pulls a plan merged by a 0.12.0 planner is unaffected.

Stdlib only, per `zero-dep-shim`. Real git repositories, the shim driven as
a subprocess. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from _preflight_fixture import CHANGE, REPO, PreflightRepo, env, git  # noqa: E402

LENS = "lens:gatedloop.implementability"


def normalize(text: str, root: Path) -> str:
    text = text.replace(str(root), "<root>").replace(str(root.resolve()), "<root>")
    text = re.sub(r"\b[0-9a-f]{7,64}\b", "<hex>", text)
    return re.sub(r"\d{4}-\d\d-\d\dT[\d:.+Z-]+", "<ts>", text)


class RecordOnlyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.with_rows = cls.build(tmp / "with", plan_rows=True)
        cls.without = cls.build(tmp / "without", plan_rows=False)
        cls.old_shim = cls.extract_old_shim(tmp / "old-plugin")
        assert ({x["gate"] for x in cls.with_rows.rows()}, {x["gate"] for x in cls.without.rows()}) \
            == ({"task-start", "plan-round", "plan-review"}, {"task-start"})

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @staticmethod
    def build(where: Path, plan_rows: bool) -> PreflightRepo:
        r = PreflightRepo(where)
        # Both ledgers exist before the loop: a merged plan's ledger already
        # holds a row (its approval, or as here a task-start row), so the baseline
        # is "the same ledger without plan rows", not "no ledger".
        assert r.gates("task", "start", "1.1", "--change", CHANGE).returncode == 0
        git(r.root, "add", r.ledger.relative_to(r.root).as_posix())
        git(r.root, "commit", "-q", "-m", f"plan: {CHANGE} (ledger)")
        if plan_rows:
            assert r.gates("plan", "classify", CHANGE, "--unavailable", "fixture").returncode == 0
            assert r.gates("plan", "round", CHANGE).returncode == 0
            assert r.gates("plan", "record", CHANGE, "--checker", LENS,
                           "--verdict", "clean").returncode == 0
            git(r.root, "add", r.ledger.relative_to(r.root).as_posix())
            git(r.root, "commit", "-q", "-m", f"plan: {CHANGE} (loop record)")
        git(r.root, "checkout", "-q", "main")
        git(r.root, "merge", "-q", "--squash", f"plan/{CHANGE}")
        git(r.root, "commit", "-q", "-m", f"plan: {CHANGE}")
        return r

    @staticmethod
    def extract_old_shim(where: Path) -> Path | None:
        arch = subprocess.run(["git", "archive", "v0.11.1", "bin", "rules"], cwd=REPO,
                              capture_output=True, env=env())
        if arch.returncode != 0:
            return None
        where.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(arch.stdout)) as t:
            t.extractall(where)
        return where / "bin" / "gates"

    def both(self, *args, branch: str = "main", setup=None) -> tuple:
        results = []
        for r in (self.with_rows, self.without):
            git(r.root, "checkout", "-q", branch)
            if setup:
                setup(r)
            out = r.gates(*args)
            results.append((out.returncode, normalize(out.stdout, r.root),
                            normalize(out.stderr, r.root)))
        return tuple(results)

    def assert_same(self, *args, **kw):
        a, b = self.both(*args, **kw)
        self.assertEqual(a, b, args)
        return a

    def test_handoff_and_check_implement(self):
        self.assert_same("handoff", CHANGE, "--json")
        self.assert_same("discipline", "check-implement", CHANGE)

    def test_only_plan_rows_reads_as_no_handoff(self):
        self.assert_same("tests", "show", CHANGE, "--json")
        code, out, _err = self.assert_same("tests", "show", CHANGE)
        self.assertIn("not authored", out)

    def test_stats_and_usage(self):
        self.assert_same("stats", "--change", CHANGE)
        self.assert_same("usage", "record", "--change", CHANGE, "--task", "1.1")

    def test_attempt_counting(self):
        self.assert_same("attempt", "notes", "1.1", "--change", CHANGE)

    def test_tests_handoff_on_the_change_branch(self):
        def hold(r):
            if git(r.root, "rev-parse", "--verify", "-q", CHANGE, check=False).returncode != 0:
                git(r.root, "branch", CHANGE, "main")
            git(r.root, "checkout", "-q", CHANGE)
            r.hold("1.1", "tests/test_widget.py.authored", "def test_w():\n    assert False\n", r.holding)
            r.hold("1.2", "tests/test_gadget.py.authored", "def test_gadget():\n    assert 2\n", r.holding)
            r.hold("2.1", "NO-TESTS", "docs\n", r.holding)
        self.assert_same("tests", "handoff", CHANGE, setup=hold, branch="main")

    def test_merge(self):
        self.assert_same("merge", CHANGE)

    def test_the_older_shim_reads_a_ledger_with_plan_rows(self):
        if self.old_shim is None:
            self.skipTest("no v0.11.1 tag in this clone")
        for args in (("stats", "--change", CHANGE), ("tests", "show", CHANGE)):
            outs = []
            for r in (self.with_rows, self.without):
                git(r.root, "checkout", "-q", "main")
                out = subprocess.run([sys.executable, str(self.old_shim), *args], cwd=r.root,
                                     capture_output=True, text=True, env=env(), timeout=120)
                self.assertNotIn("Traceback", out.stderr, args)
                outs.append(out.returncode)
            self.assertEqual(outs[0], outs[1], args)


if __name__ == "__main__":
    unittest.main()
