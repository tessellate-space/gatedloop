"""The plugin is `gatedloop`, and the earlier name is a forwarder (change
`rename-to-gatedloop`, design D4 and its task-1.1 spike result).

Claude Code installs a plugin as `<entry name>@<marketplace>`, and an
existing `specloop@specloop` install keeps resolving the entry named
`specloop` in the marketplace it was added from, even after that
marketplace's own name changes (the spike). So the marketplace lists two
entries: `gatedloop`, the plugin, and `specloop`, a forwarder whose only
content is a SessionStart notice and a stub for each former command. The
regressions these tests catch:

- an entry whose source directory is missing, or whose `plugin.json` names a
  different plugin than the entry (Claude Code then reports "not found in
  marketplace" -- the docs' rule, and what the spike saw without a forwarder);
- a forwarder that runs anything beyond its notice, so the loop keeps working
  under the old name without the adopter ever seeing it;
- a notice that sends an existing adopter to an install id that cannot
  resolve from their registration (`gatedloop@gatedloop` needs the new
  marketplace added first -- spike finding 4);
- a former command with no stub, which a typed `/specloop:<name>` then
  reaches as "unknown command" instead of the notice;
- a forwarder version that drifts from the plugin's, so `claude plugin
  update specloop@specloop` never moves an existing install onto it.

Stdlib only, per `zero-dep-shim`. The release script is loaded by path, the
way `test_release.py` loads it. Every repository is a throwaway one.

Run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
FORWARDER = REPO / "forwarder" / "specloop"
RELEASE_SCRIPT = REPO / "scripts" / "release"

_loader = importlib.machinery.SourceFileLoader("release_script_forwarder", str(RELEASE_SCRIPT))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
release = importlib.util.module_from_spec(_spec)
_loader.exec_module(release)

# Every `/specloop:<name>` the 0.6.0 plugin answered: its six commands and
# its four skills (a plugin skill is invocable by the same namespace). This
# is the fixed historical set; a command added after the rename never
# existed under the earlier name and needs no stub.
FORMER_COMMANDS = ("archive", "gates-init", "merge", "propose", "start", "upgrade",
                   "feedback", "tdd-apply", "verify", "workflow-select")


def _env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    env.update(extra)
    return env


def _entries() -> dict:
    data = json.loads(MARKETPLACE.read_text())
    return {e["name"]: e for e in data["plugins"]}


def _session_start_notice() -> str:
    """Run the forwarder's SessionStart hook the way Claude Code does (its
    hooks.json command, with CLAUDE_PLUGIN_ROOT set) and return the
    user-facing message it prints."""
    hooks = json.loads((FORWARDER / "hooks" / "hooks.json").read_text())["hooks"]
    commands = [h["command"] for group in hooks["SessionStart"] for h in group["hooks"]]
    assert len(commands) == 1, commands
    with tempfile.TemporaryDirectory() as project:
        r = subprocess.run(["bash", "-c", commands[0]], cwd=project, capture_output=True,
                           text=True, env=_env(CLAUDE_PLUGIN_ROOT=str(FORWARDER),
                                               CLAUDE_PROJECT_DIR=project), timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["systemMessage"]


class TestMarketplaceResolvesBothInstallIds(unittest.TestCase):
    def test_each_entry_resolves_to_a_plugin_of_its_own_name(self):
        data = json.loads(MARKETPLACE.read_text())
        self.assertEqual(data["name"], "gatedloop")
        entries = _entries()
        for name, source in (("gatedloop", "./"), ("specloop", "./forwarder/specloop")):
            with self.subTest(name):
                self.assertIn(name, entries)
                self.assertEqual(entries[name]["source"], source)
                manifest = (REPO / source / ".claude-plugin" / "plugin.json").resolve()
                self.assertTrue(manifest.is_file(), f"no plugin.json under {source}")
                self.assertEqual(json.loads(manifest.read_text())["name"], name)


class TestForwarderRunsOnlyItsNotice(unittest.TestCase):
    def test_the_notice_names_the_steps_an_existing_install_can_follow(self):
        notice = _session_start_notice()
        # Order matters: the new marketplace must be added before its
        # install id resolves (spike finding 4).
        steps = ["/plugin marketplace add tessellate-space/gatedloop",
                 "/plugin install gatedloop@gatedloop",
                 "/plugin uninstall specloop@specloop",
                 "gates migrate-name"]
        positions = [notice.find(s) for s in steps]
        self.assertNotIn(-1, positions, notice)
        self.assertEqual(positions, sorted(positions), notice)

    def test_the_forwarder_carries_no_loop(self):
        hooks = json.loads((FORWARDER / "hooks" / "hooks.json").read_text())["hooks"]
        self.assertEqual(set(hooks), {"SessionStart"})
        for absent in ("bin", "skills", "agents"):
            self.assertFalse((FORWARDER / absent).exists(), f"forwarder ships {absent}/")

    def test_every_former_command_answers_with_the_notice(self):
        notice = _session_start_notice()
        stubs = {p.stem for p in (FORWARDER / "commands").glob("*.md")}
        self.assertEqual(stubs, set(FORMER_COMMANDS))
        for name in FORMER_COMMANDS:
            with self.subTest(name):
                self.assertIn(notice, (FORWARDER / "commands" / f"{name}.md").read_text())


class TestForwarderVersionMovesWithThePlugin(unittest.TestCase):
    def _copy(self, root: Path) -> None:
        (root / ".claude-plugin").mkdir()
        for name in ("plugin.json", "marketplace.json"):
            shutil.copy(REPO / ".claude-plugin" / name, root / ".claude-plugin" / name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, env=_env())
        subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com",
                        "commit", "-q", "--allow-empty", "-m", "init"],
                       cwd=root, check=True, env=_env())

    def test_a_forwarder_version_that_disagrees_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy(root)
            market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())
            for entry in market["plugins"]:
                if entry["name"] == "specloop":
                    entry["version"] = "9.9.9"
            (root / ".claude-plugin" / "marketplace.json").write_text(json.dumps(market))

            with self.assertRaises(release.ReleaseError) as caught:
                release.check_version(root)
            self.assertIn("plugins[specloop].version: 9.9.9", str(caught.exception))

    def test_a_cut_bumps_the_forwarder_with_the_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy(root)
            current = release.check_version(root)

            rewritten = release.bump_fields(root, current, "99.0.0")

            market = json.loads(rewritten[".claude-plugin/marketplace.json"])
            versions = {e["name"]: e.get("version") for e in market["plugins"]}
            self.assertEqual(versions, {"gatedloop": "99.0.0", "specloop": "99.0.0"})


if __name__ == "__main__":
    unittest.main()
