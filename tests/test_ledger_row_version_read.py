"""Every ledger reader refuses a row newer than it knows (stability-contract D2).

The regressions:
- a row a newer plugin wrote is skipped, or read as a version-1 row, so an
  accept or merge row from a teammate's plugin silently reads as "never
  happened" or as something it does not mean;
- one reader is missed, so the same ledger is refused by `stats` and
  trusted by the merge;
- a ledger written before versioning reads differently once `v` exists;
- a `v` that is not an integer is trusted instead of counted as unreadable.

Real git and the real shim, through `_merge_fixture`. Stdlib only, per
`zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _merge_fixture import GATES_SHIM, LEDGER_REL, MergeRepo, clean_env, combined, git

_loader = importlib.machinery.SourceFileLoader("gates_shim_row_version_read", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CHANGE = "demo"
LEDGER = f".gatedloop/runs/{CHANGE}.jsonl"
MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n  acceptance: self\n'

# A row as the next version of the plugin might write it.
NEWER = {"ts": "2026-11-01T00:00:00+00:00", "gate": "ci", "exit": 0, "change": CHANGE, "v": 2}


def _run(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=clean_env())


def _repo(tmp: Path) -> Path:
    root = tmp / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    tasks = root / "openspec" / "changes" / CHANGE / "tasks.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text("## 1. Do it\n\n- [ ] 1.1 Do the thing\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    git(root, "checkout", "-q", "-b", CHANGE)
    (root / "feature.txt").write_text("the increment\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "task work")
    return root


def _append(root: Path, rel: str, row) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write((row if isinstance(row, str) else json.dumps(row)) + "\n")


def _assert_refused(test: unittest.TestCase, r: subprocess.CompletedProcess, ledger_name: str):
    out = combined(r)
    test.assertEqual(r.returncode, 1, out)
    test.assertIn(ledger_name, out)
    test.assertRegex(out, r"ledger row of version `?2`?")
    test.assertRegex(out, r"reads up to `?1`?")
    test.assertIn("Update the plugin", out)


class UnversionedLedgerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_stats_reads_a_ledger_without_v_exactly_as_one_marked_v_1(self):
        for _ in range(2):
            r = _run(self.root, "run", "ci", "--task", "1.1")
            self.assertEqual(r.returncode, 0, combined(r))
        path = self.root / LEDGER
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        path.write_text("".join(json.dumps({k: v for k, v in row.items() if k != "v"}) + "\n"
                                for row in rows))
        before = _run(self.root, "stats", "--change", CHANGE, "--json")
        self.assertEqual(before.returncode, 0, combined(before))
        path.write_text("".join(json.dumps({**row, "v": 1}) + "\n" for row in rows))
        after = _run(self.root, "stats", "--change", CHANGE, "--json")
        self.assertEqual(after.returncode, 0, combined(after))
        self.assertEqual(json.loads(before.stdout), json.loads(after.stdout))
        self.assertEqual(json.loads(before.stdout)["changes"][0]["skipped_lines"], 0)

    def test_a_non_integer_v_counts_as_an_unreadable_line(self):
        r = _run(self.root, "run", "ci", "--task", "1.1")
        self.assertEqual(r.returncode, 0, combined(r))
        _append(self.root, LEDGER, {**NEWER, "v": "2"})
        stats = _run(self.root, "stats", "--change", CHANGE, "--json")
        self.assertEqual(stats.returncode, 0, combined(stats))
        report = json.loads(stats.stdout)["changes"][0]
        self.assertEqual(report["skipped_lines"], 1)


class NewerRowRefusedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = _repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_stats_refuses_naming_the_file_and_both_versions(self):
        r = _run(self.root, "run", "ci", "--task", "1.1")
        self.assertEqual(r.returncode, 0, combined(r))
        _append(self.root, LEDGER, NEWER)
        _assert_refused(self, _run(self.root, "stats", "--change", CHANGE), f"{CHANGE}.jsonl")
        _assert_refused(self, _run(self.root, "stats", "--change", CHANGE, "--json"),
                        f"{CHANGE}.jsonl")

    def test_acceptance_check_refuses_rather_than_trusting_the_accept_row(self):
        a = _run(self.root, "acceptance", "attest", CHANGE, "--local")
        self.assertEqual(a.returncode, 0, combined(a))
        tree = git(self.root, "rev-parse", "HEAD^{tree}")
        ok = _run(self.root, "acceptance", "check", tree)
        self.assertEqual(ok.returncode, 0, combined(ok))
        _append(self.root, LEDGER, NEWER)
        _assert_refused(self, _run(self.root, "acceptance", "check", tree), f"{CHANGE}.jsonl")

    def test_a_committed_newer_row_read_from_a_tree_is_refused(self):
        _append(self.root, LEDGER, NEWER)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "a teammate's row")
        with self.assertRaises(SystemExit) as raised:
            gates._ledger_rows_at(self.root, git(self.root, "rev-parse", "HEAD"))
        message = str(raised.exception.code)
        self.assertIn(f"{CHANGE}.jsonl", message)
        self.assertRegex(message, r"ledger row of version `?2`?")
        self.assertRegex(message, r"reads up to `?1`?")


class MergeRefusesNewerRowTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_merge_exits_1_and_writes_no_merge_row(self):
        repo = MergeRepo(self.tmp)
        repo.start_change(lane=True)
        repo.task_commit("one.txt", "1\n", "add the part")
        repo.prove_head()
        repo.append_lane_row({**NEWER, "change": "add-thing"})
        git(repo.lane, "add", "-A")
        git(repo.lane, "commit", "-q", "-m", "trailing rows")
        origin_before = repo.origin_main()

        r = repo.merge()

        _assert_refused(self, r, Path(LEDGER_REL).name)
        self.assertEqual(repo.origin_main(), origin_before)
        for ref in ("HEAD", "refs/heads/main", "refs/heads/add-thing"):
            for cwd in (repo.primary, repo.lane):
                merges = [row for row in repo.rows_at(ref, cwd=cwd) if row.get("gate") == "merge"]
                self.assertEqual(merges, [], f"a merge row was written at {ref}")
        on_disk = repo.primary / LEDGER_REL
        if on_disk.exists():
            self.assertNotIn('"gate": "merge"', on_disk.read_text())


if __name__ == "__main__":
    unittest.main()
