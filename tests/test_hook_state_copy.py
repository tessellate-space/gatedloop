"""A direct copy of the git hook template, and whether it is current
(openspec change `adoption-followups`, design D1 and D7).

Stdlib only, per `zero-dep-shim`. Every case runs in a throwaway git repo;
nothing here touches this repository's own `.git/hooks`.

Run with:  python3 -m unittest discover -s tests
"""

import importlib.machinery
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import (EDITED_COPY, FOREIGN_HOOK, GATES_SHIM, OLDER_COPY,  # noqa: E402
                           TEMPLATE, composed_husky_hook, default_hook, init_repo, write_hook)

_loader = importlib.machinery.SourceFileLoader("gates_shim_hook_state_copy", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


class TestHookStateRecognizesACopy(unittest.TestCase):
    """D1: a file with the template header and no composed-block marker is a
    direct copy; it is current only when its bytes equal the shipped
    template. D7: `_hook_state` names a copy that is not current."""

    def state_with(self, setup):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            setup(root)
            return gates._hook_state(root)

    def test_current_copy_is_wired(self):
        # Fails if a byte-identical copy were read as stale, which would nag
        # every adopter who already has the shipped template.
        self.assertEqual(
            self.state_with(lambda r: write_hook(default_hook(r), TEMPLATE.read_bytes())), "wired")

    def test_earlier_or_edited_copy_is_stale(self):
        # Fails if a copy that differs from the shipped template still read as
        # "wired": the refresh would never be offered, the 0.5.0 defect this
        # change closes. D1 compares bytes, so a local edit counts too.
        for body in (OLDER_COPY, EDITED_COPY):
            with self.subTest(body=body.splitlines()[-2]):
                self.assertEqual(self.state_with(lambda r: write_hook(default_hook(r), body)),
                                 "stale-copy")

    def test_composed_husky_hook_is_wired(self):
        # Fails if a composed block were taken for a copy: it delegates to the
        # shipped template at run time and is never stale.
        self.assertEqual(
            self.state_with(lambda r: composed_husky_hook(r, gates._composed_hook_snippet())),
            "wired")

    def test_foreign_bare_hook_is_unmanaged(self):
        self.assertEqual(self.state_with(lambda r: write_hook(default_hook(r), FOREIGN_HOOK)),
                         "unmanaged-hook")

    def test_no_hook_is_absent(self):
        self.assertEqual(self.state_with(lambda r: None), "absent")


class TestDoctorWarnsOnAStaleCopy(unittest.TestCase):
    """D7: the doctor's hook row warns on a stale copy and names the fix; it
    stays advisory like every doctor row."""

    def test_stale_copy_warns_naming_hook_install(self):
        rows = [c for c in gates.doctor_checks(gates.TESTED_OPENSPEC_VERSION, 1, "/p", "stale-copy")
                if c[1] == "git-commit-hook"]
        self.assertEqual(len(rows), 1)
        level, _title, detail = rows[0]
        self.assertEqual(level, "warn")
        self.assertIn("gates hook install", detail)


if __name__ == "__main__":
    unittest.main()
