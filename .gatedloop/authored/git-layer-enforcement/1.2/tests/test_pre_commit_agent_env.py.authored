"""The git `pre-commit` template decides "agent session" through `gates
discipline agent-session` and resolves the shim three ways (change
`git-layer-enforcement`, design D1 and D2).

The regressions caught here: the template still testing `CLAUDECODE` itself
(an agent on another host, with its declared variable set, commits
ungated); a human commit gated; and a hook that can only find the shim
inside a plugin environment (the plugin root or `gates` on PATH), so
outside one it never enforces — the recorded install path is the last
fallback.

A real `git commit` with the template installed as the repository's
pre-commit hook: the git layer is the boundary under test, and only a real
commit runs it the way any host's commit would. `ci` is declared as `false`,
so it never passed and no marker exists: an enforcing hook denies the code
commit, and a no-op hook lets it through.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import (GATES_SHIM, REPO, TEMPLATE, default_hook,  # noqa: E402
                           env_without_gates, gate_free_path, gates_on_path_dir, init_repo,
                           with_recorded, write_hook)

MANIFEST = ('gatesVersion: 1\ngates:\n  ci: "false"\n'
            'discipline:\n  agent-env:\n    - "CLAUDECODE"\n    - "OTHER_HOST_VAR"\n')


class PreCommitTemplateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "repo"
        self.root.mkdir()
        init_repo(self.root)
        (self.root / ".gates.yaml").write_text(MANIFEST)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "init", env=env_without_gates())
        self.n = 0

    def _git(self, *args, env=None) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True,
                              env=env or env_without_gates(), timeout=120)

    def install(self, body: str) -> None:
        write_hook(default_hook(self.root), body)

    def code_commit(self, **env) -> subprocess.CompletedProcess:
        """Stage a new code file and commit it with exactly `env`."""
        self.n += 1
        (self.root / f"code{self.n}.txt").write_text(f"change {self.n}\n")
        self._git("add", f"code{self.n}.txt")
        return self._git("commit", "-q", "-m", f"code {self.n}", env=env_without_gates(**env))

    def assert_denied(self, r):
        self.assertNotEqual(r.returncode, 0, "the hook let an ungated code commit through")
        self.assertIn("gatedloop", r.stderr)

    def test_a_session_is_enforced_by_either_declared_variable(self):
        # Scenarios "A commit inside a session is enforced" and "Another
        # host's agent is declared". Fails if the template still tested
        # CLAUDECODE itself: the second variable would commit ungated.
        self.install(TEMPLATE.read_text())
        for var in ("CLAUDECODE", "OTHER_HOST_VAR"):
            with self.subTest(var=var):
                self.assert_denied(self.code_commit(**{var: "1", "CLAUDE_PLUGIN_ROOT": str(REPO)}))

    def test_a_human_commit_is_not_gated(self):
        # Scenario "A human or CI commit is not gated".
        self.install(TEMPLATE.read_text())
        r = self.code_commit(CLAUDE_PLUGIN_ROOT=str(REPO))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_shim_resolves_through_path_without_a_plugin_root(self):
        # Fails if only the plugin root could find the shim.
        self.install(TEMPLATE.read_text())
        path = gates_on_path_dir(self.tmp) + ":" + gate_free_path()
        self.assert_denied(self.code_commit(OTHER_HOST_VAR="1", PATH=path))

    def test_the_recorded_install_path_is_the_last_fallback(self):
        # Design D2: outside any plugin environment (no plugin root, no
        # `gates` on PATH) the path `gates hook install` wrote still finds
        # the shim, so the hook enforces on a host with no plugin at all.
        self.install(with_recorded(TEMPLATE.read_text(), GATES_SHIM))
        self.assert_denied(self.code_commit(OTHER_HOST_VAR="1"))

    def test_nothing_resolving_the_shim_never_blocks_the_commit(self):
        # Fails toward the human (design Risks): with no way to find the
        # shim the hook cannot tell a session from a human, so it lets the
        # commit through and says why on stderr.
        self.install(TEMPLATE.read_text())
        r = self.code_commit(OTHER_HOST_VAR="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stderr.strip(), "the hook must say it could not resolve the shim")


if __name__ == "__main__":
    unittest.main()
