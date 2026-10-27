"""Shared fixtures for the `token-ledger` tests: the Claude Code transcript
shape the usage adapter reads (design D3), and throwaway change repositories
with a ledger to record into.

The transcript entries carry assistant text that must never reach the ledger
(`SECRET`): a usage row stores counts only. Timestamps are fixed in the past
(`at(minute)`), so a window that ends "now" always contains them.

Stdlib only, per `zero-dep-shim`.
"""

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

CHANGE = "my-change"
SESSION = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
OTHER_SESSION = "99999999-8888-7777-6666-555555555555"
MODEL_A = "model-alpha"
MODEL_B = "model-beta"
SECRET = "SECRET-TRANSCRIPT-TEXT"

MANIFEST = 'gatesVersion: 1\ngates:\n  ci: "true"\n  unit: "true"\n'
TASKS = "# Tasks\n\n- [ ] 1.1 first\n- [ ] 1.2 second\n- [ ] 1.3 third\n"


def load_shim(name):
    loader = importlib.machinery.SourceFileLoader(name, str(GATES_SHIM))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def at(minute, hour=0, day=1, second=0):
    """A fixed past instant, `2026-10-<day>T<hour>:<minute>:<second>+00:00`."""
    return f"2026-10-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}+00:00"


def assistant(ts, model=MODEL_A, *, input=0, output=0, cache_read=0, cache_write=0,
              msg_id=None, sidechain=False, agent_id=None, session=SESSION, usage=None):
    """One assistant transcript entry. `usage` replaces the four-field usage
    block outright (to drop a field)."""
    if usage is None:
        usage = {
            "input_tokens": input,
            "output_tokens": output,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_write,
        }
    entry = {
        "type": "assistant",
        "timestamp": ts,
        "sessionId": session,
        "isSidechain": sidechain,
        "message": {
            "id": msg_id or f"msg-{ts}-{model}-{input}-{output}",
            "model": model,
            "role": "assistant",
            "usage": usage,
            "content": [{"type": "text", "text": SECRET}],
        },
    }
    if agent_id:
        entry["agentId"] = agent_id
    return entry


def user(ts, session=SESSION):
    return {"type": "user", "timestamp": ts, "sessionId": session,
            "message": {"role": "user", "content": SECRET}}


def _write_jsonl(path, entries, tail=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries) + tail)
    return path


def write_transcript(directory, entries, *, session=SESSION, tail=""):
    """The session's main transcript, `<directory>/<session>.jsonl`. `tail`
    is appended raw (a truncated last line, as a live writer leaves one)."""
    return _write_jsonl(Path(directory) / f"{session}.jsonl", entries, tail)


def write_subagent(directory, agent_id, entries, *, session=SESSION):
    """A subagent transcript in the session's own directory,
    `<directory>/<session>/subagents/agent-<id>.jsonl`."""
    return _write_jsonl(
        Path(directory) / session / "subagents" / f"agent-{agent_id}.jsonl", entries)


def env(agent=True, **extra):
    """The parent environment without GIT_*, plugin or project variables;
    `CLAUDECODE` set only for an agent session. `extra` applies last."""
    e = {k: v for k, v in os.environ.items()
         if not k.startswith("GIT_")
         and k not in ("CLAUDECODE", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR")}
    if agent:
        e["CLAUDECODE"] = "1"
    e.update(extra)
    return e


def git(cwd, *args, env_=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, env=env_ or env())


def run_gates(root, *args, env_=None):
    return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=root,
                          capture_output=True, text=True, env=env_ or env(), timeout=120)


def change_repo(root, manifest=MANIFEST, tasks=TASKS):
    """A repo on `main` with `manifest` committed, then the change branch
    with its `tasks.md` committed. No ledger yet."""
    root = Path(root)
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    (root / ".gates.yaml").write_text(manifest)
    git(root, "add", "-A")
    git(root, "commit", "-m", "init")
    git(root, "checkout", "-b", CHANGE)
    t = root / "openspec" / "changes" / CHANGE / "tasks.md"
    t.parent.mkdir(parents=True)
    t.write_text(tasks)
    git(root, "add", "-A")
    git(root, "commit", "-m", "tasks")
    return root


def ledger(root, change=CHANGE):
    return Path(root) / ".gatedloop" / "runs" / f"{change}.jsonl"


def rows(root, change=CHANGE):
    p = ledger(root, change)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def usage_rows(root, change=CHANGE):
    return [r for r in rows(root, change) if r.get("gate") == "usage"]


def seed(root, *entries, change=CHANGE):
    """Append ledger rows as a loop would have written them."""
    p = ledger(root, change)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        for r in entries:
            full = {"change": change, "ts": at(0)}
            full.update(r)
            f.write(json.dumps(full) + "\n")


def task_start(ts, task):
    return {"ts": ts, "gate": "task-start", "task": task, "tree": "t" * 40, "exit": 0}


def usage_row(ts, task, tokens, *, window_from=None, source="claude-code-transcript",
              messages=1):
    """A usage row as `gates usage record` writes it: `tokens` maps a model to
    its four counts, or is None for a source with no counts."""
    return {"ts": ts, "gate": "usage", "task": task, "exit": None, "tokens": tokens,
            "messages": messages if tokens is not None else None, "source": source,
            "window": {"from": window_from, "to": ts}}


def counts(input=0, output=0, cache_read=0, cache_write=0):
    return {"input": input, "output": output, "cache_read": cache_read,
            "cache_write": cache_write}


def token_total(row_tokens):
    """The sum of every count in a usage row's `tokens` map (0 for None)."""
    if not row_tokens:
        return 0
    return sum(sum(c.values()) for c in row_tokens.values())
