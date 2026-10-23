# Proposal: fix-normalize-tree-checkout-dependence

## Why

Issue #21 (field trial, one week of use on a multi-lane repo): every squash-merge is
denied as soon as any two changes' ledgers under `.specloop/runs/` diverge — which is
any repository with more than one active change. The denial repeats with *identical*
tree hashes after fresh green `gates run live-check` and `gates run ci` on the head,
so the adopter has no move that satisfies it. The cause is verified and reproduced on
`main`: `_normalize_tree` (fix-marker-mechanics D1) is not a pure function of its
`tree` argument. Its scratch-index `git rm --cached -r --ignore-unmatch .specloop/runs`
runs without `-f`, so git's safety check refuses the removal whenever the scratch entry
differs from both `HEAD` and the checked-out file; the refusal's exit status is never
read, and `git write-tree` hashes the **un-stripped** tree. A marker written on the
branch head (strip succeeds) can therefore never match `hooks/gate-merge.sh`'s check
run from `main` (strip refused). The "ledger-normalized" key depends on the checkout.

## What Changes

- **`_normalize_tree` becomes checkout-independent.** The scratch-index removal is
  forced (`-f`) — a `--cached` removal in a throwaway `GIT_INDEX_FILE` has no
  working-tree effect for git's safety check to protect — and its exit status is
  read. The same tree now normalizes to the same hash from any branch, worktree, or
  index state.
- **A failed strip stays fail-closed, but stops being silent.** A non-zero `git rm`
  returns the input tree unchanged (as the documented STRICT contract requires — it
  can only deny, never pass an unnormalized ledger delta), and a one-line stderr note
  names the plumbing failure so a denial it causes is diagnosable in minutes rather
  than a week of friction-journal entries (`fail-loud-gates`).
- **A regression test pins the property.** The stdlib scenario from #21 — same branch
  tree normalized once from the branch and once from `main` after the ledger diverges,
  compared against a ground-truth forced strip — lands in
  `tests/test_marker_normalization.py`. It fails on 0.3.0 and passes with the fix.

No hook interface, marker file format, ledger row, or shipped prompt changes. The
proposed patch in #21 is adopted as written, plus the stderr note.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `gate-binding`: the requirement "Marker freshness is blind to the durable ledger"
  gains the property the field defect violated — the normalization is a pure function
  of the tree it is given, independent of the current checkout, working tree, or real
  index — and a normalization failure is reported, not swallowed.

## Impact

- `bin/gates` — `_normalize_tree` only (two lines plus a stderr line). Callers
  (`_write_marker`, `gate-marker check`) are unchanged.
- `tests/test_marker_normalization.py` — one new test case; the existing six
  normalization tests and `test_marker_tree_keyed` must still pass.
- `hooks/gate-merge.sh` — no edit; its `gate-marker check live-check <tree>` from
  `main` simply starts agreeing with markers written on the branch head.
- Adopters on 0.3.0 with diverged ledgers: the blocked merges (`worktree-hygiene`,
  `agent-session-auth-resilience` in the report) become mergeable after re-running
  the gates on the head once with the fixed shim, since markers written by the old
  shim from the head are *already* correctly stripped — only the check side was wrong.
- Rejection test: this makes a stated guarantee ("the compare is a single hash
  equality on ledger-normalized trees") actually enforceable across checkouts — a
  `close` job, ours.
