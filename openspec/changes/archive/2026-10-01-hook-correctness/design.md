# Design: hook-correctness

## Context

`harden-hook-matching` gave the hooks one tokenizing matcher, and
`fix-marker-mechanics` keyed markers on the ledger-normalized staged tree. Both are
sound. The defects in #33 and #35 A sit at their edges: tokens the matcher doesn't
classify, a hook written before the tree key made it redundant, and "branch = change",
which was never checked against the change directory.

## Decisions

### D1. The matcher classifies redirections, heredocs and help flags

This is in `hooks/_gate_match.py`, after `shlex` tokenizing:

- **Redirections are dropped before argument extraction.** A token is a redirection
  when it matches `^\d*[<>]{1,2}(&\d+|&-)?$`, with the following token taken as its
  target when the operator has none attached. It is also one when it matches
  `^\d*[<>]{1,2}\S+$`, with the target attached. `2>&1`, `> out`, `2>/dev/null`,
  `<in` and `&>log` are all dropped.
- **Heredocs.** For each `<<WORD`, `<<-WORD` or `<<'WORD'` on a line, the lines after
  it up to and including the line equal to `WORD` are excluded before tokenizing.
  The heredoc body is data. The line that opens the heredoc, and any line after the
  terminator, are still matched as commands.
- **Help.** A matched invocation whose arguments contain `--help` or `-h` is reported
  as `matched=0`.
- **Empty ref.** When `git-merge` matches and no ref remains, the matcher emits
  `ref=''` and `ref_parse=failed`. `gate-merge.sh` then denies with:

  > specloop: merge denied — no incoming ref could be parsed from the command. Run
  > the merge as a bare `git merge --squash <change>` line.

  Before, it fell back to HEAD's tree and reported "stale".

The existing unbalanced-quote fallback (fire generously, never bypass) is unchanged.

### D2. Merge gating applies to the integration target only

`gate-merge.sh` resolves the current branch and the integration target with
`_resolve_merge_target`, the same resolution the propose gate uses. When the current
branch is not the target, the hook exits 0 before any marker work.

A detached HEAD is treated as integrating when HEAD equals the target's tip. That is
the merge recipe's detach onto `origin/main`. Otherwise a detached HEAD is not
integrating.

### D3. `clear-ci-marker.sh` is deleted

The hook's stated purposes, and why neither holds:

1. **"A clearer signal: no marker instead of stale".** D4 makes the stale denial
   explain itself, which is clearer than "no marker".
2. **"An edit that coincidentally restores the same tree hash".** If the staged tree
   equals the tree `ci` passed on, the commit is exactly what was verified. Allowing
   it is correct, not a loophole.

The costs are real: a clear of every marker in the store, on every write, in every
repo the session touches. So the hook and its `hooks.json` entry go. `gates
gate-marker clear` stays as a manual command.

The loop-enforcement requirement "Commit is blocked unless CI passed on the tree being
committed" already specifies tree-keyed invalidation. That requirement is unchanged.

### D4. Stale denials list what changed

`gates gate-marker check ci` already knows the recorded tree and the current staged
tree. On a mismatch it runs `git diff-tree -r --name-status <recorded> <staged>` over
the ledger-normalized trees:

- When every entry is `A` (added), it prints "N file(s) were staged after `gates run
  ci` ran: <paths> — re-run the gate". This is #33 item 8's most common case.
- Otherwise it prints "the staged tree differs from the one `ci` passed on: <status
  path> …", listing at most 10 paths and then "and N more".

`gate-commit.sh` and the git-layer pre-commit hook print this output as their denial.

### D5. The propose gate reads change state, not HEAD

`discipline check-propose` now does the following:

- **Resolve the change from the written path.** The path is
  `openspec/changes/<name>/…`, so the change name is known without HEAD.
- **Allow or refuse on implementation state.** A planning write is allowed unless the
  change is in implementation. "In implementation" means a branch named `<name>`
  exists with commits beyond the target, or the ledger holds a `task-start` row for
  it. Otherwise the write is allowed, whether HEAD is `main`, detached, or a
  `plan/*` branch. HEAD is consulted only to allow the always-allowed cases faster.
- **Decide "unproposed" from tracking.** It means the change directory is not tracked
  at the integration target's tip (`git ls-tree <target> openspec/changes/<name>`).
  The label goes on a directory that really is untracked, and never on a tracked
  one.
- **Treat every planning artifact the same.** `proposal.md`, `design.md`,
  `specs/**`, `adr/**` and any artifact the change's schema declares get identical
  treatment. `tasks.md` stays excluded, because checkbox flips happen during
  implementation.

This keeps the original intent (design D9 of `harden-unattended-loop`: don't author a
plan from inside the change's implementation). It stops using HEAD as a stand-in for
that.

### D6. Branch-to-change resolution checks the change directory

`_resolve_change_name(root, given)` resolves as follows:

- **`given` contains `/`** → refuse with "change names never contain '/'; use
  `<basename>`", exit 1.
- **`given` is set** → return it. An explicit name is trusted, as today.
- **Current branch is `main`, `master` or the target** → `None`.
- **`openspec/changes/<branch>/` exists** → return `branch`. The active directory is
  checked first, then `openspec/changes/archive/*-<branch>/`, so that a just-archived
  change still resolves for its merge row.
- **Otherwise** → `None`, so no ledger row is written. This covers `plan/*`, docs
  branches, and the stray files this repo kept deleting.

When `gates run` is on a detached HEAD with no `--change`, it prints one line to
stderr: "detached HEAD — no ledger row written; pass --change <name> to record one".

### D7. Worktree-shared branches are refused at commit

This is a new `gates discipline check-worktree` command. It parses
`git worktree list --porcelain`, and exits 1 when the current branch appears in more
than one worktree, naming each one. `gate-commit.sh` and the git-layer pre-commit hook
call it before the marker check.

`agents/tdd-implementer.md` gains: "never `git checkout -f`,
`--ignore-other-worktrees`, or `git switch --discard-changes` onto a branch another
worktree holds; if a checkout is refused, halt with `environment`".

### D8. #35's lane rules

| # | Rule | Where it goes |
|---|---|---|
| 1 | one action per call; don't chain gated lines | fixed by D1; no prompt text |
| 2 | gates in the foreground; never end a turn waiting on one | `tdd-implementer` §5, and `tdd-apply` 5f |
| 3 | bare change name | fixed by D6 |
| 4 | stage, then gate, then commit | `tdd-apply` 5h, and `tdd-implementer` §2 (the D4 denial also explains it) |
| 5 | printf for message files | fixed by D3 |
| 6 | delete test lines with Edit or `git rm`, never a line-range stream edit | `tdd-implementer`, one line: the host's auto-mode classifier reads a line-range deletion in a test file as removing tests |
| 7 | a refusal is a full stop | already in `tdd-implementer` §5 |

The prompt text names no stack tool. Rule 6 says "a line-range stream edit"; it does
not name a specific command.

## Risks

- **The heredoc rule could hide a real command after the heredoc on a later line.**
  In a single Bash tool call, lines after a heredoc's terminator are further commands.
  D1 therefore excludes only up to the terminator word's line, and matches the lines
  after it as commands.
- **Removing the clear hook changes a user-visible message** from "no marker" to a
  more specific "stale". That's the intent.

## Out of scope

- Lock hygiene and ledger-grade commits (#33 items 5–7): `lock-and-ledger-hygiene`.
- The merge step itself (#36): `merge-step`.
