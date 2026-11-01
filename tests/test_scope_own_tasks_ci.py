"""A task commit's own tick does not widen `ci`'s scope (scope-own-tasks D1-D3, #122).

Every task commit stages its change's `tasks.md` `[x]` beside its code. Under
err-full scoping that path was either unmatched (no surface covers
`openspec/**`) or a second hot surface (one does), so a task commit could never
run a surface's scoped `ci`. The current change's own `tasks.md` -- the change
the branch resolves to -- is now left out of scope selection. Another change's
`tasks.md` still counts, and off a change branch nothing is exempt.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

CHANGE = "demo"
OWN_TASKS = f"openspec/changes/{CHANGE}/tasks.md"
OTHER_TASKS = "openspec/changes/other/tasks.md"

MANIFEST = """\
gatesVersion: 1
gates:
  ci: "echo GLOBAL-CI"
  unit: "echo GLOBAL-UNIT"
surfaces:
  - name: frontend
    match: "frontend/**"
    gates:
      ci: "echo SCOPED-CI"
      unit: "echo SCOPED-UNIT"
"""

MANIFEST_WITH_OPENSPEC_SURFACE = MANIFEST + """\
  - name: docs
    match: "openspec/**"
"""


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _write(root: Path, rel: str, text: str = "x\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _repo(root: Path, manifest: str, branch: str | None = CHANGE) -> None:
    """`main` holds the manifest and two changes' task lists; `branch`, when
    given, is cut from it and is the change the run resolves to."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    _write(root, OWN_TASKS, "## 1. Do it\n\n- [ ] 1.1 Do the thing\n")
    _write(root, OTHER_TASKS, "## 1. Other\n\n- [ ] 1.1 Other thing\n")
    _write(root, "frontend/app.js", "v1\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    if branch:
        _git(root, "checkout", "-b", branch)


def _stage_task_commit(root: Path, tasks: str = OWN_TASKS) -> None:
    """A frontend edit plus a tick in `tasks`, both staged."""
    _write(root, "frontend/app.js", "v2\n")
    p = root / tasks
    p.write_text(p.read_text().replace("- [ ]", "- [x]"))
    _git(root, "add", "frontend/app.js", tasks)


def _log(root: Path) -> str:
    logs = list((root / ".gatedloop" / "out").glob("ci-*.log"))
    assert len(logs) == 1, logs
    return logs[0].read_text()


class TestOwnTickDoesNotWidenCi(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_own_tick_with_no_surface_over_openspec_runs_scoped_ci(self):
        _repo(self.root, MANIFEST)
        _stage_task_commit(self.root)

        r = _run_gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SCOPED-CI", _log(self.root))
        self.assertNotIn("matches no surface", r.stderr)

    def test_own_tick_with_openspec_in_its_own_surface_runs_scoped_ci(self):
        _repo(self.root, MANIFEST_WITH_OPENSPEC_SURFACE)
        _stage_task_commit(self.root)

        r = _run_gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SCOPED-CI", _log(self.root))

    def test_another_changes_tasks_md_still_errs_full_and_is_named(self):
        _repo(self.root, MANIFEST)
        _stage_task_commit(self.root, tasks=OTHER_TASKS)

        r = _run_gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("GLOBAL-CI", _log(self.root))
        self.assertIn(f"ci[full] — {OTHER_TASKS} matches no surface", r.stderr)

    def test_on_main_nothing_is_exempt(self):
        _repo(self.root, MANIFEST, branch=None)
        _stage_task_commit(self.root)

        r = _run_gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("GLOBAL-CI", _log(self.root))
        self.assertIn(f"ci[full] — {OWN_TASKS} matches no surface", r.stderr)

    def test_a_tick_alone_runs_the_global_ci(self):
        _repo(self.root, MANIFEST)
        p = self.root / OWN_TASKS
        p.write_text(p.read_text().replace("- [ ]", "- [x]"))
        _git(self.root, "add", OWN_TASKS)

        r = _run_gates(self.root, "run", "ci")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("GLOBAL-CI", _log(self.root))


if __name__ == "__main__":
    unittest.main()
