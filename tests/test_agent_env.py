"""`discipline.agent-env` and `gates discipline agent-session` (change
`git-layer-enforcement`, design D1).

The git-layer hooks used to test `CLAUDECODE` themselves, so an agent on any
other host committed and pushed ungated. The decision now lives in one
place: `gates discipline agent-session` exits 0 when any variable the
manifest lists is set, 1 otherwise, with `[CLAUDECODE]` as the default.

The regressions caught here: the default list lost (a Claude Code session no
longer enforced), a declared second variable ignored (another host still
ungated), a declaration that appends to the default instead of replacing it,
an empty value read as a session, a malformed declaration accepted by
`gates validate`, and a malformed declaration that stops the hooks deciding
at all (it falls back to the default instead, so no human is blocked and a
Claude Code session stays enforced).

Black-box, as the hooks call it: the shim runs as a subprocess in a throwaway
git repository with the environment set explicitly, never inherited.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import GATES_SHIM, init_repo  # noqa: E402

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
SESSION_VARS = ("CLAUDECODE", "OTHER_HOST_VAR")


def _manifest(agent_env_block: str) -> str:
    return BASE + "discipline:\n" + agent_env_block


DECLARED_TWO = _manifest('  agent-env:\n    - "CLAUDECODE"\n    - "OTHER_HOST_VAR"\n')
DECLARED_OTHER_ONLY = _manifest('  agent-env:\n    - "OTHER_HOST_VAR"\n')
# Each is not a list of non-empty variable names, in a shape both YAML
# parsers (PyYAML and the shim's own) read as invalid.
INVALID = (
    ("a bare string", _manifest('  agent-env: "OTHER_HOST_VAR"\n')),
    ("a name starting with a digit", _manifest('  agent-env:\n    - "1BAD"\n')),
    ("a name with a space", _manifest('  agent-env:\n    - "HAS SPACE"\n')),
    ("an empty name", _manifest('  agent-env:\n    - ""\n')),
    ("a mapping", _manifest('  agent-env:\n    CLAUDECODE: "1"\n')),
)


def _env(**set_vars) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in SESSION_VARS}
    env.update(set_vars)
    return env


def _repo(tmp: str, manifest: str | None) -> Path:
    root = Path(tmp)
    init_repo(root)
    if manifest is not None:
        (root / ".gates.yaml").write_text(manifest)
    return root


def _gates(root: Path, *args, **set_vars) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(**set_vars), timeout=60)


def _session(root: Path, **set_vars) -> int:
    return _gates(root, "discipline", "agent-session", **set_vars).returncode


class TestTheDefaultList(unittest.TestCase):
    """With nothing declared, the list is `[CLAUDECODE]` — with or without a
    manifest, since the hook runs in repositories that have none yet."""

    def test_claudecode_alone_marks_a_session(self):
        # Fails if the default were lost: a Claude Code session would stop
        # enforcing at the git layer.
        for name, manifest in (("no manifest", None), ("no declaration", BASE)):
            with self.subTest(manifest=name), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp, manifest)
                self.assertEqual(_session(root, CLAUDECODE="1"), 0)
                self.assertEqual(_session(root), 1)
                self.assertEqual(_session(root, OTHER_HOST_VAR="1"), 1,
                                 "an undeclared variable is not a session")

    def test_an_empty_value_is_not_a_session(self):
        # Fails if presence of the name alone counted: the earlier hook
        # tested a non-empty value, and an exported empty variable is no
        # agent.
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, None)
            self.assertEqual(_session(root, CLAUDECODE=""), 1)


class TestADeclaredList(unittest.TestCase):
    def test_a_second_declared_variable_marks_a_session(self):
        # Scenario "Another host's agent is declared".
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, DECLARED_TWO)
            self.assertEqual(_session(root, OTHER_HOST_VAR="1"), 0)
            self.assertEqual(_session(root, CLAUDECODE="1"), 0)
            self.assertEqual(_session(root), 1)

    def test_the_declaration_replaces_the_default(self):
        # Fails if the declared list were appended to `[CLAUDECODE]`: an
        # adopter who lists only their own host's variable would still be
        # gated on a variable they never named.
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, DECLARED_OTHER_ONLY)
            self.assertEqual(_session(root, CLAUDECODE="1"), 1)
            self.assertEqual(_session(root, OTHER_HOST_VAR="1"), 0)


class TestAnInvalidDeclaration(unittest.TestCase):
    def test_validate_fails_naming_the_key(self):
        # Scenario "An invalid declaration".
        for name, manifest in INVALID:
            with self.subTest(value=name), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp, manifest)
                r = _gates(root, "validate")
                self.assertNotEqual(r.returncode, 0, r.stdout)
                self.assertIn("discipline.agent-env", r.stdout + r.stderr)

    def test_validate_accepts_a_list_of_names(self):
        # Fails if the check rejected the shape it exists to admit.
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, DECLARED_TWO)
            r = _gates(root, "validate")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_session_check_falls_back_to_the_default_and_says_so(self):
        # Fails if a malformed declaration made the check error out (every
        # hook would then deny, a human's commit included) or read the bad
        # value as a list of one name. It decides by `[CLAUDECODE]` and names
        # the key on stderr.
        with tempfile.TemporaryDirectory() as tmp:
            root = _repo(tmp, INVALID[0][1])
            other = _gates(root, "discipline", "agent-session", OTHER_HOST_VAR="1")
            self.assertEqual(other.returncode, 1, other.stderr)
            self.assertIn("discipline.agent-env", other.stderr)
            self.assertEqual(_session(root, CLAUDECODE="1"), 0)


if __name__ == "__main__":
    unittest.main()
