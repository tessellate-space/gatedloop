"""`loop.ci-at` in `.gates.yaml` (openspec change `ci-at`, design D1; the
loop-enforcement delta's "When the full ci runs is declared by `loop.ci-at`"
requirement).

Stdlib only, per `zero-dep-shim`. `gates validate` is driven as a subprocess
against a throwaway project directory; the effective mode is read through the
shim's pure `_ci_at_mode(manifest)`.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_ci_at_manifest", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

CI_ONLY = 'gatesVersion: 1\ngates:\n  ci: "true"\n'
CI_AND_UNIT = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'


def _env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _validate(manifest: str):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True,
                       capture_output=True, env=_env())
        (root / ".gates.yaml").write_text(manifest)
        return subprocess.run(
            [sys.executable, str(GATES_SHIM), "validate"], cwd=root,
            capture_output=True, text=True, env=_env(), timeout=60,
        )


class TestEffectiveMode(unittest.TestCase):
    def test_absent_reads_as_task(self):
        self.assertEqual(gates._ci_at_mode({"gates": {"ci": "true"}}), "task")
        self.assertEqual(gates._ci_at_mode({"loop": {"attempts": 2}}), "task")

    def test_declared_values(self):
        self.assertEqual(gates._ci_at_mode({"loop": {"ci-at": "task"}}), "task")
        self.assertEqual(gates._ci_at_mode({"loop": {"ci-at": "ready"}}), "ready")

    def test_malformed_reads_as_task(self):
        for v in ("merge", 1, None, ["ready"]):
            with self.subTest(v=v):
                self.assertEqual(gates._ci_at_mode({"loop": {"ci-at": v}}), "task")
        self.assertEqual(gates._ci_at_mode({"loop": "ready"}), "task")


class TestValidation(unittest.TestCase):
    def test_absent_is_valid(self):
        r = _validate(CI_ONLY)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_task_is_valid_without_unit(self):
        r = _validate(CI_ONLY + "loop:\n  ci-at: task\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_ready_with_global_unit_is_valid(self):
        r = _validate(CI_AND_UNIT + "loop:\n  ci-at: ready\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_ready_without_unit_fails_naming_the_gate(self):
        r = _validate(CI_ONLY + "loop:\n  ci-at: ready\n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("loop.ci-at: ready", r.stderr)
        self.assertIn("gates.unit", r.stderr)

    def test_surface_only_unit_override_does_not_satisfy_ready(self):
        manifest = (
            CI_ONLY
            + "surfaces:\n  - name: api\n    match: \"api/**\"\n"
            + "    gates:\n      unit: \"true\"\n"
            + "loop:\n  ci-at: ready\n"
        )
        r = _validate(manifest)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("loop.ci-at: ready", r.stderr)
        self.assertIn("gates.unit", r.stderr)

    def test_unknown_value_fails_naming_key_and_values(self):
        r = _validate(CI_AND_UNIT + "loop:\n  ci-at: merge\n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("loop.ci-at", r.stderr)
        self.assertIn("'task'", r.stderr)
        self.assertIn("'ready'", r.stderr)


class TestSchema(unittest.TestCase):
    def test_schema_declares_ci_at(self):
        schema = json.loads((REPO / "schema" / "gates.schema.json").read_text())
        loop = schema["properties"]["loop"]["properties"]
        self.assertIn("ci-at", loop)
        self.assertEqual(sorted(loop["ci-at"]["enum"]), ["ready", "task"])


if __name__ == "__main__":
    unittest.main()
