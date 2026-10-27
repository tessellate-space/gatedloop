"""Shared fixtures for the git-hook tests of `adoption-followups` and
`git-layer-enforcement`: throwaway git repos, hook bodies, the installed
shim-path line, and an environment in which nothing but that line resolves
the shim. Never touches this repository's own `.git/hooks`.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
TEMPLATE = REPO / "templates" / "git-hooks" / "pre-commit"
PUSH_TEMPLATE = REPO / "templates" / "git-hooks" / "pre-push"

# The header every template the `none` install path ever wrote carries.
TEMPLATE_HEADER = "# gatedloop git pre-commit hook (enforce-at-the-effect, design D1/D2).\n"
# The pre-push template's header (git-layer-enforcement D3).
PUSH_TEMPLATE_HEADER = "# gatedloop git pre-push hook (enforce-at-the-effect, git-layer-enforcement D3).\n"

# A direct copy of an earlier template: today's header over the pre-0.5 body
# (`gate-marker check ci`, before lock-and-ledger-hygiene D4).
OLDER_COPY = (
    "#!/usr/bin/env bash\n" + TEMPLATE_HEADER
    + 'if marker_out="$("${GATES}" gate-marker check ci "${tree}" 2>&1)"; then\n'
    "  exit 0\nfi\nexit 1\n"
)

# A direct copy of a pre-push template whose body is not the shipped one.
OLDER_PUSH_COPY = "#!/usr/bin/env bash\n" + PUSH_TEMPLATE_HEADER + "echo an-older-body\nexit 0\n"

# A direct copy an adopter edited by hand.
EDITED_COPY = "#!/usr/bin/env bash\n" + TEMPLATE_HEADER + "echo my-local-edit\nexit 0\n"

# A hook nobody at gatedloop wrote.
FOREIGN_HOOK = "#!/bin/sh\necho someone-elses-hook\nexit 0\n"

# git-layer-enforcement D2: the one line `gates hook install` writes into a
# template, recording the installing shim's path. The shipped template holds
# it empty.
RECORDED_LINE_RE = re.compile(r"^GATES_INSTALLED=.*$", re.MULTILINE)
EMPTY_RECORDED_LINE = "GATES_INSTALLED=''"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def init_repo(root):
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")


def default_hook(root, name="pre-commit"):
    return Path(root) / ".git" / "hooks" / name


def write_hook(path, body):
    """Write `body` (text or bytes) as an executable hook at `path`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body if isinstance(body, bytes) else body.encode())
    path.chmod(0o755)


def composed_husky_hook(root, snippet, name="pre-commit"):
    """A husky `.husky/<name>` with an existing step and `snippet` (the
    shim's composed block) appended, as `gates hook install` composes it."""
    (Path(root) / ".husky").mkdir(exist_ok=True)
    path = Path(root) / ".husky" / name
    write_hook(path, "#!/usr/bin/env sh\necho lint\n\n" + snippet)
    return path


def with_recorded(body: str, shim_path) -> str:
    """`body` (a template's text) with the recorded shim path set, as `gates
    hook install` writes it."""
    line = "GATES_INSTALLED=" + shlex.quote(str(shim_path))
    return RECORDED_LINE_RE.sub(lambda _m: line, body, count=1)


def normalized(body: str) -> str:
    """`body` with the recorded shim path emptied: what an installed hook is
    compared with the shipped template as."""
    return RECORDED_LINE_RE.sub(lambda _m: EMPTY_RECORDED_LINE, body, count=1)


def recorded_path(body: str):
    """The shim path recorded in an installed hook, or None when the line is
    empty or missing."""
    m = RECORDED_LINE_RE.search(body)
    if not m:
        return None
    words = shlex.split(m.group(0)[len("GATES_INSTALLED="):])
    return words[0] if words and words[0] else None


def _has_gates(directory: str) -> bool:
    return os.access(os.path.join(directory, "gates"), os.X_OK)


def gate_free_path() -> str:
    """A PATH holding git, bash and this Python, and no `gates`: the shim
    resolves through neither the plugin root nor PATH."""
    dirs = []
    for d in (os.path.dirname(sys.executable), os.path.dirname(shutil.which("git") or ""),
              "/usr/bin", "/bin"):
        if d and d not in dirs and not _has_gates(d):
            dirs.append(d)
    return os.pathsep.join(dirs)


def env_without_gates(**extra) -> dict:
    """The parent environment with no GIT_* variable, no agent-session
    variable, no plugin root and a gate-free PATH; `extra` is applied last
    (a None value removes the key)."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in ("CLAUDECODE", "OTHER_HOST_VAR",
                                                     "CLAUDE_PLUGIN_ROOT")}
    env["PATH"] = gate_free_path()
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


def gates_on_path_dir(parent) -> str:
    """A directory holding a `gates` that runs this checkout's shim: the
    shim resolves through PATH alone."""
    d = Path(parent) / "path-bin"
    d.mkdir(parents=True, exist_ok=True)
    write_hook(d / "gates", f'#!/bin/sh\nexec "{sys.executable}" "{GATES_SHIM}" "$@"\n')
    return str(d)
