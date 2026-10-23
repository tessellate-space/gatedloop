"""A branch is a change only when `openspec/changes/<branch>/` exists (design
D6 of `hook-correctness`, #33 item 9, #35 rule 3).

"Branch = change" was never checked against the change directory, so a
`plan/<name>` branch or a docs branch grew its own ledger -- the stray
`.gatedloop/runs/plan/` and `<branch>.jsonl` files this repo kept deleting --
and `--change plan/<name>` minted a nested ledger path. Now: only a branch
backed by an active (or just-archived) change directory keys the ledger, a
`/` in `--change` is refused naming the bare name, and a detached HEAD with
no `--change` says that no row was written.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _gates(root: Path, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args], cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _ledger_files(root: Path) -> list[str]:
    runs = root / ".gatedloop" / "runs"
    if not runs.exists():
        return []
    return sorted(str(p.relative_to(runs)) for p in runs.rglob("*") if p.is_file())


class TestOnlyDirectoryBackedBranchesKeyTheLedger(unittest.TestCase):
    def test_a_plan_branch_writes_no_ledger_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "plan/foo")
            r = _gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_ledger_files(root), [])

    def test_a_docs_branch_writes_no_ledger_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "docs-tweaks")
            r = _gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_ledger_files(root), [])

    def test_an_active_change_branch_keys_its_own_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "openspec" / "changes" / "foo").mkdir(parents=True)
            (root / "openspec" / "changes" / "foo" / "proposal.md").write_text("foo\n")
            _git(root, "checkout", "-b", "foo")
            r = _gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_ledger_files(root), ["foo.jsonl"])

    def test_a_just_archived_change_still_keys_its_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            archived = root / "openspec" / "changes" / "archive" / "2026-09-30-foo"
            archived.mkdir(parents=True)
            (archived / "proposal.md").write_text("foo\n")
            _git(root, "checkout", "-b", "foo")
            r = _gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(_ledger_files(root), ["foo.jsonl"])


class TestASlashInAChangeNameIsRefused(unittest.TestCase):
    def test_change_with_a_slash_is_refused_naming_the_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            r = _gates(root, "run", "ci", "--change", "plan/foo")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("change names never contain '/'; use `foo`", r.stderr)
            self.assertEqual(_ledger_files(root), [])


class TestDetachedHeadSaysNoRowWasWritten(unittest.TestCase):
    def test_detached_head_without_change_prints_the_no_row_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "--detach", "main")
            r = _gates(root, "run", "ci")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(
                "detached HEAD — no ledger row written; pass --change <name> to record one",
                r.stderr,
            )
            self.assertEqual(_ledger_files(root), [])


if __name__ == "__main__":
    unittest.main()
