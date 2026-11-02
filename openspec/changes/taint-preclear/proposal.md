## Why

The reflog audit taints any new commit on a change branch whose own tree has no green `ci` row (loop-enforcement, "An ungated commit is detected after the fact and taints the change"). A green `ci` on the branch head clears a taint, but only one that already exists (`_maybe_resolve_taint`). `gates merge` step 1 runs the audit itself, so a lane that rebased or synced its branch fails like this (#132):

1. Every rebased commit gets a new tree that no `ci` ever saw.
2. The lane runs a full `ci` on its head. It passes, and there is no taint yet to clear.
3. `gates merge` step 1 audits, taints the rebased commits and refuses.
4. A second full `ci` clears the taint, and the merge then goes through.

That's one wasted full `ci` per rebased change, 8–15 minutes on the adopter's machine, seen twice on 0.8.0. `gates taint check` only reads recorded rows, so it can't warn the lane beforehand.

## What Changes

- The reflog audit treats a commit with no green `ci` row of its own as **vouched for by the head** when two things hold:
  - the commit is an ancestor of the branch head being audited;
  - a green, unscoped `ci` row names the head's tree, compared ledger-blind as the audit already compares.

  It records a distinct `vouched` row for that commit, not a taint and not a gated classification, so the ledger still shows which commits were individually gated.
- A scoped `ci` doesn't vouch. A commit with no head `ci` to vouch for it taints exactly as before.
- AUTOMATION.md and SETUP.md describe the vouching.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `loop-enforcement`: the reflog audit gains one exemption, a commit vouched for by a green unscoped `ci` on the audited head, and records it as `vouched`.

## Impact

- `bin/gates`: `cmd_audit` and a matcher lookup for the head's tree.
- `AUTOMATION.md` (layer 3 of the enforcement model) and SETUP.md's taint section.
- `tests/`: new audit cases.
- Default-on. The merge outcome is the one D7 already allows, since a green `ci` on the head clears a taint today; this moves that resolution before the merge instead of after a refused one.
