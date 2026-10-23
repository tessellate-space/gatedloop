# Tasks: unblock-parallel-planning

## 1. Worktree-aware repo resolution (design D1)

- [x] 1.1 Red: fixture test driving each gate hook's embedded resolution logic through
      the shim boundary it exercises — hook input with `cwd` set to a secondary
      worktree resolves there; input without `cwd` falls back to
      `CLAUDE_PROJECT_DIR`; neither set falls back to `pwd`
- [x] 1.2 `hooks/gate-commit.sh`: parse top-level `cwd` in the existing `python3 -c`
      block; `cd` per the D1 fallback chain
- [x] 1.3 Same change in `hooks/gate-merge.sh`, `hooks/gate-archive.sh`,
      `hooks/gate-implement.sh`, `hooks/gate-propose.sh`, `hooks/clear-ci-marker.sh`
      (gate-propose keeps its path-relativization, now against the resolved repo)
- [x] 1.4 End-to-end check in a scratch repo with two worktrees: green marker in the
      worktree allows its commit; the primary checkout's commit is still denied
      without its own marker (spec: both worktree scenarios)

## 2. Planning-grade commit gate (design D2)

- [x] 2.1 Red: unit tests for staged-diff classification — planning-only (openspec/**),
      planning-only including the declared `conventions.rules-doc`, mixed diff, empty
      diff
- [x] 2.2 Implement `gates discipline check-commit <tree>`: classify; planning-only →
      `gates validate` + `openspec validate` per staged change dir; otherwise →
      existing `gate-marker check ci <tree>`; failure messages name the failing
      validation or missing gate (fail-loud-gates)
- [x] 2.3 `hooks/gate-commit.sh` calls `gates discipline check-commit` instead of
      `gate-marker check ci` directly
- [x] 2.4 Red→green: planning-only staged tree with an invalid artifact is denied;
      valid one is allowed with no `ci` marker present; mixed diff still requires the
      marker

## 3. D9 admits plan branches (design D3)

- [x] 3.1 Red: tests for `discipline check-propose` — merge target allowed (existing),
      `plan/*` with merge target as ancestor allowed, `plan/*` without ancestry
      refused, other branches refused; stale-base advisory printed when the merge
      target is ahead
- [x] 3.2 Implement the D3 branch logic in `bin/gates`; refusal message states the
      rationale and the permitted locations
- [x] 3.3 Confirm `discipline check-implement` never recognizes a `plan/*` branch as a
      change branch (test with a `plan/<existing-change>` name)

## 4. Scaffold gating and debris naming (design D4)

- [x] 4.1 Red: `discipline check-propose --scaffold` refuses on a feature branch,
      allows on the merge target and on a based `plan/*` branch
- [x] 4.2 Implement `--scaffold` (D3 logic, no file argument); add
      `hooks/gate-scaffold.sh` (PreToolUse on Bash, matches `openspec new change`) and
      register it in `hooks/hooks.json`
- [x] 4.3 Refusal messages (scaffold and authoring) list any untracked, unproposed
      `openspec/changes/*` directory with its cleanup command
- [x] 4.4 End-to-end in the scratch repo: scaffold on a feature branch refused with
      the tree unchanged; pre-existing debris is named

## 5. Docs and release note

- [x] 5.1 `SETUP.md`: planning-grade gate contract (what satisfies the commit gate for
      a docs-only tree) and the worktree resolution rule
- [x] 5.2 `AUTOMATION.md`: update the enforcement description — gates measure the repo
      the command runs in; note the reconciliation point with `enforce-at-the-effect`
      (single `discipline check-commit` entry)
- [x] 5.3 `commands/propose.md`: document the plan-worktree path (author on a `plan/*`
      branch in a secondary worktree while an implementer holds the change branch)
- [x] 5.4 Release note: hook changes require plugin reinstall + new session
