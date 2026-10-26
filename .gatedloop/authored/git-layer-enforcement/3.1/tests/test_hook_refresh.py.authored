"""`gates hook install` refreshes its own stale direct copy
(openspec change `adoption-followups`, design D3; loop-enforcement delta), of
either git-layer hook (`git-layer-enforcement`, design D2 and D4).

A copy is stale when its body, with the recorded shim-path line normalized,
differs from the shipped template — or when the shim path it records no
longer exists and neither the plugin root nor PATH resolves the shim.

Stdlib only, per `zero-dep-shim`. Black-box: the shim runs as a subprocess
in throwaway git repos, the way gates-init calls it, in an environment where
only a recorded path could resolve the shim. Nothing here touches this
repository's own `.git/hooks`.

Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import (EDITED_COPY, FOREIGN_HOOK, GATES_SHIM, OLDER_COPY,  # noqa: E402
                           OLDER_PUSH_COPY, PUSH_TEMPLATE, TEMPLATE, default_hook,
                           env_without_gates, init_repo, normalized, recorded_path,
                           with_recorded, write_hook)

COPIES = (("pre-commit", TEMPLATE, OLDER_COPY), ("pre-push", PUSH_TEMPLATE, OLDER_PUSH_COPY))


def _install(root):
    return subprocess.run([sys.executable, str(GATES_SHIM), "hook", "install"], cwd=root,
                          capture_output=True, text=True, timeout=60, env=env_without_gates())


def _backup(root, name="pre-commit"):
    return root / ".git" / "hooks" / f"{name}.gatedloop-prev"


class TestRefreshAStaleCopy(unittest.TestCase):
    """Scenario "A stale direct copy is present": back up, replace, keep it
    executable, name both paths, exit 0 — for either hook."""

    def test_stale_copy_is_replaced_and_backed_up(self):
        # Fails if the installer still answered "already installed" for an
        # older copy: the defect that made the upgrade's refresh a no-op.
        for name, template, older in COPIES:
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_repo(root)
                write_hook(default_hook(root, name), older)
                result = _install(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                body = default_hook(root, name).read_text()
                self.assertEqual(normalized(body), template.read_text())
                self.assertEqual(recorded_path(body), str(GATES_SHIM.resolve()))
                self.assertEqual(_backup(root, name).read_text(), older)

    def test_refreshed_hook_stays_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_hook(default_hook(root), OLDER_COPY)
            self.assertEqual(_install(root).returncode, 0)
            self.assertTrue(default_hook(root).stat().st_mode & 0o100,
                            "the hook must stay executable")

    def test_message_names_the_hook_and_the_backup(self):
        # D3 step 3: an adopter whose local edit was replaced is told where
        # it went.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_hook(default_hook(root), EDITED_COPY)
            result = _install(root)
            hook_path, backup_path = str(default_hook(root)), str(_backup(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(hook_path, result.stdout)
        self.assertIn(backup_path, result.stdout)

    def test_second_refresh_overwrites_the_backup(self):
        # D3 step 1: the backup holds the last replaced body, not the first.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_hook(default_hook(root), OLDER_COPY)
            self.assertEqual(_install(root).returncode, 0)
            write_hook(default_hook(root), EDITED_COPY)
            second = _install(root)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(_backup(root).read_text(), EDITED_COPY)
            self.assertEqual(normalized(default_hook(root).read_text()), TEMPLATE.read_text())

    def test_a_copy_whose_recorded_shim_is_gone_is_refreshed_with_the_current_path(self):
        # Scenario "The recorded shim path is gone": the body is current, but
        # the one path that would find the shim outside a plugin no longer
        # exists, so the hook could never enforce. The refresh records the
        # installing shim instead.
        for name, template, _older in COPIES:
            with self.subTest(hook=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_repo(root)
                gone = with_recorded(template.read_text(), Path(tmp) / "moved" / "bin" / "gates")
                write_hook(default_hook(root, name), gone)
                result = _install(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(recorded_path(default_hook(root, name).read_text()),
                                 str(GATES_SHIM.resolve()))
                self.assertEqual(_backup(root, name).read_text(), gone)


class TestNothingElseIsReplaced(unittest.TestCase):
    """The no-clobber requirement still holds for everything that is not
    gatedloop's own stale copy: no rewrite, and no backup either."""

    def test_current_copy_is_nothing_to_do(self):
        # Scenario "A current direct copy is present": the shipped body, its
        # recorded path empty or naming a shim that exists.
        for label, body in (("empty path", TEMPLATE.read_text()),
                            ("existing path", with_recorded(TEMPLATE.read_text(), GATES_SHIM))):
            with self.subTest(copy=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                init_repo(root)
                write_hook(default_hook(root), body)
                result = _install(root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("nothing to do", result.stdout)
                self.assertEqual(default_hook(root).read_text(), body)
                self.assertFalse(_backup(root).exists(), "a current copy must not be backed up")

    def test_foreign_hook_is_still_refused_and_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_hook(default_hook(root), FOREIGN_HOOK)
            result = _install(root)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertEqual(default_hook(root).read_text(), FOREIGN_HOOK)
            self.assertFalse(_backup(root).exists())


if __name__ == "__main__":
    unittest.main()
