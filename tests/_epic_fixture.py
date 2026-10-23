"""Shared fixtures for the `epic-linkage` tests: a throwaway git repository
holding OpenSpec changes, some naming an epic with `x-gatedloop-epic`, plus
hand-written ledger rows. Never touches this repository's own `.git`, hooks
or marker stores.

Every subprocess runs with `CLAUDECODE=1` pinned and every `GIT_*` variable
stripped, so the tests behave the same under a git hook, locally and in CI.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
HOOKS = REPO / "hooks"
BRIEF_HELPER = HOOKS / "_session_brief.py"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\napproval:\n  plan: self\n'

ARCHIVE_DATE = "2026-10-01"

# Run the shim as __main__ with PyYAML made unimportable (the technique of
# tests/test_schema_dispatch_e2e.py).
_NO_YAML_RUNNER = (
    "import runpy, sys; sys.modules['yaml'] = None; "
    "sys.argv = ['gates'] + sys.argv[1:]; "
    f"runpy.run_path({str(GATES_SHIM)!r}, run_name='__main__')"
)


def clean_env(extra: dict | None = None) -> dict:
    """The parent environment minus every `GIT_*` variable and the plugin's
    own session variables, with the agent-session marker pinned on."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDECODE"] = "1"
    for k, v in (extra or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


def git(cwd, *args) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=clean_env())
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {r.stderr}")
    return r.stdout.strip()


def load_shim(name: str = "gates_shim_epics"):
    """The shim as a module, for its pure readers."""
    loader = importlib.machinery.SourceFileLoader(name, str(GATES_SHIM))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def row(gate: str, minute: int = 0, **extra) -> dict:
    """One ledger row; `minute` orders rows in time within one hour."""
    r = {
        "ts": f"2026-10-01T10:{minute:02d}:00+00:00", "gate": gate, "exit": 0,
        "duration_ms": 0, "change": None, "task": None, "tree": None,
        "attempt": 1, "session": "agent",
    }
    r.update(extra)
    return r


class EpicRepo:
    """A git repository on `main` with a gate manifest and OpenSpec changes."""

    def __init__(self, root):
        self.root = Path(root)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "T")
        (self.root / ".gates.yaml").write_text(MANIFEST)
        self.commit("init")

    def change(self, name: str, epic: str | None = None, approved: bool = False,
               tasks: tuple[int, int] | None = None, archived: bool = False) -> Path:
        """Write a change directory, active or archived, and return it.
        `tasks` is (done, total) for its `tasks.md`."""
        base = self.root / "openspec" / "changes"
        d = base / "archive" / f"{ARCHIVE_DATE}-{name}" if archived else base / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "proposal.md").write_text(f"# {name}\n")
        meta = "schema: spec-driven\ncreated: 2026-10-01\n"
        if epic is not None:
            meta += f"x-gatedloop-epic: {epic}\n"
        if approved:
            meta += "approved_by: T <t@example.com>\n"
        (d / ".openspec.yaml").write_text(meta)
        if tasks is not None:
            done, total = tasks
            lines = [f"- [{'x' if i < done else ' '}] 1.{i + 1} step {i + 1}" for i in range(total)]
            (d / "tasks.md").write_text("## 1. Work\n\n" + "\n".join(lines) + "\n")
        return d

    def ledger(self, change: str, *rows: dict) -> None:
        path = self.root / ".gatedloop" / "runs" / f"{change}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            for r in rows:
                f.write(json.dumps(dict(r, change=change)) + "\n")

    def commit(self, msg: str = "work") -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", msg)

    def gates(self, *args, no_yaml: bool = False) -> subprocess.CompletedProcess:
        argv = ([sys.executable, "-c", _NO_YAML_RUNNER, *args] if no_yaml
                else [sys.executable, str(GATES_SHIM), *args])
        return subprocess.run(argv, cwd=self.root, capture_output=True, text=True,
                              env=clean_env(), timeout=120)

    def gates_json(self, *args) -> dict:
        r = self.gates(*args)
        if r.returncode != 0:
            raise AssertionError(f"gates {' '.join(args)} exited {r.returncode}: {r.stderr}")
        return json.loads(r.stdout)

    def hook(self, hook_name: str, command: str) -> subprocess.CompletedProcess:
        """Drive a real PreToolUse hook script with Bash tool-input JSON."""
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                   "tool_input": {"command": command}, "cwd": str(self.root)}
        return subprocess.run(
            ["bash", str(HOOKS / hook_name)], input=json.dumps(payload),
            cwd=self.root, capture_output=True, text=True, env=clean_env(), timeout=120,
        )

    def decide_all_adoption_items(self) -> None:
        """Record every adoption item as declined, so the brief carries no
        version-dependent adoption line."""
        doc = self.gates_json("adoption", "status", "--json")
        for item in doc["undecided"]:
            r = self.gates("adoption", "record", item["id"], "declined")
            if r.returncode != 0:
                raise AssertionError(r.stderr)

    def brief(self, payload: dict) -> str:
        """`hooks/_session_brief.py` over a synthesized `openspec list --json`."""
        r = subprocess.run(
            [sys.executable, str(BRIEF_HELPER)], input=json.dumps(payload),
            cwd=self.root, capture_output=True, text=True,
            env=clean_env({"CLAUDE_PLUGIN_ROOT": str(REPO)}), timeout=120,
        )
        return r.stdout
