"""Both commit hooks under `loop.ci-at: ready` (openspec change `ci-at`,
design D3; the gate-binding delta's "Both commit layers apply the same commit
check" requirement).

The regressions: either layer refusing a commit the check allowed on a `unit`
marker, or skipping the authored-test lock for it; the tool layer staying
silent about the mode, so nothing a reader sees says a full `ci` is still
owed; a denial that sends a `ready` loop back to `gates run ci`; and the tool
layer's output on an ordinary `ci`-marker commit changing.

Real hooks driven against real repositories: the tool-level hook reads its
command from stdin and the git-layer hook is the shipped template.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
TOOL_HOOK = REPO / "hooks" / "gate-commit.sh"
GIT_HOOK = REPO / "templates" / "git-hooks" / "pre-commit"

CHANGE = "demo-change"
BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
READY = BASE + "loop:\n  ci-at: ready\n"
TEST_REL = "tests/test_calc.py"
TEST_V1 = "def test_add():\n    assert add(2, 3) == 5\n"
MODE_LINE = "loop.ci-at: ready"


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDECODE"] = "1"
    return env


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=_env())


def _gates(root, *args):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=_env(), timeout=120)


def _tool_hook(root):
    return subprocess.run(
        ["bash", str(TOOL_HOOK)], cwd=root, env=_env(), capture_output=True, text=True,
        input=json.dumps({"tool_input": {"command": "git commit -m x"}, "cwd": str(root)}),
    )


def _git_hook(root):
    return subprocess.run(["bash", str(GIT_HOOK)], cwd=root, env=_env(),
                          capture_output=True, text=True)


HOOKS = (("tool", _tool_hook), ("git", _git_hook))


def _repo(tmp, manifest=READY) -> Path:
    root = Path(tmp)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    change_dir = root / "openspec" / "changes" / CHANGE
    change_dir.mkdir(parents=True)
    (change_dir / ".openspec.yaml").write_text("schema: spec-driven\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "checkout", "-q", "-b", CHANGE)
    return root


def _stage_code(root):
    (root / "src.py").write_text("def add(a, b):\n    return a + b\n")
    _git(root, "add", "src.py")


def _run(root, gate):
    r = _gates(root, "run", gate)
    assert r.returncode == 0, r.stdout + r.stderr
    _git(root, "add", "-A")


class UnitGatedCommitTest(unittest.TestCase):
    def test_both_layers_allow_it_and_print_the_mode(self):
        for name, hook in HOOKS:
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp)
                _stage_code(root)
                _run(root, "unit")

                r = hook(root)

                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("'unit' marker matches", r.stdout)
                self.assertIn(MODE_LINE, r.stdout)

    def test_both_layers_run_the_authored_test_lock_after_it(self):
        """Task 1.1's tests are placed and only a green `unit` ran after the
        placement: the lock wants a red run, so both layers deny."""
        for name, hook in HOOKS:
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp)
                held = root / ".gatedloop" / "authored" / CHANGE / "1.1" / f"{TEST_REL}.authored"
                held.parent.mkdir(parents=True)
                held.write_text(TEST_V1)
                for args in (("tests", "handoff", CHANGE), ("task", "start", "1.1"),
                             ("tests", "place", "1.1")):
                    p = _gates(root, *args)
                    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                _stage_code(root)
                _git(root, "add", "-A")
                _run(root, "unit")
                self.assertNotEqual(_gates(root, "tests", "check").returncode, 0)

                r = hook(root)

                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("authored tests are locked", r.stderr)

    def test_both_layers_deny_with_no_marker_naming_unit_and_a_neutral_remedy(self):
        for name, hook in HOOKS:
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp)
                _stage_code(root)

                r = hook(root)

                self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("gates run unit", r.stderr)
                self.assertIn("run the gate named above", r.stderr)
                self.assertNotIn("run `gates run ci` and stage exactly", r.stderr)


class CiMarkerOutputTest(unittest.TestCase):
    def test_the_tool_layer_prints_nothing_on_a_ci_marker_commit(self):
        for manifest in (READY, BASE):
            with self.subTest(ready=manifest == READY), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp, manifest)
                _stage_code(root)
                _run(root, "ci")

                r = _tool_hook(root)

                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")
                self.assertEqual(r.stderr, "")

    def test_a_denial_under_task_names_the_gate_neutral_remedy(self):
        for name, hook in HOOKS:
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = _repo(tmp, BASE)
                _stage_code(root)

                r = hook(root)

                self.assertNotEqual(r.returncode, 0)
                self.assertIn("gates run ci", r.stderr)
                self.assertIn("run the gate named above", r.stderr)


if __name__ == "__main__":
    unittest.main()
