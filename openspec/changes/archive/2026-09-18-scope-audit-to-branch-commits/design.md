# Design: scope-audit-to-branch-commits

## Context

See proposal.md — Why. The mechanics that matter for the fix:

- `_new_commits_to_audit` (`bin/gates`, ~1759–1794) picks a range base in this
  order: the per-worktree cursor (`.git/specloop/audit/<change>.head`) when it is
  still an ancestor of `HEAD`; else the merge target from `_resolve_merge_target`;
  else no walk. It then runs `git rev-list <base>..HEAD`.
- The merge-target branch of that ladder is already correct: `target..HEAD`
  excludes everything reachable from the target by construction. The cursor branch
  is the defective one — a fast-forward onto a moved `main` keeps the cursor an
  ancestor of `HEAD`, so `cursor..HEAD` sweeps in `main`'s adopted squash commits.
- `cmd_audit` joins each walked commit's tree against green-`ci` ledger rows and
  taints on a miss. Adopted squash commits always miss (their gates ran pre-squash
  on their own branch), so every adoption taints.
- Constraints: `zero-dep-shim` (stdlib only), `fail-loud-gates` (never silently
  narrow detection), and the tests convention — branching Python gets stdlib
  `unittest` coverage; `tests/test_audit.py` already drives `gates audit` as a
  subprocess against throwaway repos.

## Goals / Non-Goals

**Goals:**

- No taint for commits already reachable from the merge target, in every walk mode
  (cursor-based and target-based alike).
- The exemption is ancestry-only. A commit created locally without a green-`ci` row
  taints exactly as before, including immediately after an adoption.
- Resolution failure degrades toward *more* auditing, never less.

**Non-Goals:**

- No session-identity or timestamp heuristics for "commits the session created"
  (issue #11 lists them as alternatives; see D2 for why ancestry wins).
- No change to taint semantics, the remedy (green `ci` on head), the cursor's
  lifecycle, or `cmd_audit`'s reporting.
- Marker freshness and hook matching — sibling changes `fix-marker-mechanics` and
  `harden-hook-matching`; this change is fully independent of both.

## Decisions

### D1 — Filter by merge-target ancestry inside `_new_commits_to_audit`

Always resolve the merge target, and when it resolves, exclude its ancestry from
the walk regardless of which base was chosen: `git rev-list <base>..<head> --not
<target>` (one process, no per-commit `merge-base --is-ancestor` calls — the walk
stays O(range), not O(range × ancestry check)). When the base already *is* the
target, `--not target` is a no-op, so one code path serves both modes.

*Alternative considered:* filter per-commit in `cmd_audit` with
`_is_ancestor(sha, target)`. Rejected: N subprocesses per audit under a Stop-hook
timeout budget, and it spreads range semantics across two functions. The selection
belongs where the range is built — the same "selection is done in code" principle
the surfaces logic follows.

### D2 — Ancestry is the only exemption

Issue #11 offers three candidate scopes: a recorded branch-creation point,
committer identity/timestamp windows, or merge-target ancestry. Ancestry is chosen
because it matches the actual guarantee: a commit on the merge target *was gated by
its own PR* — that is a fact about the repository, checkable in code. Identity and
timestamps are facts about who typed, forgeable by exactly the actor the audit
exists to catch (an agent that slipped the hooks can also write plausible committer
fields). A branch-creation record is new durable state with its own staleness
problems, and it still mis-handles adoption (the adopted commits postdate the
branch creation).

### D3 — Unresolvable target keeps today's behaviour

When `_resolve_merge_target` returns nothing, the walk is exactly what it is today
(cursor-based when possible, else empty). The failure mode of the exemption must be
"audit more", never "skip more" — narrowing detection because a lookup failed would
invert `fail-loud-gates`. This is stated as its own spec scenario and gets its own
test.

### D4 — Tests are black-box subprocess tests in `tests/test_audit.py`

Extend the existing style: build a throwaway repo, create a `main` with a
squash-like commit, fast-forward the change branch onto it, run `gates audit`, and
assert on real ledger rows. Three cases pin the three behaviours: adoption does not
taint; a subsequent local ungated commit still taints; no-target behaviour is
unchanged. Black-box because the join is on real git trees and real ledger rows —
the same rationale the file's docstring already records.

## Risks / Trade-offs

- [A genuinely ungated commit that somehow lands on the merge target is exempt] →
  Accepted by design: the merge target is protected by its own gates (the merge
  gate locally, branch protection on the forge per the existing loop-enforcement
  requirement). The audit's job is this branch's commits; guarding `main` is the
  merge gate's.
- [`origin/HEAD`-based target resolution can lag the true default branch] →
  Pre-existing property of `_resolve_merge_target`, shared with the merge gate and
  surface selection; a stale target only shrinks the exemption (more auditing),
  which is the safe direction.
- [An adopter merges `main` into the branch instead of fast-forwarding] →
  `rev-list --not target` handles merge topologies identically — reachability, not
  first-parent order — so the fix covers merge-based upkeep too; the fast-forward
  case in the tests is the reported repro, not the limit of the fix.

## Open Questions

None — the fix is a range-construction change with the behaviour pinned by specs
and tests above.
