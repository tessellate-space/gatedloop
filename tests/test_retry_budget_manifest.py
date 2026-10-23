"""`loop.attempts` and `loop.fresh-restarts` in `.gates.yaml` (openspec change
`retry-budget`, design D5; the retry-budget delta's "The budget is declared
in the manifest" requirement).

Stdlib only, per `zero-dep-shim`. `gates validate` is driven as a subprocess
against a throwaway project directory; the effective budget is read through
the shim's pure `loop_budget(manifest)`.

Run with:  python3 -m unittest discover -s tests
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

_loader = importlib.machinery.SourceFileLoader("gates_shim_retry_budget_manifest", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

BASE = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _validate(loop_block: str):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True,
                       capture_output=True, env=_env())
        (root / ".gates.yaml").write_text(BASE + loop_block)
        return subprocess.run(
            [sys.executable, str(GATES_SHIM), "validate"], cwd=root,
            capture_output=True, text=True, env=_env(), timeout=60,
        )


class TestBudgetDefaults(unittest.TestCase):
    def test_no_loop_block_means_two_attempts_and_one_restart(self):
        self.assertEqual(gates.loop_budget({"gates": {"ci": "true"}}), (2, 1))

    def test_declared_values_are_used(self):
        m = {"loop": {"attempts": 3, "fresh-restarts": 0}}
        self.assertEqual(gates.loop_budget(m), (3, 0))

    def test_one_key_declared_keeps_the_other_default(self):
        self.assertEqual(gates.loop_budget({"loop": {"attempts": 5}}), (5, 1))
        self.assertEqual(gates.loop_budget({"loop": {"fresh-restarts": 0}}), (2, 0))


class TestBudgetValidation(unittest.TestCase):
    def test_declared_budget_is_valid(self):
        r = _validate("loop:\n  attempts: 3\n  fresh-restarts: 2\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_negative_attempts_fails_naming_the_key(self):
        r = _validate("loop:\n  attempts: -1\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("loop.attempts", r.stderr)

    def test_non_integer_attempts_fails_naming_the_key(self):
        for value in ('"two"', "2.5", "true"):
            with self.subTest(value=value):
                r = _validate(f"loop:\n  attempts: {value}\n")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("loop.attempts", r.stderr)

    def test_negative_fresh_restarts_fails_naming_the_key(self):
        r = _validate("loop:\n  fresh-restarts: -2\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("loop.fresh-restarts", r.stderr)

    def test_non_integer_fresh_restarts_fails_naming_the_key(self):
        r = _validate('loop:\n  fresh-restarts: "one"\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn("loop.fresh-restarts", r.stderr)

    def test_zero_attempts_is_valid_but_warns(self):
        r = _validate("loop:\n  attempts: 0\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("loop.attempts", r.stderr)
        self.assertIn("warning", r.stderr.lower())

    def test_zero_fresh_restarts_is_valid_without_warning(self):
        r = _validate("loop:\n  fresh-restarts: 0\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("warning", r.stderr.lower())


if __name__ == "__main__":
    unittest.main()
