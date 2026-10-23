"""End-to-end: `gates schema dispatch` on a machine without PyYAML
(schema-declared-flow task 3.3, issue #32).

Each case runs the real shim in a subprocess whose `import yaml` raises
ImportError, against a temporary project holding project-local schemas. It
guards the two regressions #32 reported on the dispatch path: a fork of the
bugfix pack under another name falling through to the per-task loop, and
`tdd-apply` failing at dispatch because the only route decision needed PyYAML.

Stdlib only. Run with:  python3 -m unittest discover -s tests
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

# Run the shim as __main__ with PyYAML made unimportable.
_NO_YAML_RUNNER = (
    "import runpy, sys; sys.modules['yaml'] = None; "
    "sys.argv = ['gates'] + sys.argv[1:]; "
    f"runpy.run_path({str(GATES_SHIM)!r}, run_name='__main__')"
)

FORK = """\
name: acme-bugfix
version: 1
description: Our fork of the bugfix pack, with our own report template.
artifacts:
  - id: report
    generates: report.md
    template: report.md
    instruction: >
      Capture the bug as something that runs.
    requires: []
  - id: tasks
    generates: tasks.md
    requires:
      - report
apply:
  requires:
    - tasks
  tracks: tasks.md
  instruction: |
    Run the reproduction red first.
gatedloop:
  flow: regression-first
"""

EPIC = """\
name: epic
version: 1
description: An epic groups changes and is never implemented itself.
artifacts:
  - id: epic
    generates: epic.md
    requires: []
apply:
  requires: [epic]
  instruction: |
    An epic is never implemented.
"""


class TestDispatchWithoutPyYAML(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.project = Path(cls._tmp.name)
        for name, text in (("acme-bugfix", FORK), ("epic", EPIC)):
            d = cls.project / "openspec" / "schemas" / name
            d.mkdir(parents=True)
            (d / "schema.yaml").write_text(text)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _dispatch(self, *argv):
        return subprocess.run(
            [sys.executable, "-c", _NO_YAML_RUNNER, "schema", "dispatch", *argv, "--json"],
            cwd=self.project, capture_output=True, text=True, timeout=60,
        )

    def test_pyyaml_is_really_hidden(self):
        out = subprocess.run(
            [sys.executable, "-c", "import sys; sys.modules['yaml'] = None\n"
             "try:\n import yaml\nexcept ImportError:\n print('hidden')"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(out.stdout.strip(), "hidden")

    def test_fork_under_another_name_routes_regression_first(self):
        r = self._dispatch("--path", "openspec/schemas/acme-bugfix")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["route"], "regression-first")

    def test_apply_without_tracks_refuses_with_exit_zero(self):
        r = self._dispatch("--path", "openspec/schemas/epic")
        self.assertEqual(r.returncode, 0, r.stderr)
        obj = json.loads(r.stdout)
        self.assertEqual(obj["route"], "refuse")
        self.assertTrue(obj["has_apply"])
        self.assertFalse(obj["implementable"])

    def test_unrecognised_shape_fails_loud_not_absent(self):
        d = self.project / "openspec" / "schemas" / "odd"
        d.mkdir(parents=True, exist_ok=True)
        (d / "schema.yaml").write_text("name: odd\napply: {tracks: tasks.md}\n")
        r = self._dispatch("--path", "openspec/schemas/odd")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")
        self.assertIn("line 2", r.stderr)

    def test_fork_resolved_by_name_through_openspec(self):
        if shutil.which("openspec") is None:
            self.skipTest("OpenSpec CLI not on PATH; name resolution needs `openspec schema which`")
        r = self._dispatch("acme-bugfix")
        self.assertEqual(r.returncode, 0, r.stderr)
        obj = json.loads(r.stdout)
        self.assertEqual((obj["schema"], obj["route"]), ("acme-bugfix", "regression-first"))


if __name__ == "__main__":
    unittest.main()
