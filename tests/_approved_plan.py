"""An approved plan, written into a test repository (change `loop-hardening`).

`gates merge` and every acceptance writer refuse a change whose plan is not
the approved one (loop-hardening D1, D2): the merge target must carry the
plan with a populated approval whose `approved_sha` still matches it. A test
that builds its own repository and merges or accepts a change therefore
writes the plan through here before committing `main`, so its approval is
computed by the shim itself -- never a hand-typed hash that would drift from
the digest the shim checks.

Stdlib only, per `zero-dep-shim`. Not a test module (no `test` prefix).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATES_SHIM = REPO / "bin" / "gates"

APPROVER = "T <t@example.com>"
APPROVED_AT = "2026-10-20T09:00:00Z"


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CLAUDECODE"] = "1"
    return env


def approval_sha(root: Path, change: str) -> str:
    """`gates approval sha <change>` in `root`, which needs a manifest."""
    r = subprocess.run(
        [sys.executable, str(GATES_SHIM), "approval", "sha", change],
        cwd=root, capture_output=True, text=True, env=_env(),
    )
    if r.returncode != 0:
        raise AssertionError(f"fixture `gates approval sha {change}` failed: {r.stdout}{r.stderr}")
    return r.stdout.strip()


def record_approval(root: Path, change: str) -> str:
    """Write `change`'s `.openspec.yaml` with an approval matching its plan
    as it stands in `root`'s working tree, as an attest would. Commits
    nothing. Returns the approved sha."""
    sha = approval_sha(root, change)
    (Path(root) / "openspec" / "changes" / change / ".openspec.yaml").write_text(
        "schema: spec-driven\n"
        f"x-gatedloop-approved-by: {APPROVER}\n"
        f"x-gatedloop-approved-at: '{APPROVED_AT}'\n"
        f"x-gatedloop-approved-sha: {sha}\n"
    )
    return sha


def write_approved_plan(root: Path, change: str) -> str:
    """A minimal plan for `change` (proposal, one spec, one task) plus its
    recorded approval, in `root`'s working tree. Commits nothing."""
    d = Path(root) / "openspec" / "changes" / change
    (d / "specs" / "cap").mkdir(parents=True, exist_ok=True)
    (d / "proposal.md").write_text(f"# Proposal: {change}\n\n## Why\n\nBecause.\n")
    (d / "specs" / "cap" / "spec.md").write_text(
        "## ADDED Requirements\n\n### Requirement: Thing\n\nThe system SHALL work.\n\n"
        "#### Scenario: It works\n\n- **WHEN** it runs\n- **THEN** it works\n"
    )
    (d / "tasks.md").write_text("## 1. Do it\n\n- [ ] 1.1 Add the thing\n")
    return record_approval(root, change)
