"""The `approval-keys` adoption item and its `old-approval-keys` detector
(openspec change `openspec-1-14-compat`, design D4a; issue #39's third
request: `/gatedloop:upgrade` offers the migration).

The detector is acted on unless an active change's `.openspec.yaml` carries
an earlier-spelled approval key. The item recurs, because a change attested
by an older gatedloop on another machine can reappear after it was migrated.

Stdlib only, per `zero-dep-shim`. The pure cases run on in-memory facts; the
listing cases run the shim from a scratch plugin directory beside the
shipped catalogue, exactly as an adopter's install reads it (the technique
`test_adoption_followup_items.py` uses).

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

_loader = importlib.machinery.SourceFileLoader("gates_shim_adoption_approval_keys", str(GATES_SHIM))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
gates = importlib.util.module_from_spec(_spec)
_loader.exec_module(gates)


def _shipped_item() -> dict:
    data = json.loads((REPO / "adoption" / "catalog.json").read_text())
    items = gates.load_adoption_catalog(data)
    match = [i for i in items if i["id"] == "approval-keys"]
    assert len(match) == 1, [i["id"] for i in items]
    return match[0]


def _facts(old: list[str]) -> dict:
    return {"manifest": {}, "rules_doc": None, "schemas": [], "existing_globs": set(),
            "hook": {"copy": False, "current": False}, "old_approval_changes": old}


class TestDetector(unittest.TestCase):
    def test_known_kind(self):
        self.assertIn("old-approval-keys", gates.ADOPTION_DETECTOR_KINDS)

    def test_acted_when_no_change_carries_an_old_key(self):
        self.assertTrue(gates.adoption_detector_acted({"kind": "old-approval-keys"}, _facts([])))

    def test_not_acted_when_a_change_carries_an_old_key(self):
        self.assertFalse(gates.adoption_detector_acted({"kind": "old-approval-keys"},
                                                       _facts(["alpha"])))


class TestShippedItem(unittest.TestCase):
    def test_shape(self):
        item = _shipped_item()
        self.assertEqual(item["since"], "0.5.1")
        self.assertIs(item.get("recurs"), True)
        self.assertEqual(item["detector"], {"kind": "old-approval-keys"})
        self.assertIsNone(item["applies_when"])
        self.assertEqual(item["action"]["kind"], "confirm")
        self.assertIn("gates approval migrate", item["action"]["detail"])

    def test_pure_listing_at_0_5_1(self):
        item = _shipped_item()
        listed = gates.adoption_undecided([item], _facts(["alpha"]), {}, "0.5.1")
        self.assertEqual([i["id"] for i in listed], ["approval-keys"])
        self.assertEqual(gates.adoption_undecided([item], _facts([]), {}, "0.5.1"), [])
        # Unreleased until 0.5.1 is the installed version.
        self.assertEqual(gates.adoption_undecided([item], _facts(["alpha"]), {}, "0.5.0"), [])


@contextlib.contextmanager
def _installed(version: str):
    with tempfile.TemporaryDirectory() as tmp:
        plugin, project = Path(tmp) / "plugin", Path(tmp) / "project"
        (plugin / "bin").mkdir(parents=True)
        shutil.copy(GATES_SHIM, plugin / "bin" / "gates")
        (plugin / "adoption").mkdir()
        shutil.copy(REPO / "adoption" / "catalog.json", plugin / "adoption" / "catalog.json")
        (plugin / "templates" / "git-hooks").mkdir(parents=True)
        shutil.copy(REPO / "templates" / "git-hooks" / "pre-commit",
                    plugin / "templates" / "git-hooks" / "pre-commit")
        (plugin / ".claude-plugin").mkdir()
        (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))
        project.mkdir()
        env = _env()
        for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Test"),
                     ("config", "user.email", "test@example.com")):
            subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, env=env)
        yield plugin, project


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def _listed(plugin: Path, project: Path) -> list[str]:
    r = subprocess.run([sys.executable, str(plugin / "bin" / "gates"), "adoption", "status",
                        "--json"], cwd=project, capture_output=True, text=True, env=_env(),
                       timeout=60)
    if r.returncode != 0:
        raise AssertionError(f"status exited {r.returncode}: {r.stderr}")
    return [i["id"] for i in json.loads(r.stdout)["undecided"]]


def _change(project: Path, name: str, keys: str, archived: bool = False) -> None:
    base = project / "openspec" / "changes"
    d = base / "archive" / f"2026-01-01-{name}" if archived else base / name
    d.mkdir(parents=True)
    (d / ".openspec.yaml").write_text("schema: spec-driven\ncreated: 2026-08-19\n" + keys)


class TestListing(unittest.TestCase):
    def test_listed_when_an_active_change_carries_an_old_key(self):
        with _installed("0.5.1") as (plugin, project):
            _change(project, "alpha", "approved_by: Old\n")
            self.assertIn("approval-keys", _listed(plugin, project))

    def test_not_listed_when_every_change_is_migrated(self):
        with _installed("0.5.1") as (plugin, project):
            _change(project, "alpha", "x-gatedloop-approved-by: New\n")
            self.assertNotIn("approval-keys", _listed(plugin, project))

    def test_not_listed_for_an_archived_change(self):
        with _installed("0.5.1") as (plugin, project):
            _change(project, "alpha", "approved_by: Old\n", archived=True)
            self.assertNotIn("approval-keys", _listed(plugin, project))

    def test_not_listed_before_0_5_1(self):
        with _installed("0.5.0") as (plugin, project):
            _change(project, "alpha", "approved_by: Old\n")
            self.assertNotIn("approval-keys", _listed(plugin, project))

    def test_recurs_after_an_adopted_decision(self):
        with _installed("0.5.1") as (plugin, project):
            _change(project, "alpha", "approved_by: Old\n")
            r = subprocess.run([sys.executable, str(plugin / "bin" / "gates"), "adoption",
                                "record", "approval-keys", "adopted"], cwd=project,
                               capture_output=True, text=True, env=_env(), timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("approval-keys", _listed(plugin, project))


if __name__ == "__main__":
    unittest.main()
