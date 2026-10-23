"""Editing a file never clears gate evidence (design D3 of `hook-correctness`,
#33 item 3, #35 rule 5).

`clear-ci-marker.sh`, a `PostToolUse` hook on Write/Edit, wiped the whole
marker store on every write -- a scratch file, a planning file, another
lane's work -- although the `ci` marker is keyed on the STAGED tree and a
write never touches the index. One wipe cost a 250 s full `ci` re-run.

The test drives the plugin's own hook configuration: every hook
`hooks/hooks.json` wires to a Write tool call, in any event, runs for a
scratch-file write between a green `gates run ci` and the commit; the commit
hook must then still allow the commit on the unchanged staged tree.

Stdlib only, per `zero-dep-shim`. Run with:  python3 -m unittest discover -s tests
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
HOOKS_JSON = REPO / "hooks" / "hooks.json"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n'


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _env(root: Path) -> dict:
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    return env


def _hook_commands_for_tool(tool: str) -> list[tuple[str, str]]:
    """(event, command) for every configured hook whose matcher selects
    `tool` -- an absent matcher selects every tool."""
    config = json.loads(HOOKS_JSON.read_text())["hooks"]
    found = []
    for event, entries in config.items():
        for entry in entries:
            matcher = entry.get("matcher")
            if matcher and not re.fullmatch(matcher, tool):
                continue
            if event not in ("PreToolUse", "PostToolUse"):
                continue  # not fired by a tool call
            for hook in entry.get("hooks", []):
                found.append((event, hook["command"]))
    return found


def _run(command: str, root: Path, payload: dict):
    return subprocess.run(
        ["bash", "-c", command], input=json.dumps(payload), cwd=str(root),
        env=_env(root), capture_output=True, text=True,
    )


class TestAScratchWriteLeavesTheCommitAllowed(unittest.TestCase):
    def test_write_hooks_between_the_gate_and_the_commit_keep_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.email", "t@example.com")
            _git(root, "config", "user.name", "T")
            (root / ".gates.yaml").write_text(MANIFEST)
            _git(root, "add", "-A")
            _git(root, "commit", "-m", "init")
            (root / "work.txt").write_text("the task\n")
            _git(root, "add", "work.txt")
            ci = subprocess.run(
                [sys.executable, str(GATES_SHIM), "run", "ci"],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(ci.returncode, 0, ci.stderr)

            scratch = root / "scratch.md"
            scratch.write_text("notes\n")
            write_payload = {
                "tool_name": "Write", "cwd": str(root),
                "tool_input": {"file_path": str(scratch), "content": "notes\n"},
            }
            for event, command in _hook_commands_for_tool("Write"):
                with self.subTest(event=event, command=command):
                    r = _run(command, root, {"hook_event_name": event, **write_payload})
                    self.assertEqual(r.returncode, 0, r.stderr)

            commit = _run(
                'bash "${CLAUDE_PLUGIN_ROOT}/hooks/gate-commit.sh"', root,
                {"tool_name": "Bash", "cwd": str(root),
                 "tool_input": {"command": "git commit -m task"}},
            )
            self.assertEqual(commit.returncode, 0, commit.stderr)


if __name__ == "__main__":
    unittest.main()
