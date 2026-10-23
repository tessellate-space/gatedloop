"""Shared fixtures for the git-hook tests of `adoption-followups`: throwaway
git repos and hook bodies. Never touches this repository's own `.git/hooks`.
"""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"
TEMPLATE = REPO / "templates" / "git-hooks" / "pre-commit"

# The header every template the `none` install path ever wrote carries.
TEMPLATE_HEADER = "# gatedloop git pre-commit hook (enforce-at-the-effect, design D1/D2).\n"

# A direct copy of an earlier template: today's header over the pre-0.5 body
# (`gate-marker check ci`, before lock-and-ledger-hygiene D4).
OLDER_COPY = (
    "#!/usr/bin/env bash\n" + TEMPLATE_HEADER
    + 'if marker_out="$("${GATES}" gate-marker check ci "${tree}" 2>&1)"; then\n'
    "  exit 0\nfi\nexit 1\n"
)

# A direct copy an adopter edited by hand.
EDITED_COPY = "#!/usr/bin/env bash\n" + TEMPLATE_HEADER + "echo my-local-edit\nexit 0\n"

# A hook nobody at gatedloop wrote.
FOREIGN_HOOK = "#!/bin/sh\necho someone-elses-hook\nexit 0\n"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def init_repo(root):
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")


def default_hook(root):
    return Path(root) / ".git" / "hooks" / "pre-commit"


def write_hook(path, body):
    """Write `body` (text or bytes) as an executable hook at `path`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body if isinstance(body, bytes) else body.encode())
    path.chmod(0o755)


def composed_husky_hook(root, snippet):
    """A husky `.husky/pre-commit` with an existing step and `snippet` (the
    shim's composed block) appended, as `gates hook install` composes it."""
    (Path(root) / ".husky").mkdir(exist_ok=True)
    path = Path(root) / ".husky" / "pre-commit"
    write_hook(path, "#!/usr/bin/env sh\necho lint\n\n" + snippet)
    return path
