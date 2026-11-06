"""A plan on its plan branch, for the plan preflight (openspec change
`plan-preflight`).

`PreflightRepo` builds a real git repository whose `main` holds a small
project (a manifest, two source files, one test) and whose `plan/<change>`
branch adds the change's plan: proposal, design, one spec and a `tasks.md`.
The shim is driven as a subprocess, as the planner drives it. `CLAUDECODE`
is set explicitly, so a run behaves the same locally and in CI.

Stdlib only, per `zero-dep-shim`. Not a test module (no `test` prefix).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
CHANGE = "add-widget"

MANIFEST = (
    "gatesVersion: 1\n"
    "gates:\n"
    '  ci: "true"\n'
    '  unit: "true"\n'
)

TASKS = """\
# Tasks

## 1. Widget

- [ ] 1.1 Add the widget in `src/widget.py` [oracle: unit]
- [ ] 1.2 Rework the gadget test [oracle: unit rewrites: tests/test_gadget.py]
- [ ] 2.1 Document the widget in `docs/widget.md` [oracle: none]
"""

PROPOSAL = """\
# Proposal

## Why

Widgets.

## What Changes

- **Add a widget.** It widgets.
  More prose.
- **Document it.**
"""

DESIGN = """\
# Design

## Decisions

### D1. The widget lives in `src/widget.py`

It does.

### D2. The gadget test moves

It does.
"""

SPEC = """\
# Spec Delta

## ADDED Requirements

### Requirement: Widgets widget

The system SHALL widget.

#### Scenario: Widgeting

- **WHEN** it widgets
- **THEN** it is widgeted
"""

GADGET_TEST = "def test_gadget():\n    assert True\n"


def env(**extra) -> dict:
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    e.pop("CLAUDE_PROJECT_DIR", None)
    e["CLAUDECODE"] = "1"
    e.update(extra)
    return e


def _hook_env() -> dict:
    return env(CLAUDE_PLUGIN_ROOT=str(REPO))


def tool_hook(root):
    """The PreToolUse commit hook, as the host runs it for `git commit`."""
    return subprocess.run(
        ["bash", str(REPO / "hooks" / "gate-commit.sh")], cwd=root, env=_hook_env(),
        capture_output=True, text=True,
        input=json.dumps({"tool_input": {"command": "git commit -m x"}, "cwd": str(root)}),
    )


def git_hook(root):
    """The git `pre-commit` hook template, run in place."""
    return subprocess.run(["bash", str(REPO / "templates" / "git-hooks" / "pre-commit")],
                          cwd=root, env=_hook_env(), capture_output=True, text=True)


def tool_denied(r) -> bool:
    return r.returncode != 0 or '"deny"' in r.stdout


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True,
                          text=True, env=env())


def write(root, rel, text) -> Path:
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


class PreflightRepo:
    """A project on `main`, and the change's plan committed on `plan/<change>`."""

    def __init__(self, tmp, tasks: str = TASKS, manifest: str = MANIFEST,
                 proposal: str = PROPOSAL, design: str = DESIGN,
                 specs: dict | None = None, change: str = CHANGE,
                 branch: str | None = None, commit_plan: bool = True):
        self.root = Path(tmp)
        self.change = change
        root = self.root
        root.mkdir(parents=True, exist_ok=True)
        git(root, "init", "-b", "main")
        git(root, "config", "user.email", "t@example.com")
        git(root, "config", "user.name", "T")
        git(root, "config", "commit.gpgsign", "false")
        write(root, ".gates.yaml", manifest)
        write(root, "src/gadget.py", "def gadget():\n    return 1\n")
        write(root, "src/other.py", "X = 1\n")
        write(root, "tests/test_gadget.py", GADGET_TEST)
        git(root, "add", "-A")
        git(root, "commit", "-m", "init")
        git(root, "checkout", "-b", branch or f"plan/{change}")
        self.change_dir = root / "openspec" / "changes" / change
        write(root, f"{self.rel_dir}/.openspec.yaml", "schema: spec-driven\n")
        write(root, f"{self.rel_dir}/proposal.md", proposal)
        write(root, f"{self.rel_dir}/design.md", design)
        write(root, f"{self.rel_dir}/tasks.md", tasks)
        for cap, text in (specs if specs is not None else {"widget": SPEC}).items():
            write(root, f"{self.rel_dir}/specs/{cap}/spec.md", text)
        if commit_plan:
            git(root, "add", "-A")
            git(root, "commit", "-m", f"plan: {change}")

    @property
    def rel_dir(self) -> str:
        return f"openspec/changes/{self.change}"

    @property
    def store(self) -> Path:
        return self.root / ".gatedloop" / "out" / "preflight" / self.change

    @property
    def holding(self) -> Path:
        return self.root / ".gatedloop" / "authored" / self.change

    @property
    def ledger(self) -> Path:
        return self.root / ".gatedloop" / "runs" / f"{self.change}.jsonl"

    def gates(self, *args, cwd=None, timeout=120, **extra_env):
        return subprocess.run([sys.executable, str(GATES_SHIM), *args], cwd=cwd or self.root,
                              capture_output=True, text=True, env=env(**extra_env),
                              timeout=timeout)

    def hold(self, task: str, rel: str, text: str, where: Path | None = None) -> Path:
        """Write one held file, `<task>/<rel>` (suffix included by the caller
        for a test, bare for CHARACTERIZATION / NO-TESTS)."""
        base = where if where is not None else self.store / "authored"
        return write(base, f"{task}/{rel}", text)

    def rows(self) -> list[dict]:
        if not self.ledger.exists():
            return []
        return [json.loads(x) for x in self.ledger.read_text().splitlines() if x.strip()]

    def set_tasks(self, text: str) -> None:
        write(self.root, f"{self.rel_dir}/tasks.md", text)

    def edit(self, rel: str, old: str, new: str) -> None:
        p = self.root / rel
        body = p.read_text()
        assert old in body, f"{old!r} not in {rel}"
        p.write_text(body.replace(old, new, 1))

    def status(self) -> str:
        return git(self.root, "status", "--porcelain", "--untracked-files=all").stdout

    def count_objects(self) -> str:
        return git(self.root, "count-objects", "-v").stdout
