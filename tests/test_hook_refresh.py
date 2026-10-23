"""`gates hook install` refreshes its own stale direct copy
(openspec change `adoption-followups`, design D3; loop-enforcement delta).

Stdlib only, per `zero-dep-shim`. Black-box: the shim runs as a subprocess
in throwaway git repos, the way gates-init calls it. Nothing here touches
this repository's own `.git/hooks`.

Run with:  python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import (EDITED_COPY, FOREIGN_HOOK, GATES_SHIM, OLDER_COPY,  # noqa: E402
                           TEMPLATE, default_hook, init_repo, write_hook)


def _install(root):
    return subprocess.run([sys.executable, str(GATES_SHIM), "hook", "install"], cwd=root,
                          capture_output=True, text=True, timeout=60)


def _backup(root):
    return root / ".git" / "hooks" / "pre-commit.gatedloop-prev"


class TestRefreshAStaleCopy(unittest.TestCase):
    """Scenario "A stale direct copy is present": back up, replace, keep it
    executable, name both paths, exit 0."""

    def test_stale_copy_is_replaced_and_backed_up(self):
        # Fails if the installer still answered "already installed" for an
        # older copy: the defect that made the upgrade's refresh a no-op.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_hook(default_hook(root), OLDER_COPY)
            result = _install(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(default_hook(root).read_bytes(), TEMPLATE.read_bytes())
            self.assertEqual(_backup(root).read_text(), OLDER_COPY)

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
            self.assertEqual(default_hook(root).read_bytes(), TEMPLATE.read_bytes())


class TestNothingElseIsReplaced(unittest.TestCase):
    """The no-clobber requirement still holds for everything that is not
    gatedloop's own stale copy: no rewrite, and no backup either."""

    def test_current_copy_is_nothing_to_do(self):
        # Scenario "A current direct copy is present".
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            write_hook(default_hook(root), TEMPLATE.read_bytes())
            result = _install(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("nothing to do", result.stdout)
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
