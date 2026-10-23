# Design: fix-normalize-tree-checkout-dependence

## Context

See proposal.md — Why. The relevant mechanics, all in `bin/gates`:

- `_normalize_tree(root, tree)` (fix-marker-mechanics D1) builds a scratch index
  via `GIT_INDEX_FILE`, `git read-tree <tree>`, then `git rm --cached -r
  --ignore-unmatch .specloop/runs`, then `git write-tree`. It is called at both
  ends — `_write_marker` and `_check_marker_and_report` (`gate-marker check`) — which
  is the single-implementation argument that both sides agree on "fresh".
- Its docstring promises "no working-tree effect" and a fail-safe STRICT contract:
  any plumbing failure returns `tree` unchanged, so a defect can only deny.
- `git rm --cached` without `-f` applies git's *working-tree safety check*: it
  refuses to drop an index entry whose blob differs from both `HEAD` and the file on
  disk, because a user running it against the real index could lose staged content.
  In a scratch index whose only purpose is to be hashed, that check protects nothing
  — but it still fires, keyed on the *current checkout's* `HEAD` and working file.
- The `rm` result is discarded; only `read-tree` and `write-tree` are checked. So a
  refusal produces a successful-looking, un-stripped `write-tree`.
- The merge hook (`hooks/gate-merge.sh`) runs `gate-marker check live-check
  <branch-head-tree>` from the merge-target checkout. The marker was written by
  `gates run live-check` on the branch head. Whenever any ledger file differs between
  those two checkouts, exactly one of the two normalizations is refused.
- Constraints: `zero-dep-shim` (stdlib subprocess only), `fail-loud-gates`,
  the O(1) hook budget (no re-running gates under a hook timeout). The existing
  suites `test_marker_normalization` (6 cases) and `test_marker_tree_keyed` pin the
  current behavior of the normalizer and its wiring; they must keep passing.

## Goals / Non-Goals

**Goals:**

- `_normalize_tree` is a pure function of `(tree, .specloop/runs prefix)`.
- The STRICT fail-closed contract is kept *and* made observable.
- The fix is pinned by a test that fails on 0.3.0 for the exact field reason.

**Non-Goals:**

- Changing what is stripped (the ledger prefix), the marker file format, the
  tree-keyed store, the hook interface, or any prompt.
- Making a normalization failure *fail open* (accepting the marker anyway) — that
  would let an unnormalized ledger delta pass, the very thing D1 forbids.
- Recovering already-blocked adopters automatically; re-running the gate on the
  head once with the fixed shim is sufficient and documented in the proposal.

## Decisions

### D1: Force the scratch-index removal and read its exit status

Adopt #21's patch: add `-f` to the `git rm --cached` invocation and return `tree`
when it exits non-zero.

- `-f` is correct, not merely expedient: git's safety check exists to protect a
  working tree from losing content staged in the *real* index. With `GIT_INDEX_FILE`
  pointing at a throwaway file and `--cached`, the command touches no working-tree
  path and the real index is never opened. There is nothing to protect, so the
  check is pure false-positive noise that happens to be keyed on state (`HEAD`, the
  checked-out file) that the function's contract says it must not depend on.
- Reading the exit status closes the second half of the defect: a swallowed
  non-zero result is what turned a refusal into a wrong-but-successful answer.

**Alternative — normalize by filtering `git ls-tree -r` output and rebuilding with
`git mktree`:** rejected. It is checkout-independent by construction, but it
replaces three plumbing calls with a parse-and-rebuild loop (recursing into
subtrees, re-emitting modes and object types) — more code in the zero-dep shim to
achieve the same hash that the forced `rm` already yields, and a second
normalization algorithm to keep in agreement with the tests' ground truth.

**Alternative — run the scratch operations from a detached temporary worktree or
with `GIT_WORK_TREE` pointed at an empty directory:** rejected. It defeats the
safety check indirectly (no working file to compare against) but costs a worktree
or an environment trick per call, and `-f` states the intent directly.

### D2: Report a strip failure on stderr instead of returning silently

When `git rm` (or `read-tree`/`write-tree`) fails, keep returning `tree` — the
STRICT contract — and additionally print one line to stderr:
`specloop: ledger normalization failed (git rm --cached): <first line of stderr>;
comparing the unnormalized tree`. The message names the step and quotes git.

- `fail-loud-gates` says a check never silently skips. Today's silent fallback is
  what let the defect masquerade as "marker is stale" for a week of denials; the
  denial text itself was true but pointed at the wrong cause.
- stderr, not stdout: callers such as `gate-marker check` are parsed by hooks on
  exit status and message text; a stderr note passes through `2>&1` in
  `hooks/gate-merge.sh` and shows up in the hook's denial reason, which is where the
  adopter reads it.
- No exit-code change: a normalization failure still resolves to a deny via the
  hash mismatch, so the hook's contract (exit code is the oracle) is untouched.

**Alternative — raise / exit non-zero on normalization failure:** rejected. It would
turn a marker *write* into a gate failure after the gate itself passed green,
inverting the meaning of the exit code; and the deny-by-mismatch path already
produces the right verdict.

### D3: Pin the property with the #21 scenario, against a ground-truth strip

Add `test_same_tree_normalizes_identically_from_any_checkout` to
`tests/test_marker_normalization.py`, next to the six existing normalizer cases and
using their loader. It is the scenario from the issue verbatim:

1. `main`: commit `a.txt` and `.specloop/runs/other-change.jsonl` (`{"row": 1}`).
2. `plan/x`: add `b.txt`, append `{"row": 2}` to the ledger, commit; capture
   `HEAD^{tree}` as `branch_tree`.
3. `from_branch = _normalize_tree(root, branch_tree)` with the branch checked out.
4. Back on `main`: overwrite the ledger with `{"row": 1}\n{"row": 99}` and commit.
5. `from_main = _normalize_tree(root, branch_tree)` with `main` checked out.
6. Ground truth: a scratch index, `read-tree branch_tree`, `rm --cached -r -f -q
   --ignore-unmatch .specloop/runs`, `write-tree`.

Assert `from_branch == stripped`, `from_main == stripped`, `from_branch ==
from_main`, with the failure message naming the checkout dependence. The ground
truth is computed independently of the function under test so the test cannot pass
by both sides being wrong the same way. Verified: on current `main` step 5 returns
`branch_tree` itself (unstripped) and the test fails; with D1 it passes.

A second small case covers D2: monkeypatch `subprocess.run` (or point the shim at a
`git` shim on `PATH`) so the `rm` step exits non-zero, and assert the return value is
the input tree and stderr contains the normalization-failed line.

## Risks / Trade-offs

- [`-f` masks a genuine future misuse where the scratch index is accidentally the
  real one] → The function sets `GIT_INDEX_FILE` to a path inside a fresh
  `TemporaryDirectory` on every call; the new D3 test additionally asserts that
  the real index (`git write-tree` without `GIT_INDEX_FILE`) and the working tree
  are byte-identical before and after both normalizations, so a future regression
  that reached the real index would fail the suite.
- [Adopters already holding markers from the old shim] → Markers written *on the
  head* by 0.3.0 are already correctly stripped (the strip only fails on the
  divergent side); only the check side was wrong. After upgrading, one
  `gates run live-check` / `gates run ci` on the head is enough and is what the
  denial message already tells them to do.
- [The stderr note adds a line to hook output in a failure that should now be
  near-impossible] → It only prints when the strip actually fails; the common path
  is unchanged and quiet-on-green.

## Migration Plan

Ship in the next plugin release. No manifest, marker, or hook migration. Rollback
is reverting the two-line change; the test would fail again, which is the point.
