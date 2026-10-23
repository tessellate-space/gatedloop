"""The propose gate reads the change's state, not HEAD (design D5 of
`hook-correctness`, #33 item 4).

`gates discipline check-propose <path>` refused every planning write on a
detached HEAD -- exactly where a merge recipe parks the primary checkout --
and on any branch that was neither the target nor `plan/*`, although the
rule it enforces (design D9 of `harden-unattended-loop`) is narrower: don't
author a plan from inside the change's IMPLEMENTATION. It also judged only
`proposal.md`, `design.md` and `specs/**/*.md`, so other artifacts of the
same plan slipped by, and its debris advisory could call a directory
"unproposed" that the integration target already tracks.

Now: the change comes from the written path; the write is refused only when
that change is in implementation (a branch `<name>` with commits beyond the
target, or a `task-start` ledger row); every artifact under the change
directory except `tasks.md` is treated alike; "unproposed" is decided by
whether the directory is tracked at the target's tip.

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
    return r.stdout.strip()


def _check(root: Path, rel: str):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), "discipline", "check-propose", rel],
        cwd=root, capture_output=True, text=True,
    )


def _init_repo(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(MANIFEST)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")


def _implementing(root: Path, change: str) -> None:
    """Put `change` in implementation: its own branch, one task commit ahead
    of main. Leaves `main` checked out."""
    _git(root, "checkout", "-b", change)
    (root / f"{change}-code.txt").write_text("task 1.1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "task 1.1")
    _git(root, "checkout", "main")


PROPOSAL = "openspec/changes/foo/proposal.md"


class TestNotInImplementationIsAllowedAnywhere(unittest.TestCase):
    def test_detached_head_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "--detach", "main")
            r = _check(root, PROPOSAL)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_plan_branch_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "plan/foo")
            r = _check(root, PROPOSAL)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_unrelated_branch_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "docs-tweaks")
            r = _check(root, PROPOSAL)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_change_branch_before_any_task_commit_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "foo")
            r = _check(root, PROPOSAL)
            self.assertEqual(r.returncode, 0, r.stderr)


class TestInImplementationIsRefusedOffTheTarget(unittest.TestCase):
    def test_a_change_branch_ahead_of_the_target_refuses_every_artifact_but_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _implementing(root, "foo")
            _git(root, "checkout", "--detach", "foo")
            for artifact in (
                "proposal.md", "design.md", "specs/cap/spec.md", "adr/0001-choice.md",
                "research.md",
            ):
                with self.subTest(artifact=artifact):
                    r = _check(root, f"openspec/changes/foo/{artifact}")
                    self.assertEqual(r.returncode, 1, r.stdout)
                    self.assertIn("in implementation", r.stderr)
            r = _check(root, "openspec/changes/foo/tasks.md")
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_task_start_ledger_row_marks_the_change_in_implementation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "lane")
            start = subprocess.run(
                [sys.executable, str(GATES_SHIM), "task", "start", "1.1", "--change", "foo"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(start.returncode, 0, start.stderr)
            r = _check(root, "openspec/changes/foo/design.md")
            self.assertEqual(r.returncode, 1, r.stdout)

    def test_the_target_itself_stays_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _implementing(root, "foo")
            r = _check(root, PROPOSAL)
            self.assertEqual(r.returncode, 0, r.stderr)


class TestUnproposedMeansUntrackedAtTheTarget(unittest.TestCase):
    def test_only_a_directory_untracked_at_the_target_tip_is_called_unproposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            _git(root, "checkout", "-b", "foo")
            (root / "foo-code.txt").write_text("task\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "task 1.1")
            # `bar` lands on main after `foo` branched ...
            _git(root, "checkout", "main")
            bar = root / "openspec" / "changes" / "bar"
            bar.mkdir(parents=True)
            (bar / "proposal.md").write_text("bar\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "propose bar")
            _git(root, "checkout", "foo")
            # ... and is present, untracked, in foo's checkout; `baz` is
            # untracked everywhere.
            bar.mkdir(parents=True)
            (bar / "proposal.md").write_text("bar\n")
            baz = root / "openspec" / "changes" / "baz"
            baz.mkdir(parents=True)
            (baz / "proposal.md").write_text("baz\n")

            r = _check(root, PROPOSAL)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("openspec/changes/baz", r.stderr)
            self.assertNotIn("openspec/changes/bar", r.stderr)


if __name__ == "__main__":
    unittest.main()
