# Proposal: scope-audit-to-branch-commits

## Why

`gates audit` — the layer-3 detection pass behind the Stop hook — taints the ledger
spuriously when a change branch is fast-forwarded onto a moved `main` (issue #11,
observed on `375096f`). The walk in `_new_commits_to_audit` uses the audit cursor as
the range base whenever the cursor is still an ancestor of `HEAD`; after a
fast-forward that range (`cursor..HEAD`) includes `main`'s adopted squash commits,
which never have a green-`ci` ledger row for this change (their gates ran pre-squash
on their own branch), so each one is tainted as if an ungated commit had been created
locally. Every spurious taint trains people to treat taint as noise, which defeats
the audit's purpose as the detection layer behind the git-layer hooks.

## What Changes

- `_new_commits_to_audit` in `bin/gates` excludes commits already reachable from the
  merge target from the audit walk, even when the walk starts at the cursor —
  `git rev-list <base>..HEAD --not <target>` semantics, with the target from the
  existing `_resolve_merge_target`. Commits already on the merge target were gated
  by their own PR and are exempt.
- The invariant is preserved and stated as a spec scenario: a commit created locally
  without a green-`ci` row STILL taints. Only merge-target ancestry exempts a commit
  — never authorship, timestamps, or session identity.
- When no merge target resolves, behaviour is unchanged from today: the audit fails
  toward auditing more commits, never toward silently skipping any (fail-loud-gates).
- Stdlib-only `unittest` additions in `tests/test_audit.py` covering the new
  branching: fast-forward adoption does not taint; a local ungated commit after such
  an adoption still taints; no-merge-target behaviour is unchanged. The audit
  selection is branching Python — exactly the class of code this repo tests.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `loop-enforcement`: the requirement "An ungated commit is detected after the fact
  and taints the change" gains a boundary — the audit scopes itself to commits not
  already reachable from the merge target, and a new scenario pins the exemption
  (adopted upstream commits do not taint) alongside the preserved invariant (local
  ungated commits still do). Note: this capability's base text is currently the
  `enforce-at-the-effect` delta (`openspec/changes/enforce-at-the-effect/specs/loop-enforcement/spec.md`),
  pending its sync to `openspec/specs/`; this change's delta applies on top of it.

## Impact

- **Code**: `bin/gates` only — `_new_commits_to_audit` (~lines 1759–1794); `cmd_audit`
  is untouched apart from consuming the corrected commit list.
- **Tests**: `tests/test_audit.py` gains cases; no new files or dependencies
  (zero-dep-shim holds).
- **Docs**: none required; the audit's user-facing message and remedy are unchanged.
- **Non-scope**: marker freshness (sibling `fix-marker-mechanics`) and hook matching
  (sibling `harden-hook-matching`) are untouched.
- **Ordering**: fully independent of both sibling changes; can land before or after
  either.

Rejection test: this makes a stated guarantee enforceable — the taint signal is only
a guarantee while it has no false positives — so it is ours (close), not upstream's.
