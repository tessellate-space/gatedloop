"""A plan merged through a plan PR (change `planner-handoff`).

`gates approval attest --merged`, the plan branch of `gates record-merged`
and `gates handoff` all start from the same state: change `add-plan` was
proposed on `plan/add-plan`, its PR was squash-merged into `main` in the
forge, and the checkout is on `main` at that squash, as a CI job's or an
orchestrator's would be. `PlanRepo` builds that state on `_merge_fixture`'s
real repository with a bare `origin`, and registers the PR with
`_forge_fixture`'s fake forge, so no test reaches the real API.

Stdlib only, per `zero-dep-shim`. Not a test module (no `test` prefix).
"""

from __future__ import annotations

import json
from pathlib import Path

import importlib.machinery
import importlib.util

from _forge_fixture import NO_CI, PR_MODE, Forge
from _merge_fixture import GATES_SHIM, MergeRepo, combined, git, rows_from_text

_SHIM = None


def _shim():
    """`bin/gates` loaded as a module (it has no `.py` suffix), once."""
    global _SHIM
    if _SHIM is None:
        loader = importlib.machinery.SourceFileLoader("gates_shim_plan", str(GATES_SHIM))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(module)
        _SHIM = module
    return _SHIM

PLAN = "add-plan"
PLAN_HEAD = f"plan/{PLAN}"
PLAN_DIR = f"openspec/changes/{PLAN}"
PLAN_YAML = f"{PLAN_DIR}/.openspec.yaml"
PLAN_LEDGER = f".gatedloop/runs/{PLAN}.jsonl"
MERGED_AT = "2026-10-20T09:30:00Z"

POLICY = {
    "self": "approval:\n  plan: self\n",
    "review": "approval:\n  plan: review\n",
}

class PlanRepo:
    """A `MergeRepo` under a declared plan-approval policy, in pull-request
    mode, with the fake forge on PATH."""

    def __init__(self, tmp: Path, policy: str = "self"):
        self.tmp = Path(tmp)
        self.repo = MergeRepo(self.tmp, manifest_extra=POLICY[policy] + PR_MODE)
        self.forge = Forge(self.tmp / "forge.json").install(self.repo.bin)
        self.primary = self.repo.primary

    # ---- running -----------------------------------------------------------

    def gates(self, *args, cwd=None, **env):
        return self.repo.gates(*args, cwd=cwd, **{**NO_CI, **env})

    # ---- building the plan -------------------------------------------------

    def write_plan(self, cwd: Path | None = None, proposal: bool = True, epic: str | None = None,
                   approval: dict | None = None) -> None:
        """`add-plan`'s artifacts: proposal, design, one spec, two open
        tasks, and a `.openspec.yaml` naming the schema (plus an epic or
        approval keys when asked)."""
        d = Path(cwd or self.primary) / PLAN_DIR
        (d / "specs" / "cap").mkdir(parents=True, exist_ok=True)
        if proposal:
            (d / "proposal.md").write_text("# Proposal: Add the plan\n\n## Why\n\nBecause.\n")
        (d / "design.md").write_text("# Design\n\n## Decisions\n\nD1. Do it.\n")
        (d / "specs" / "cap" / "spec.md").write_text(
            "## ADDED Requirements\n\n### Requirement: Plan\n\nThe system SHALL plan.\n\n"
            "#### Scenario: Planned\n\n- **WHEN** it plans\n- **THEN** it is planned\n"
        )
        (d / "tasks.md").write_text(
            "## 1. Do it\n\n- [x] 1.1 First thing\n- [ ] 1.2 Second thing\n- [ ] 1.3 Third thing\n"
        )
        lines = ["schema: spec-driven", "created: 2026-10-20"]
        if epic:
            lines.append(f"x-gatedloop-epic: {epic}")
        for key, value in (approval or {}).items():
            lines.append(f"{key}: {value}")
        (d / ".openspec.yaml").write_text("\n".join(lines) + "\n")

    def commit_on_main(self, subject: str) -> str:
        git(self.primary, "add", "-A")
        git(self.primary, "commit", "-q", "-m", subject)
        return git(self.primary, "rev-parse", "HEAD")

    def push_main(self) -> None:
        git(self.primary, "push", "-q", "origin", "HEAD:main")
        self.repo.push_log.write_text("")

    def merge_plan_pr(self, number: int = 42, merger: str = "alice", epic: str | None = None,
                      approval: dict | None = None) -> str:
        """Plan PR #`number` from `plan/add-plan`, squash-merged into `main`
        by `merger` and pushed; the forge knows the PR and the squash."""
        self.write_plan(epic=epic, approval=approval)
        squash = self.commit_on_main(f"propose: {PLAN} (#{number})")
        self.push_main()
        self.forge.add_pr(number, PLAN_HEAD, base="main", merged_by=merger,
                          merged_at=MERGED_AT, merge_commit=squash)
        self.forge.add_merged_pull(number, PLAN_HEAD, squash)
        return squash

    # ---- reading the outcome -----------------------------------------------

    def yaml_text(self, ref: str | None = None) -> str:
        if ref is None:
            p = self.primary / PLAN_YAML
            return p.read_text() if p.exists() else ""
        return git(self.primary, "show", f"{ref}:{PLAN_YAML}", check=False)

    def approval(self, ref: str | None = None) -> dict:
        """The `x-gatedloop-approved-*` keys, by suffix (`by`, `at`, `sha`),
        as a YAML reader sees them -- through the shim's own parser, never
        split from the raw lines, so a value YAML would misread (a ` #`
        opening a comment, a bare timestamp) reads back as it does for
        every other consumer of `.openspec.yaml`."""
        data = _shim()._parse_yaml_text(self.yaml_text(ref)) or {}
        prefix = "x-gatedloop-approved-"
        return {k[len(prefix):]: v for k, v in data.items() if str(k).startswith(prefix)}

    def ledger_rows(self) -> list:
        p = self.primary / PLAN_LEDGER
        return rows_from_text(p.read_text()) if p.exists() else []

    def state(self) -> tuple:
        """Everything a refusal must leave as it was."""
        return (
            git(self.primary, "rev-parse", "HEAD"),
            git(self.primary, "status", "--porcelain", "--untracked-files=all"),
            self.yaml_text(),
        )

    def plan_sha_at(self, ref: str) -> str:
        """`gates approval sha` over the plan as it stands at `ref`, from a
        throwaway worktree, so the expectation is computed by the shim's
        own public command and not re-derived here."""
        wt = self.tmp / f"sha-{ref[:12]}"
        git(self.primary, "worktree", "add", "-q", "--detach", str(wt), ref)
        try:
            r = self.repo.gates("approval", "sha", PLAN, cwd=wt)
            if r.returncode != 0:
                raise AssertionError(f"approval sha failed: {combined(r)}")
            return r.stdout.strip()
        finally:
            git(self.primary, "worktree", "remove", "--force", str(wt))


def payload(proc) -> dict:
    return json.loads(proc.stdout)
