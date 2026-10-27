"""The authored-test lock: `gates tests handoff|place|check|defect|show`
and the ledger fields behind them (split-test-author design D3, D4, D5).

Stdlib only, per `zero-dep-shim`. Builds throwaway git repos under a temp
directory and drives the shim as a subprocess (black-box, matching how the
loop and the commit hooks call it), then reads the durable ledger back.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_authored_tests", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "demo-change"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "false"\n'


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    )


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _rows(root, change=CHANGE):
    p = root / ".gatedloop" / "runs" / f"{change}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def _repo(tmp, branch=CHANGE):
    root = Path(tmp)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    (root / "src").mkdir()
    (root / "src" / "calc.py").write_text("def add(a, b):\n    raise NotImplementedError\n")
    if branch != "main":
        # hook-correctness D6: a branch is a change only when its change directory exists.
        change_dir = root / "openspec" / "changes" / branch
        change_dir.mkdir(parents=True)
        (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    if branch != "main":
        _git(root, "checkout", "-b", branch)
    return root


def _holding(root, task, change=CHANGE):
    return root / ".gatedloop" / "authored" / change / task


def _hold(root, task, path, content, change=CHANGE):
    """Write one authored test into the holding area, as the author does."""
    p = _holding(root, task, change) / f"{path}.authored"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _no_tests(root, task, reason, change=CHANGE):
    p = _holding(root, task, change) / "NO-TESTS"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(reason + "\n")


def _blob(root, content):
    return subprocess.run(
        ["git", "hash-object", "--stdin"], cwd=root, input=content,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _handoffs(root):
    return [r for r in _rows(root) if r["gate"] == "tests-handoff"]


TEST_V1 = "def test_add():\n    assert add(2, 3) == 5\n"
TEST_V2 = TEST_V1 + "\ndef test_add_negative():\n    assert add(-2, 1) == -1\n"


class TestHandoff(unittest.TestCase):
    """Regressions guarded: a handoff that records the wrong blobs, loses a
    behaviour-free reason, or records something the lock can't enforce (an
    empty set, a task that is both tested and behaviour-free, a file a test
    runner would discover)."""

    def test_records_each_tasks_blobs_bases_and_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "test_old.py").write_text("OLD\n")
            _hold(root, "1.1", "tests/test_calc.py", TEST_V1)
            _hold(root, "1.1", "tests/test_old.py", "NEW\n")
            _no_tests(root, "1.2", "docs only")

            result = _run_gates(root, "tests", "handoff", CHANGE)

            self.assertEqual(result.returncode, 0, result.stderr)
            (row,) = _handoffs(root)
            self.assertEqual(row["author"], "separate")
            self.assertEqual(row["tests"], {"1.1": {
                "tests/test_calc.py": _blob(root, TEST_V1),
                "tests/test_old.py": _blob(root, "NEW\n"),
            }})
            self.assertEqual(row["base"], {
                "tests/test_calc.py": None,
                "tests/test_old.py": _blob(root, "OLD\n"),
            })
            self.assertEqual(row["no_behaviour"], {"1.2": "docs only"})

    def test_inline_flag_records_inline_author(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _hold(root, "1.1", "tests/test_calc.py", TEST_V1)
            result = _run_gates(root, "tests", "handoff", CHANGE, "--inline")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(_handoffs(root)[0]["author"], "inline")

    def test_task_flag_records_only_that_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            _hold(root, "1.1", "tests/test_calc.py", TEST_V1)
            _no_tests(root, "1.2", "docs only")
            self.assertEqual(_run_gates(root, "tests", "handoff", CHANGE).returncode, 0)
            _hold(root, "1.1", "tests/test_calc.py", TEST_V2)

            result = _run_gates(root, "tests", "handoff", CHANGE, "--task", "1.1")

            self.assertEqual(result.returncode, 0, result.stderr)
            row = _handoffs(root)[-1]
            self.assertEqual(row["task"], "1.1")
            self.assertEqual(row["tests"], {"1.1": {"tests/test_calc.py": _blob(root, TEST_V2)}})
            self.assertEqual(row["no_behaviour"], {})

    def test_refusals_write_nothing(self):
        cases = {
            "empty holding area": lambda root: None,
            "tests and NO-TESTS in one task": lambda root: (
                _hold(root, "1.1", "tests/test_calc.py", TEST_V1),
                _no_tests(root, "1.1", "docs only")),
            "a file a runner could discover": lambda root: (
                _hold(root, "1.1", "tests/test_calc.py", TEST_V1),
                (_holding(root, "1.1") / "tests" / "test_raw.py").write_text(TEST_V1)),
        }
        for name, arrange in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp)
                arrange(root)
                result = _run_gates(root, "tests", "handoff", CHANGE)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertTrue(result.stderr.strip())
                self.assertEqual(_handoffs(root), [])


def _placed(root):
    return [r for r in _rows(root) if r["gate"] == "tests-placed"]


def _authored_repo(tmp):
    """A change branch whose author held 1.1 and 1.2 extending one test file,
    and 1.3 as behaviour-free, all handed off."""
    root = _repo(tmp)
    _hold(root, "1.1", "tests/test_calc.py", TEST_V1)
    _hold(root, "1.2", "tests/test_calc.py", TEST_V2)
    _no_tests(root, "1.3", "docs only")
    result = _run_gates(root, "tests", "handoff", CHANGE)
    assert result.returncode == 0, result.stderr
    return root


class TestPlace(unittest.TestCase):
    """Regressions guarded: placement that leaves the holding copy behind,
    overwrites a test file someone changed since authoring, or refuses the
    legitimate case of a later task extending an earlier task's file."""

    def test_moves_the_tasks_tests_onto_their_real_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)

            result = _run_gates(root, "tests", "place", "1.1")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "tests" / "test_calc.py").read_text(), TEST_V1)
            self.assertFalse(_holding(root, "1.1").exists())
            self.assertTrue(_holding(root, "1.2").exists())
            (row,) = _placed(root)
            self.assertEqual(row["task"], "1.1")
            self.assertEqual(row["tests"], {"1.1": {"tests/test_calc.py": _blob(root, TEST_V1)}})

    def test_later_task_replaces_an_earlier_tasks_placed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            self.assertEqual(_run_gates(root, "tests", "place", "1.1").returncode, 0)

            result = _run_gates(root, "tests", "place", "1.2")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "tests" / "test_calc.py").read_text(), TEST_V2)

    def test_refuses_a_real_path_changed_since_authoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            self.assertEqual(_run_gates(root, "tests", "place", "1.1").returncode, 0)
            (root / "tests" / "test_calc.py").write_text(TEST_V1 + "# tweaked\n")

            result = _run_gates(root, "tests", "place", "1.2")

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("tests/test_calc.py", result.stderr)
            self.assertIn("# tweaked", (root / "tests" / "test_calc.py").read_text())
            self.assertTrue(_holding(root, "1.2").exists())
            self.assertEqual([r["task"] for r in _placed(root)], ["1.1"])

    def test_behaviour_free_task_places_nothing_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)

            result = _run_gates(root, "tests", "place", "1.3")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("docs only", result.stdout)
            self.assertFalse((root / "tests" / "test_calc.py").exists())
            self.assertFalse(_holding(root, "1.3").exists())

    def test_refuses_a_task_the_handoff_does_not_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            result = _run_gates(root, "tests", "place", "9.9")
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("9.9", result.stderr)
            self.assertEqual(_placed(root), [])


PRECONDITION_MANIFEST = (
    'gatesVersion: 1\ngates:\n  ci: "true"\n'
    '  unit:\n    run: "false"\n    requires: "false"\n'
)


def _check(root, *extra):
    return _run_gates(root, "tests", "check", *extra)


def _stage(root):
    _git(root, "add", "-A")


def _commit_authoring(root):
    _stage(root)
    _git(root, "commit", "-m", f"author tests: {CHANGE}")


def _place_red_and_stage(root, task):
    """The implementer's legitimate sequence up to the task gate."""
    _git(root, "commit", "--allow-empty", "-m", "boundary")
    assert _run_gates(root, "task", "start", task).returncode == 0
    placed = _run_gates(root, "tests", "place", task)
    assert placed.returncode == 0, placed.stderr
    red = _run_gates(root, "run", "unit", "--task", task)
    assert red.returncode not in (0, 75), red.stderr
    _stage(root)


class TestCheck(unittest.TestCase):
    """Regressions guarded, one per condition of design D4: an implementer
    committing an edited placed test, an edited held test, or a task whose
    placed tests never ran red (or only 'failed' on a missing environment)."""

    def test_passes_without_a_change_or_without_a_handoff(self):
        for branch in ("main", CHANGE):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp, branch=branch)
                (root / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
                _stage(root)
                result = _check(root)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_authoring_commit_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            _stage(root)
            result = _check(root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_placed_tests_after_a_red_run_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            _commit_authoring(root)
            _place_red_and_stage(root, "1.1")
            result = _check(root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_edited_placed_test_is_refused_naming_the_path_and_the_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            _commit_authoring(root)
            _place_red_and_stage(root, "1.1")
            (root / "tests" / "test_calc.py").write_text(TEST_V1.replace("5", "6"))
            _stage(root)

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("tests/test_calc.py", result.stderr)
            self.assertIn("gates tests defect", result.stderr)

    def test_edited_held_test_is_refused_until_rehandoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            _commit_authoring(root)
            _place_red_and_stage(root, "1.1")
            _hold(root, "1.2", "tests/test_calc.py", TEST_V2 + "# edited\n")
            _stage(root)

            refused = _check(root)
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertIn("1.2", refused.stderr)

            self.assertEqual(_run_gates(root, "tests", "handoff", CHANGE, "--task", "1.2").returncode, 0)
            accepted = _check(root)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_placement_without_a_red_run_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            _commit_authoring(root)
            _run_gates(root, "task", "start", "1.1")
            self.assertEqual(_run_gates(root, "tests", "place", "1.1").returncode, 0)
            _stage(root)

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("red", result.stderr)

    def test_a_precondition_failure_is_not_a_red_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            _commit_authoring(root)
            _run_gates(root, "task", "start", "1.1")
            self.assertEqual(_run_gates(root, "tests", "place", "1.1").returncode, 0)
            (root / ".gates.yaml").write_text(PRECONDITION_MANIFEST)
            self.assertEqual(_run_gates(root, "run", "unit", "--task", "1.1").returncode, 75)
            _stage(root)

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_behaviour_free_task_needs_no_red_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            _commit_authoring(root)
            _run_gates(root, "task", "start", "1.3")
            self.assertEqual(_run_gates(root, "tests", "place", "1.3").returncode, 0)
            (root / "README.md").write_text("docs\n")
            _stage(root)

            result = _check(root)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_implementing_a_task_without_placing_its_tests_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            _commit_authoring(root)
            _run_gates(root, "task", "start", "1.1")
            (root / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
            _stage(root)

            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("gates tests place 1.1", result.stderr)


def _defects(root):
    return [r for r in _rows(root) if r["gate"] == "test-defect"]


class TestDefect(unittest.TestCase):
    """Regressions guarded: a defect recorded with no reason for the author
    to act on, and author and implementer bouncing a task's tests forever
    instead of reaching a human (design D5)."""

    def test_records_the_defect_with_its_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            result = _run_gates(root, "tests", "defect", "1.1", "--kind", "assertion", "--detail", "expects 6")
            self.assertEqual(result.returncode, 0, result.stderr)
            (row,) = _defects(root)
            self.assertEqual((row["task"], row["detail"]), ("1.1", "expects 6"))

    def test_refuses_without_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            result = _run_gates(root, "tests", "defect", "1.1", "--kind", "assertion", "--detail", "  ")
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(_defects(root), [])

    def test_third_defect_on_a_task_is_refused_naming_the_halt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            for n in (1, 2):
                self.assertEqual(
                    _run_gates(root, "tests", "defect", "1.1", "--kind", "assertion", "--detail", f"d{n}").returncode, 0)
            self.assertEqual(
                _run_gates(root, "tests", "defect", "1.2", "--kind", "assertion", "--detail", "other task").returncode, 0)

            result = _run_gates(root, "tests", "defect", "1.1", "--kind", "assertion", "--detail", "d3")

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("oracle-conflict", result.stderr)
            self.assertEqual(len(_defects(root)), 3)


def _show(root):
    result = _run_gates(root, "tests", "show", CHANGE, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestShow(unittest.TestCase):
    """Regression guarded: the session brief and the reviewer reading a
    wrong picture of the authoring state — no handoff reported as one, a
    placed task shown as held, or defects uncounted."""

    def test_no_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp)
            doc = _show(root)
            self.assertFalse(doc["handoff"])
            self.assertEqual(doc["mode"], "separate")

    def test_reports_each_task_placement_and_defects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            self.assertEqual(_run_gates(root, "tests", "place", "1.1").returncode, 0)
            self.assertEqual(
                _run_gates(root, "tests", "defect", "1.2", "--kind", "assertion", "--detail", "x").returncode, 0)

            doc = _show(root)

        self.assertTrue(doc["handoff"])
        self.assertEqual(doc["authors"], ["separate"])
        self.assertEqual(doc["tasks"]["1.1"],
                         {"tests": ["tests/test_calc.py"], "no_behaviour": None,
                          "characterization": None, "placed": True, "defects": 0,
                          "defects_by_kind": {"assertion": 0, "setup": 0, "green": 0},
                          "defect_log": []})
        self.assertEqual(doc["tasks"]["1.2"]["placed"], False)
        self.assertEqual(doc["tasks"]["1.2"]["defects"], 1)
        self.assertEqual(doc["tasks"]["1.3"]["no_behaviour"], "docs only")


class TestTwoTasksShareOneTestFile(unittest.TestCase):
    """End to end across real commits (design D3/D4, "two tasks extend one
    test file"). Regressions guarded: the lock staying on the earlier task's
    content after a later placement replaces it, and a defect's clean halt
    being refused because the voided placement still counts."""

    def _through_task_1_1(self, root):
        _commit_authoring(root)
        _place_red_and_stage(root, "1.1")
        (root / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
        _stage(root)
        self.assertEqual(_check(root).returncode, 0)
        _git(root, "commit", "-m", "task 1.1")

    def test_lock_moves_to_the_later_tasks_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            self._through_task_1_1(root)
            _place_red_and_stage(root, "1.2")
            self.assertEqual((root / "tests" / "test_calc.py").read_text(), TEST_V2)
            self.assertEqual(_check(root).returncode, 0)

            (root / "tests" / "test_calc.py").write_text(TEST_V1)
            _stage(root)
            result = _check(root)

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("task 1.2", result.stderr)

    def test_defect_then_clean_halt_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _authored_repo(tmp)
            self._through_task_1_1(root)
            _place_red_and_stage(root, "1.2")
            # Discard the task's partial work, keeping the ledger.
            _git(root, "reset", "-q")
            _git(root, "checkout", "--", "tests", ".gatedloop/authored")
            self.assertEqual(
                _run_gates(root, "tests", "defect", "1.2", "--kind", "assertion", "--detail", "wrong sign").returncode, 0)
            _git(root, "add", ".gatedloop/runs")

            result = _check(root)

            self.assertEqual(result.returncode, 0, result.stderr)


TOOL_HOOK = REPO / "hooks" / "gate-commit.sh"
GIT_HOOK = REPO / "templates" / "git-hooks" / "pre-commit"


def _hook_env():
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDECODE"] = "1"
    return env


def _tool_hook(root):
    return subprocess.run(
        ["bash", str(TOOL_HOOK)], cwd=root, env=_hook_env(), capture_output=True, text=True,
        input=json.dumps({"tool_input": {"command": "git commit -m x"}, "cwd": str(root)}),
    )


def _git_hook(root):
    return subprocess.run(
        ["bash", str(GIT_HOOK)], cwd=root, env=_hook_env(), capture_output=True, text=True,
    )


class TestCommitHooksRunTheCheck(unittest.TestCase):
    """Design D4, "where the check runs": both commit-creating paths the
    `ci` marker check covers also apply the authored-test check. Regression
    guarded: an edited placed test committed on a green `ci` marker, via
    either the tool hook or the git-layer hook."""

    def _green_ci(self, root):
        result = _run_gates(root, "run", "ci")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_both_hooks(self):
        for name, hook in (("tool", _tool_hook), ("git", _git_hook)):
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = _authored_repo(tmp)
                _stage(root)
                self._green_ci(root)
                authoring = hook(root)
                self.assertEqual(authoring.returncode, 0, authoring.stderr)
                _git(root, "commit", "--no-verify", "-m", "author tests")

                _place_red_and_stage(root, "1.1")
                self._green_ci(root)
                clean = hook(root)
                self.assertEqual(clean.returncode, 0, clean.stderr)

                (root / "tests" / "test_calc.py").write_text(TEST_V1.replace("5", "6"))
                _stage(root)
                self._green_ci(root)
                edited = hook(root)
                self.assertNotEqual(edited.returncode, 0, edited.stdout)
                self.assertIn("tests/test_calc.py", edited.stderr)


class TestLedgerRowCarriesAuthoringFields(unittest.TestCase):
    """Regression guarded: the fixed-shape row writer silently dropping the
    handoff's blobs, so nothing survives once the holding files move (D3)."""

    def test_written_row_keeps_tests_base_and_no_behaviour(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gates._append_ledger_row(root, {
                "gate": "tests-handoff", "change": CHANGE, "author": "separate",
                "tests": {"1.1": {"tests/test_calc.py": "abc"}},
                "base": {"tests/test_calc.py": None},
                "no_behaviour": {"1.2": "docs only"},
            })
            (row,) = _rows(root)
        self.assertEqual(row["tests"], {"1.1": {"tests/test_calc.py": "abc"}})
        self.assertEqual(row["base"], {"tests/test_calc.py": None})
        self.assertEqual(row["no_behaviour"], {"1.2": "docs only"})
        self.assertEqual(row["author"], "separate")


class TestAuthoringEventsAreNotGates(unittest.TestCase):
    """Regression guarded: `gates stats` counting a handoff, placement or
    defect row as a gate run, inflating gate counts and failures."""

    def test_authoring_events_count_as_events_not_gate_runs(self):
        rows = [
            {"ts": "2026-09-01T00:00:00+00:00", "gate": g, "exit": None, "duration_ms": 0}
            for g in ("tests-handoff", "tests-placed", "test-defect")
        ]
        stats = gates.stats_from_rows(rows, 30 * 60000)
        self.assertEqual(stats["gates"], {})
        self.assertEqual(set(stats["events"]), {"tests-handoff", "tests-placed", "test-defect"})


if __name__ == "__main__":
    unittest.main()
