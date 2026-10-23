"""Both commit layers apply the same commit check (design D4 of
`lock-and-ledger-hygiene`, #33 item 7).

The tool-level hook runs `gates discipline check-commit`, which allows a
ledger-only commit (ledger grade) and a planning-only commit (planning grade)
without a `ci` marker. The git-layer `pre-commit` ran only `gate-marker check
ci`, so the same commit made by any path the tool hook does not see was
denied, and cost a full `ci` run (129 s in the field) to satisfy. The git
layer now runs `check-commit` too.

A real `git commit` with the template installed as the repo's pre-commit
hook: the git layer is the boundary under test, and only a real commit
exercises it the way a subprocess or library commit would. A code commit
without a matching marker is still denied -- covered at both layers by
`test_stale_denial_names_paths`, which runs this same template.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GIT_PRE_COMMIT = REPO / "templates" / "git-hooks" / "pre-commit"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "false"\n'


def _git(cwd, *args, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)


def _session_env(root: Path) -> dict:
    env = dict(os.environ)
    env["CLAUDECODE"] = "1"
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    return env


class TestGitLayerAllowsWhatTheToolLayerAllows(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for args in (("init", "-b", "main"), ("config", "user.email", "t@example.com"),
                     ("config", "user.name", "T")):
            self.assertEqual(_git(self.root, *args).returncode, 0)
        (self.root / ".gates.yaml").write_text(MANIFEST)
        (self.root / "openspec").mkdir()
        (self.root / "openspec" / "config.yaml").write_text("schema: spec-driven\n")
        _git(self.root, "add", "-A")
        self.assertEqual(_git(self.root, "commit", "-m", "init").returncode, 0)
        hook = self.root / ".git" / "hooks" / "pre-commit"
        shutil.copy(GIT_PRE_COMMIT, hook)
        hook.chmod(0o755)

    def tearDown(self):
        self._tmp.cleanup()

    def test_ledger_and_planning_commits_need_no_ci_run(self):
        """`ci` is declared as `false`: it never passed, so no marker exists
        and only the grade allowances can let these commits through."""
        cases = (
            ("ledger-grade", ".gatedloop/runs/lane.jsonl", '{"gate": "ci"}\n'),
            ("planning-grade", "openspec/config.yaml", "schema: spec-driven\n# edited\n"),
        )
        for verdict, rel, content in cases:
            with self.subTest(verdict=verdict):
                path = self.root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                _git(self.root, "add", rel)
                r = _git(self.root, "commit", "-m", f"only {rel}", env=_session_env(self.root))
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn(f"{verdict} commit allowed", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
