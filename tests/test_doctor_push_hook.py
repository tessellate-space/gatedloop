"""`gates doctor`'s `git-push-hook` row (change `git-layer-enforcement`,
design D2 and D4).

The push hook is diagnosed in the commit hook's vocabulary: `wired`,
`stale-copy`, `manager-uncomposed`, `unmanaged-hook`, `absent`. A hook is
also `stale-copy` when the shim path it records is gone and neither the
plugin root nor PATH resolves the shim — it would never find the shim
outside a plugin environment.

The regressions caught here: a push-hook shape classified as another state
(the wrong remedy printed), the recorded-path case read as wired, the row
missing from the doctor or blocking it, and a fresh install not reported
wired for both hooks.

The state primitive runs on real throwaway repositories, with the process
environment patched so no plugin root or `gates` on PATH resolves the shim;
the row is tested as a pure function on that primitive; one end-to-end run
of `gates doctor` checks both rows after a real `gates hook install`.

Stdlib only, per `zero-dep-shim`. Run with: python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import (FOREIGN_HOOK, GATES_SHIM, OLDER_PUSH_COPY, PUSH_TEMPLATE,  # noqa: E402
                           REPO, TEMPLATE, composed_husky_hook, default_hook,
                           env_without_gates, init_repo, with_recorded, write_hook)

_loader = importlib.machinery.SourceFileLoader("gates_shim_doctor_push_hook", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

STATES = ("wired", "stale-copy", "manager-uncomposed", "unmanaged-hook", "absent")


class PushHookStateTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, env_without_gates(), clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def state_with(self, setup, hook="pre-push"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            setup(root)
            return gates._hook_state(root, hook)

    def test_each_shape_has_its_state(self):
        # Fails if a shape were classified as another state, so the doctor
        # printed the wrong remedy (or none) for the push hook.
        cases = (
            ("wired", lambda r: write_hook(default_hook(r, "pre-push"), PUSH_TEMPLATE.read_text())),
            ("stale-copy", lambda r: write_hook(default_hook(r, "pre-push"), OLDER_PUSH_COPY)),
            # husky owns the path; only the commit hook has our block in it.
            ("manager-uncomposed",
             lambda r: composed_husky_hook(r, gates._composed_hook_snippet())),
            ("unmanaged-hook", lambda r: write_hook(default_hook(r, "pre-push"), FOREIGN_HOOK)),
            ("absent", lambda r: None),
        )
        for state, setup in cases:
            with self.subTest(state=state):
                self.assertEqual(self.state_with(setup), state)

    def test_a_recorded_shim_that_is_gone_is_stale_unless_something_else_resolves(self):
        # Scenario "The recorded shim path is gone", for both hooks.
        for name, template in (("pre-commit", TEMPLATE), ("pre-push", PUSH_TEMPLATE)):
            def setup(r, name=name, template=template):
                write_hook(default_hook(r, name),
                           with_recorded(template.read_text(), Path(r) / "moved" / "gates"))
            with self.subTest(hook=name):
                self.assertEqual(self.state_with(setup, name), "stale-copy")
            with self.subTest(hook=name, plugin_root="set"), \
                    mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO)}):
                self.assertEqual(self.state_with(setup, name), "wired")


class PushHookRowTest(unittest.TestCase):
    def rows(self, state):
        return [c for c in gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p", None,
                                               push_hook_state=state)
                if c[1] == "git-push-hook"]

    def test_wired_is_ok_and_every_other_state_warns_naming_hook_install(self):
        for state in STATES:
            with self.subTest(state=state):
                rows = self.rows(state)
                self.assertEqual(len(rows), 1)
                level, _title, detail = rows[0]
                if state == "wired":
                    self.assertEqual(level, "ok")
                else:
                    self.assertEqual(level, "warn")
                    self.assertIn("gates hook install", detail)

    def test_omitted_when_not_checked(self):
        self.assertEqual(self.rows(None), [])


class DoctorEndToEndTest(unittest.TestCase):
    def test_a_fresh_install_reports_both_hooks_wired(self):
        # Scenario "A fresh install".
        def doctor(root):
            r = subprocess.run([sys.executable, str(GATES_SHIM), "doctor"], cwd=root,
                               capture_output=True, text=True, env=env_without_gates(),
                               timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            return {title: line for line in r.stdout.splitlines()
                    for title in ("git-commit-hook", "git-push-hook") if f"] {title}:" in line}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            self.assertIn("[WARN]", doctor(root)["git-push-hook"])
            install = subprocess.run([sys.executable, str(GATES_SHIM), "hook", "install"],
                                     cwd=root, capture_output=True, text=True,
                                     env=env_without_gates(), timeout=60)
            self.assertEqual(install.returncode, 0, install.stderr)
            rows = doctor(root)
            for title in ("git-commit-hook", "git-push-hook"):
                with self.subTest(row=title):
                    self.assertIn("[ok  ]", rows[title])


if __name__ == "__main__":
    unittest.main()
