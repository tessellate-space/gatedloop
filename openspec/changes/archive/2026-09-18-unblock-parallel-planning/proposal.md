# Proposal: unblock-parallel-planning

## Why

Field-trial issues #5 and #7 report the same underlying assumption: the loop believes
there is exactly one working tree. Planning is serialized behind the implementation
checkout (#5), and a proposal refused off `main` strands a half-created scaffold on
the feature branch (#7). A halted `tdd-implementer` run then proved the assumption is
enforced even where it was meant to be escaped: every `PreToolUse` gate hook resolves
the repository from `CLAUDE_PROJECT_DIR` — the session root — rather than from where
the guarded command actually runs, so an agent in a git worktree has its commits
checked against the *primary checkout's* index and an *empty* marker store, and is
denied on a green `ci`. The natural escape hatch (implementer in a worktree, planning
in the primary checkout) is exactly the configuration the enforcement layer breaks.

## What Changes

- **Worktree-aware enforcement (the root fix).** Every gate hook that today does
  `cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"` — `gate-commit.sh`, `gate-merge.sh`,
  `gate-archive.sh`, `gate-implement.sh`, `gate-propose.sh`, `clear-ci-marker.sh` —
  SHALL resolve the repository from the hook input's `cwd` field, falling back to
  `CLAUDE_PROJECT_DIR` only when `cwd` is absent. The gate then measures the repo the
  command will actually run in; markers already live per-worktree under
  `.git/worktrees/<name>/`, so the compare becomes correct by construction.
- **Planning-grade commit gate.** When the staged diff touches only planning files —
  `openspec/**` plus the manifest's `conventions.rules-doc` — the commit gate SHALL be
  satisfied by `gates validate` + `openspec validate` instead of a green `ci` marker.
  Same enforce-at-the-marker mechanism, same exit-code oracle, scoped to what a
  docs-only tree can actually break. Any non-planning file in the diff keeps the full
  `ci` requirement.
- **D9 admits plan branches.** Proposal authoring SHALL be permitted on `main`/`master`
  and on `plan/*` branches (the branch `/specloop:propose` itself creates), so a
  secondary worktree on a plan branch can author while the implementer holds the
  change branch. The D9 rationale — author against the authoritative specs with all
  in-flight changes visible — is preserved by requiring the plan branch to be based on
  the merge target.
- **The scaffold is branch-gated too (#7).** The same D9 check SHALL fire before
  `openspec new change`, not only before artifact writes, so a refused proposal never
  leaves a stranded change directory. The refusal message SHALL name any debris that
  does exist and how to clean it.
- **Explicitly out of scope:** parallel *implementers* (one implementer owning the
  primary checkout and running stack remains correct — live-checks are stack-coupled);
  the brace-glob matcher fix (issue #1, a separate change).

## Capabilities

### New Capabilities

- `parallel-planning`: planning work proceeds while an implementer holds a checkout —
  gate enforcement resolves the repository from the guarded command's own working
  directory (worktree-correct), docs-only commits are gated at planning grade, and
  proposal scaffolding is subject to the same branch discipline as proposal authoring
  so a refusal leaves the tree unchanged.

### Modified Capabilities

<!-- None in openspec/specs/ today. The behavior this change amends was introduced by
     harden-unattended-loop, whose loop-enforcement spec is still a delta inside that
     change (not yet archived). This change's spec therefore lands as a new capability;
     if harden-unattended-loop archives first, the archive step should reconcile the
     two rather than duplicate requirements. -->

## Impact

- **Hooks**: the six `hooks/*.sh` gate scripts gain `cwd`-based repo resolution (hook
  changes require a new session to take effect — release note).
- **Shim**: `bin/gates` gains the planning-grade selection for the commit gate and the
  scaffold-time discipline check; `tests/` covers the diff classification (planning-only
  vs mixed) and the fallback ordering (`cwd` → `CLAUDE_PROJECT_DIR`).
- **Commands/docs**: `commands/propose.md` documents the worktree path; `SETUP.md` and
  `AUTOMATION.md` describe the planning-grade gate and the worktree resolution rule.
- **Ordering**: `enforce-at-the-effect` moves commit enforcement to the git layer,
  where per-repo resolution is inherent — but its git `pre-commit` hook must apply the
  same planning-grade selection, and the `PreToolUse` layer it retains as "layer 1"
  needs this fix regardless. Whichever lands second reconciles the commit-gate wording.
- **No new dependencies**; `zero-dep-shim` holds (diff classification is `git diff
  --cached --name-only` + the existing matcher).
