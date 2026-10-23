"""`gates integration` tests -- the one source `skills/tdd-apply/SKILL.md`
§7.5 reads to pick a merge strategy without hand-parsing `.gates.yaml`
(reconciling the loop with `onboarding-asks-first` §5's declared process).

Stdlib only, per `zero-dep-shim`.

Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"


def _run_gates(root, *args):
    return subprocess.run(
        [sys.executable, str(GATES_SHIM), *args],
        cwd=root, capture_output=True, text=True,
    )


def _write_manifest(root: Path, text: str):
    (root / ".gates.yaml").write_text(text)


class TestIntegrationDeclaration(unittest.TestCase):
    def test_absent_integration_means_local_squash_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "gatesVersion: 1\ngates:\n  ci: \"true\"\n")
            result = _run_gates(root, "integration")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("mode=local-squash-merge", result.stdout)
            self.assertIn("requireApproval=false", result.stdout)

    def test_pull_request_no_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, (
                "gatesVersion: 1\ngates:\n  ci: \"true\"\n"
                "integration:\n  mode: pull-request\n"
            ))
            result = _run_gates(root, "integration")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("mode=pull-request", result.stdout)
            self.assertIn("requireApproval=false", result.stdout)

    def test_pull_request_with_required_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, (
                "gatesVersion: 1\ngates:\n  ci: \"true\"\n"
                "integration:\n  mode: pull-request\n  requireApproval: true\n"
            ))
            result = _run_gates(root, "integration")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("mode=pull-request", result.stdout)
            self.assertIn("requireApproval=true", result.stdout)


if __name__ == "__main__":
    unittest.main()
