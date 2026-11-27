"""The commit check under `loop.ci-at: ready` (openspec change `ci-at`,
design D2; the loop-enforcement delta's "Commit is blocked unless CI passed on
the tree being committed" requirement).

The regressions: a `unit` marker that allows a commit under `task` or with the
key absent; one that allows a commit off a change branch (`main`, `plan/*`, a
detached HEAD, so the squash `gates merge` makes); a `ci` marker no longer
allowing a commit under `ready`; a `unit` marker written under `task`; and a
denial under `ready` that sends the loop back to the full `ci`.

Real git in a throwaway repository: the verdict is a function of the staged
index and the current branch, which only a real repository has.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_ci_at_commit_check", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
READY = BASE + "loop:\n  ci-at: ready\n"
TASK = BASE + "loop:\n  ci-at: task\n"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env()).stdout.strip()


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


class _Repo(unittest.TestCase):
    MANIFEST = READY

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        self.root.mkdir()
        self.verdict = Path(self._tmp.name) / "verdict"
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(self.MANIFEST)
        (self.root / "openspec" / "changes" / "my-change").mkdir(parents=True)
        (self.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
        (self.root / "openspec" / "changes" / "my-change" / "tasks.md").write_text(
            "## 1. Work\n\n- [ ] 1.1 do it\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def _set_manifest(self, text):
        (self.root / ".gates.yaml").write_text(text)
        _git(self.root, "add", ".gates.yaml")
        _git(self.root, "commit", "-q", "-m", "manifest")

    def _stage_code(self):
        (self.root / "app.py").write_text("print('hi')\n")
        _git(self.root, "add", "app.py")

    def _run(self, gate):
        r = _gates(self.root, "run", gate)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def _check(self):
        self.verdict.unlink(missing_ok=True)
        tree = _git(self.root, "write-tree")
        return _gates(self.root, "discipline", "check-commit", tree,
                      "--verdict-file", str(self.verdict))

    def _token(self):
        return self.verdict.read_text().strip() if self.verdict.exists() else None

    def _marker_dir(self, gate):
        return Path(_git(self.root, "rev-parse", "--absolute-git-dir")) / "gatedloop" / "markers" / gate


class TestReadyOnAChangeBranch(_Repo):
    def setUp(self):
        super().setUp()
        _git(self.root, "checkout", "-q", "-b", "my-change")

    def test_a_unit_marker_allows_the_commit_with_the_unit_token(self):
        self._stage_code()
        self._run("unit")
        r = self._check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._token(), "unit")
        self.assertIn("'unit' marker matches", r.stdout)
        self.assertIn("loop.ci-at: ready", r.stdout)
        self.assertIn("the full ci runs before READY and at the merge", r.stdout)

    def test_the_unit_marker_records_its_scope(self):
        self._stage_code()
        self._run("unit")
        markers = list(self._marker_dir("unit").glob("*.json"))
        self.assertEqual(len(markers), 1)
        self.assertIn('"scope": "full"', markers[0].read_text())

    def test_a_ci_marker_still_allows_it_with_the_marker_token(self):
        self._stage_code()
        self._run("ci")
        r = self._check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._token(), "marker")

    def test_no_marker_is_denied_naming_gates_run_unit(self):
        self._stage_code()
        r = self._check()
        self.assertEqual(r.returncode, 1)
        self.assertIsNone(self._token())
        self.assertIn("gates run unit", r.stderr)
        self.assertIn("gates run ci", r.stderr)

    def test_a_unit_marker_for_another_tree_is_stale(self):
        self._stage_code()
        self._run("unit")
        (self.root / "app.py").write_text("print('changed')\n")
        _git(self.root, "add", "app.py")
        r = self._check()
        self.assertEqual(r.returncode, 1)
        self.assertIn("gates run unit", r.stderr)
        self.assertIn("app.py", r.stderr)

    def test_a_ledger_only_commit_stays_ledger_grade(self):
        ledger = self.root / ".gatedloop" / "runs" / "my-change.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text('{"gate": "halt", "task": "1.1", "change": "my-change"}\n')
        _git(self.root, "add", ".gatedloop/runs/my-change.jsonl")
        r = self._check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._token(), "ledger")

    def test_a_planning_only_commit_stays_planning_grade(self):
        (self.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n# edited\n")
        _git(self.root, "add", "openspec/config.yaml")
        r = self._check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._token(), "planning")


class TestReadyOffAChangeBranch(_Repo):
    def _denied_on_unit_only(self):
        self._stage_code()
        self._run("unit")
        r = self._check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIsNone(self._token())
        return r

    def test_main_needs_a_ci_marker(self):
        r = self._denied_on_unit_only()
        self.assertIn("gates run ci", r.stderr)

    def test_a_plan_branch_needs_a_ci_marker(self):
        _git(self.root, "checkout", "-q", "-b", "plan/my-change")
        self._denied_on_unit_only()

    def test_a_detached_head_needs_a_ci_marker(self):
        _git(self.root, "checkout", "-q", "--detach")
        self._denied_on_unit_only()

    def test_an_archived_only_change_branch_needs_a_ci_marker(self):
        _git(self.root, "checkout", "-q", "-b", "done-change")
        arch = self.root / "openspec" / "changes" / "archive" / "2026-01-01-done-change"
        arch.mkdir(parents=True)
        (arch / "tasks.md").write_text("- [x] 1.1 done\n")
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", "archive")
        self._denied_on_unit_only()

    def test_the_merge_squash_commit_needs_a_ci_marker(self):
        # `gates merge` commits its squash on a detached HEAD through
        # `_merge_commit`, which runs the same check-commit.
        tip = _git(self.root, "rev-parse", "HEAD")
        _git(self.root, "checkout", "-q", "--detach")
        self._stage_code()
        self._run("unit")
        m = {"gates": {"ci": "true", "unit": "true"}, "loop": {"ci-at": "ready"}}
        with self.assertRaises(gates._MergeHalt):
            gates._merge_commit(m, self.root, 2, "squash", tip, {"branch": None, "sha": tip})


class TestTaskMode(_Repo):
    MANIFEST = TASK

    def setUp(self):
        super().setUp()
        _git(self.root, "checkout", "-q", "-b", "my-change")

    def test_a_unit_run_writes_no_unit_marker(self):
        self._stage_code()
        self._run("unit")
        self.assertFalse(self._marker_dir("unit").exists()
                         and any(self._marker_dir("unit").glob("*.json")))

    def test_a_unit_only_commit_is_denied(self):
        self._stage_code()
        self._run("unit")
        r = self._check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("gates run ci", r.stderr)

    def test_a_ci_marker_allows_it(self):
        self._stage_code()
        self._run("ci")
        r = self._check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._token(), "marker")


class TestKeyAbsent(TestTaskMode):
    MANIFEST = BASE


if __name__ == "__main__":
    unittest.main()
