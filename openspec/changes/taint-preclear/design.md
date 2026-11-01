## Context

The audit (`cmd_audit`) walks the change branch's commits since the audit cursor. For each one it looks up a green `ci` row by the commit's own tree, raw first and then ledger-normalised (`_GreenCiMatcher`). A miss records a `taint` row. Design D7 of `harden-unattended-loop` lets a green `ci` on the branch head resolve a taint: `_maybe_resolve_taint` appends `taint-clear`, but only when a taint is already outstanding. `gates merge` step 1 and the merge hook run the audit immediately before the taint check.

So a green head `ci` that runs *before* the audit has nothing to clear, and the audit then taints every commit whose tree no `ci` saw. A rebase produces exactly those commits. #132 reports one extra full `ci` per rebased change.

## Goals / Non-Goals

**Goals:** a lane that rebased and then ran a green full `ci` on its head merges without a second `ci`. The ledger still distinguishes individually gated commits from those the head vouched for.

**Non-Goals:**
- changing what clears an existing taint;
- changing the merge-target ancestry exemption;
- a read-only audit probe (option (a); see D4);
- the raw-versus-normalised tree comparison in `_maybe_resolve_taint`.

## Decisions

### D1. A green unscoped `ci` on the audited head vouches for its ancestors

In `cmd_audit`, before recording a taint for commit `c`, the audit checks two things:
- `c` is an ancestor of the head being audited (`git merge-base --is-ancestor c head`);
- the matcher finds a green `ci` row with scope `full` (or no scope) for the head's tree.

When both hold, the audit records a `vouched` row for `c` (gate `vouched`, `sha` = c, `tree` = c's tree) instead of a `taint`. `c` is not counted as an incident, and the audit exits 0 for it.

**Why the head and not the commit:** the head's tree contains every ancestor's surviving content, and a full green `ci` on it is the same evidence D7 already accepts as resolving a taint. The commit's own intermediate tree was never shipped on its own: the merge squashes the change.

**Why unscoped only:** a scoped `ci` ran one surface's command. It vouches for nothing outside that surface, so it can't stand in for commits that may touch others.

**Why ancestry and not timestamps:** ancestry is a fact of the commit graph. Committer dates are set by whoever commits and can be anything. The issue's "postdates every commit" is achieved by ancestry. A commit created after the head `ci` is a new head with a new tree, so the old row no longer names it.

### D2. `vouched` is a distinct record, not a taint and not a gated classification

The row keeps the ledger honest. `gates stats` and the escalation record can still tell an individually gated commit (`ci` row on its own tree, classified as today) from one the head vouched for. Recording it as gated would erase the distinction, and recording it as a taint followed by `taint-clear` would report an incident where there was only a rebase.

`_existing_classified_shas` includes `vouched` rows, so a later audit never re-reports the commit.

### D3. Threat model: the taint still catches what it is for

The taint exists to catch a commit that slipped the hooks (`--no-verify`, a stripped `CLAUDECODE`). With vouching:
- **Merge outcome:** unchanged. Today such a commit taints, and a green full `ci` on the head clears it (D7), so the merge passes. With vouching, the same green head `ci` means no taint is recorded and the merge passes. The only difference is when the resolution happens.
- **What vouching can't do:** create the green head `ci`. That `ci` is a real run on the exact tree being merged. A head whose own commit slipped the hooks has a tree with no green row, so nothing vouches and it taints as before.
- **What's lost:** the taint row for a hook-slipping mid-branch commit that a later head `ci` covers. That incident is recorded as `vouched`, not as a taint. The commit still appears in the ledger by sha, so a reader can still find it, but it no longer counts as a taint incident. D7 already treated such a commit as resolved, so the loss is the incident count, not the gate. The proposal accepts that trade for the issue's cost.
- **The Stop hook's audit:** it runs at session stop, usually before any head `ci`, so a hook-slipping commit audited then still taints. Vouching only applies where a head `ci` already exists when the audit runs, which in practice is the merge's own audit after a rebase.

### D4. No read-only probe

Option (a), letting `gates taint check` run the audit read-only, would let a lane see the coming taint, but it would still have to pay a second full `ci` to clear it. D1 removes the second `ci` outright, so the probe isn't needed for #132. It stays a candidate if an orchestrator asks for one.

### D5. The sync route is unchanged

The shipped prompts already give only the `--no-commit`, then `gates run ci`, then `git commit` sync route (loop-hardening D4). Neither `skills/tdd-apply` nor `agents/tdd-implementer` offers rebase, so no prompt changes. A rebased lane now merges without the extra `ci`.

## Risks / Trade-offs

- **The taint count drops for hook-slipping commits a head `ci` later covers** (D3). Accepted, and the `vouched` row keeps them visible.
- **One ancestry check per otherwise-tainted commit.** That's cheap, and it runs only on a miss.
