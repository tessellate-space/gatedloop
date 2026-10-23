# Proposal: hook-correctness

## Why

A field adopter has run three unattended lanes plus a merge lane for two weeks. Two
reports from that run, #33 and #35 A, show the enforcement hooks misfiring in ways
that cost whole gate runs and halted lanes. Adopters paper over them with rules typed
into every dispatch brief. Every item below was checked against the code.

- **The merge hook loses the ref on a trailing redirect** (#33 item 1). An example is
  `git merge --squash x 2>&1`. The matcher returns an empty ref, the hook falls back
  to `main`'s tree, and it denies with a misleading "stale marker". Reproduced; a
  `cd … &&` prefix parses correctly. Related misfires: `openspec archive --help 2>&1`
  is read as archiving a change named `2`, and a heredoc body that mentions a gated
  command can trip a hook.
- **Syncing `main` into a change branch is gated as if it were integration** (#33
  item 2), and it can never be satisfied. A lane halted on it.
- **`clear-ci-marker.sh` wipes the whole marker store on any Write or Edit** (#33
  item 3, #35 rule 5). That includes scratch files, planning files, and another
  lane's work. The hook's own header calls it "belt-and-suspenders": the `ci` marker
  is keyed on the *staged* tree, and Write/Edit never touch the index. So the hook
  adds nothing, and it destroys valid evidence. One wipe cost a 250 s full `ci`
  re-run.
- **The propose gate refuses on a detached HEAD** (#33 item 4). That is exactly where
  a merge recipe parks the primary checkout. The refusal is also inconsistent: some
  artifact files are refused and others are not.
- **A "stale" commit denial doesn't say why** (#33 item 8). The usual cause is files
  staged after the gate ran.
- **Any non-`main` branch is treated as a change** (#33 item 9, #35 rule 3). A
  `plan/<name>` branch or a docs branch grows its own ledger. That's the stray
  `.specloop/runs/plan/` and `<branch>.jsonl` files this repo keeps cleaning up.
- **A lane forced a checkout of a branch another worktree held** (#33 item 10). Its
  commit moved the ref under the primary checkout.
- **#35 A's generic lane rules** belong in the implementer's own definition, not in
  every dispatch brief.

## What Changes

- **The matcher skips redirections and heredoc bodies.** Redirect tokens (`2>&1`,
  `>file`, `2>/dev/null`, `<file`) are never taken as arguments. A heredoc's body is
  never scanned. A guarded command with `--help` or `-h` is not a guarded invocation.
  When a merge matches but no ref parses, the denial says "no incoming ref parsed
  from the command", never "stale".
- **A merge into a branch other than the integration target is not gated.** Examples
  are `main` into a change branch, and one branch into another. The merge hook guards
  integration only.
- **`clear-ci-marker.sh` is removed.** The marker's tree key already invalidates it on
  any staging change. The "stale" denial becomes the clear signal instead (next item).
- **Stale denials explain themselves.** The commit hook compares the marker's tree
  with the staged tree. It says "N file(s) were staged after `gates run ci` ran:
  <paths> — re-run the gate", or names the paths that differ.
- **The propose gate resolves a detached HEAD from the change's state.** It decides
  "unproposed" from whether the change directory is tracked on the integration
  target, never from HEAD. It treats every artifact path the same way.
- **A branch is a change only when `openspec/changes/<branch>/` exists.** Other
  branches write no ledger row. A `--change` value containing `/` is refused. On a
  detached HEAD with no `--change`, `gates run` warns that no row is written.
- **Commits refuse a branch checked out in another worktree.** The commit hook and
  `gates discipline` deny it. `tdd-implementer` forbids forced checkouts.
- **The implementer carries #35's generic rules:**
  - run gates in the foreground, and never end a turn waiting on one;
  - stage before the gate, then commit;
  - delete lines in a test file with Edit or `git rm`, never a line-range stream
    edit.

  Rules 1, 3 and 5 need no prompt text: this change fixes their causes. Rule 7 is
  already in the agent.

## Capabilities

### Modified Capabilities

- `loop-enforcement`: the matcher's handling of redirections, heredocs and help
  flags; integration-only merge gating; no marker clearing on edit; self-explaining
  stale denials; detached-HEAD proposal resolution; branch-to-change resolution;
  worktree-shared branches.

## Impact

- `hooks/_gate_match.py`; `hooks/gate-merge.sh`; `hooks/gate-commit.sh`;
  `hooks/gate-propose.sh`; `templates/git-hooks/pre-commit`.
- `hooks/clear-ci-marker.sh` is deleted, and its entry is removed from
  `hooks/hooks.json`.
- `bin/gates`: `_resolve_change_name`, `gate-marker check`'s stale diagnosis,
  `discipline check-propose`, and the worktree check.
- `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md` get the prompt rules.
- `tests/`: matcher cases, and hook and shim cases for each item.
- Ships in 0.5.0.
