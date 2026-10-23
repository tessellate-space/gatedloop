"""The shipped `git-hook-refresh` and `confirm-gate` items, end to end through
`gates adoption status` (openspec change `adoption-followups`, design D5/D6;
the upgrade-adoption delta's added requirements).

Stdlib only, per `zero-dep-shim`. These sit at the CLI layer on purpose: what
is under test is the *shipped catalogue's* entries meeting the real fact
gathering, which no pure test of an evaluator can observe. The shim resolves
its catalogue, plugin.json and hook template from its own location, so a copy
of it in a scratch plugin directory, beside the shipped catalogue and
template, reads exactly what an adopter's install reads. Every project is a
throwaway git repo; nothing here touches this repository's own `.git/hooks`.

Run with:  python3 -m unittest discover -s tests
"""

import contextlib
import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_fixture import (GATES_SHIM, OLDER_COPY, REPO, TEMPLATE,  # noqa: E402
                           composed_husky_hook, default_hook, write_hook)

_loader = importlib.machinery.SourceFileLoader("gates_shim_followup_items", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)

LIVE_CHECK = ('gatesVersion: 1\ngates:\n  ci: "true"\nsurfaces:\n'
              '  - name: app\n    match: "**"\n    live-check: "probe"\n')


@contextlib.contextmanager
def installed(version="0.5.0", manifest=None):
    with tempfile.TemporaryDirectory() as tmp:
        plugin, project = Path(tmp) / "plugin", Path(tmp) / "project"
        (plugin / "bin").mkdir(parents=True)
        shutil.copy(GATES_SHIM, plugin / "bin" / "gates")
        (plugin / "adoption").mkdir()
        shutil.copy(REPO / "adoption" / "catalog.json", plugin / "adoption" / "catalog.json")
        (plugin / "templates" / "git-hooks").mkdir(parents=True)
        shutil.copy(TEMPLATE, plugin / "templates" / "git-hooks" / "pre-commit")
        (plugin / ".claude-plugin").mkdir()
        set_version(plugin, version)
        project.mkdir()
        for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Test"),
                     ("config", "user.email", "test@example.com")):
            subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)
        if manifest is not None:
            (project / ".gates.yaml").write_text(manifest)
        yield plugin, project


def set_version(plugin, version):
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))


def run_gates(plugin, project, *args):
    return subprocess.run([sys.executable, str(plugin / "bin" / "gates"), *args], cwd=project,
                          capture_output=True, text=True, timeout=60)


def listed(plugin, project):
    result = run_gates(plugin, project, "adoption", "status", "--json")
    if result.returncode != 0:
        raise AssertionError(f"status exited {result.returncode}: {result.stderr}")
    return [i["id"] for i in json.loads(result.stdout)["undecided"]]


def record(plugin, project, item_id, decision):
    result = run_gates(plugin, project, "adoption", "record", item_id, decision)
    if result.returncode != 0:
        raise AssertionError(f"record exited {result.returncode}: {result.stderr}")


class TestGitHookRefreshListing(unittest.TestCase):
    """Requirement "A stale copy of the git hook is offered for refresh"."""

    def test_stale_copy_lists_it(self):
        # Scenario "The installed copy predates the shipped template".
        with installed() as (plugin, project):
            write_hook(default_hook(project), OLDER_COPY)
            self.assertIn("git-hook-refresh", listed(plugin, project))

    def test_a_delegating_hook_or_none_does_not_list_it(self):
        # Scenario "The hook delegates to the shipped template".
        setups = (("composed", lambda p: composed_husky_hook(p, gates._composed_hook_snippet())),
                  ("no hook", lambda p: None))
        for name, setup in setups:
            with self.subTest(hook=name), installed() as (plugin, project):
                setup(project)
                self.assertNotIn("git-hook-refresh", listed(plugin, project))

    def test_refreshing_the_hook_clears_it(self):
        # Scenario "The adopter refreshes the hook": the walk's action is the
        # hook-install step, and afterwards the item is gone.
        with installed() as (plugin, project):
            write_hook(default_hook(project), OLDER_COPY)
            install = run_gates(plugin, project, "hook", "install")
            self.assertEqual(install.returncode, 0, install.stderr)
            record(plugin, project, "git-hook-refresh", "adopted")
            self.assertNotIn("git-hook-refresh", listed(plugin, project))

    def test_adopted_earlier_does_not_hide_a_later_stale_copy(self):
        # The shipped item recurs: an `adopted` from 0.5.0 must not hide the
        # refresh the next template change needs.
        with installed("0.5.0") as (plugin, project):
            record(plugin, project, "git-hook-refresh", "adopted")
            set_version(plugin, "0.6.0")
            write_hook(default_hook(project), OLDER_COPY)
            self.assertIn("git-hook-refresh", listed(plugin, project))

    def test_declined_holds_only_at_its_version(self):
        with installed("0.5.0") as (plugin, project):
            write_hook(default_hook(project), OLDER_COPY)
            record(plugin, project, "git-hook-refresh", "declined")
            self.assertNotIn("git-hook-refresh", listed(plugin, project))
            set_version(plugin, "0.6.0")
            self.assertIn("git-hook-refresh", listed(plugin, project))


class TestConfirmGateListing(unittest.TestCase):
    """Requirement "The confirm gate is offered where a live-check is bound"."""

    def test_live_check_without_confirm_lists_it(self):
        # Scenario "A surface declares a live-check and no confirm gate is bound".
        with installed(manifest=LIVE_CHECK) as (plugin, project):
            self.assertIn("confirm-gate", listed(plugin, project))

    def test_no_live_check_does_not_list_it(self):
        # Scenario "No surface declares a live-check".
        manifest = 'gatesVersion: 1\ngates:\n  ci: "true"\n  verify: "v"\n'
        with installed(manifest=manifest) as (plugin, project):
            self.assertNotIn("confirm-gate", listed(plugin, project))

    def test_bound_confirm_does_not_list_it(self):
        manifest = LIVE_CHECK.replace('  ci: "true"\n', '  ci: "true"\n  confirm: "smoke"\n')
        with installed(manifest=manifest) as (plugin, project):
            self.assertNotIn("confirm-gate", listed(plugin, project))

    def test_declined_is_never_listed_again(self):
        # Not recurring: the ordinary rule applies across an upgrade.
        with installed("0.5.0", manifest=LIVE_CHECK) as (plugin, project):
            record(plugin, project, "confirm-gate", "declined")
            set_version(plugin, "0.6.0")
            self.assertNotIn("confirm-gate", listed(plugin, project))


if __name__ == "__main__":
    unittest.main()
