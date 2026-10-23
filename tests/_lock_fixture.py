"""A change branch carried through the authored-test lock, for the tests of
change `test-lock-remote-check`.

`LockRepo` is `_merge_fixture.MergeRepo` (a real repository with a bare
`origin`, change `add-thing` planned on `main`) whose change has authored
tests: tasks 1.1 and 1.2 each place `TEST_REL` (1.2 extends 1.1's file),
task 1.3 is behaviour-free. Its helpers walk the loop's own sequence --
handoff, task start, place, a red `unit`, implement, a green `ci`, commit --
so a test arranges a history the way a lane writes it, then breaks one step
on purpose.

Every commit goes through `gates run ci` first, as the loop's do, so the
merge step's audit finds no unrecorded commit. No git hook is installed in
these repositories: a plain `git commit` here is exactly "a commit the
commit hooks did not see".

Stdlib only, per `zero-dep-shim`. Not a test module (no `test` prefix).
"""

from __future__ import annotations

from pathlib import Path

from _merge_fixture import CHANGE, MergeRepo, combined, git

UNIT_RED = '  unit: "false"\n'

TEST_REL = "tests/test_thing.py"
TEST_BASE = "# the thing's tests, before this change\n"
TEST_V1 = "def test_thing():\n    assert thing() == 1\n"
TEST_V2 = TEST_V1 + "\ndef test_thing_twice():\n    assert thing() + thing() == 2\n"
TEST_EDITED = TEST_V1.replace("== 1", "== 2")

AUTHORED = {"1.1": {TEST_REL: TEST_V1}, "1.2": {TEST_REL: TEST_V2}}
BEHAVIOUR_FREE = {"1.3": "docs only"}


class LockRepo(MergeRepo):
    """`MergeRepo` with a `unit` gate that is always red (the lock needs a
    red run after placement, never a green one) and the authoring helpers."""

    def __init__(self, tmp: Path, manifest_extra: str = ""):
        super().__init__(tmp, manifest_extra=UNIT_RED + manifest_extra)

    # ---- the loop's steps ----------------------------------------------

    def must(self, *args, cwd=None, **env):
        r = self.gates(*args, cwd=cwd or self.lane, **env)
        if r.returncode != 0:
            raise AssertionError(f"fixture `gates {' '.join(args)}` failed: {combined(r)}")
        return r

    def gated_commit(self, subject: str, task: str | None = None) -> str:
        """Stage everything, a green `gates run ci`, commit with its row."""
        git(self.lane, "add", "-A")
        self.must("run", "ci", *(["--task", task] if task else []))
        git(self.lane, "add", "-A")
        git(self.lane, "commit", "-q", "-m", subject)
        return self.head()

    def author(self, with_base: bool = True) -> str:
        """Commit `TEST_BASE` (unless told not to), then hold every task's
        tests, hand them off and commit the authoring. Returns its sha."""
        if with_base:
            self.write(TEST_REL, TEST_BASE)
            self.gated_commit("the thing's existing tests")
        holding = self.lane / ".gatedloop" / "authored" / CHANGE
        for task, files in AUTHORED.items():
            for rel, content in files.items():
                p = holding / task / f"{rel}.authored"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
        for task, reason in BEHAVIOUR_FREE.items():
            p = holding / task / "NO-TESTS"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(reason + "\n")
        self.must("tests", "handoff", CHANGE)
        return self.gated_commit(f"author tests: {CHANGE}")

    def place(self, task: str) -> None:
        self.must("task", "start", task)
        self.must("tests", "place", task)

    def red(self, task: str) -> None:
        r = self.gates("run", "unit", "--task", task, "--attempt", "1", cwd=self.lane)
        if r.returncode in (0, 75):
            raise AssertionError(f"fixture red run for {task} was not red: {combined(r)}")

    def do_task(self, task: str, red: bool = True) -> str:
        """Place, run red (unless told not to), implement, commit."""
        self.place(task)
        if red:
            self.red(task)
        self.write(f"src/task_{task.replace('.', '_')}.txt", f"task {task}\n")
        return self.gated_commit(f"task {task}", task)

    def void(self, task: str) -> str:
        """Place and run red, then send the tests back as a defect and
        discard the task's partial work, committing only the ledger."""
        self.place(task)
        self.red(task)
        self.must("tests", "defect", task, "--kind", "assertion", "--detail", "asserts the wrong thing")
        ledger = self.lane / ".gatedloop" / "runs" / f"{CHANGE}.jsonl"
        rows = ledger.read_bytes()
        git(self.lane, "checkout", "-q", "--", ".")  # the placed path and holding file come back
        ledger.write_bytes(rows)
        return self.gated_commit(f"test defect: {task}")

    def edit_past_the_hooks(self, rel: str, content: str, subject: str = "edit a locked test") -> str:
        """A commit no commit hook saw: here, simply a commit (none is installed)."""
        self.write(rel, content)
        return self.gated_commit(subject)

    # ---- reading ---------------------------------------------------------

    def write(self, rel: str, content: str) -> None:
        f = self.lane / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)

    def head(self, cwd=None) -> str:
        return git(cwd or self.lane, "rev-parse", "HEAD")

    def check_ref(self, ref: str, *extra: str, cwd=None, **env):
        return self.gates("tests", "check", "--ref", ref, *extra, cwd=cwd or self.lane, **env)


def finished_lane(tmp: Path, lane: bool = True, manifest_extra: str = "") -> LockRepo:
    """A change whose every task is done and committed with its lock intact,
    and whose head is proven (ci, live-check), ready for `gates merge`."""
    repo = LockRepo(tmp, manifest_extra=manifest_extra)
    repo.start_change(lane=lane)
    repo.author()
    repo.do_task("1.1")
    repo.do_task("1.2")
    repo.place("1.3")
    repo.write("README.md", "docs\n")
    repo.gated_commit("task 1.3", "1.3")
    return repo
