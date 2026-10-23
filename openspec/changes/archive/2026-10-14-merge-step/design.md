# Design: merge-step

## Context

Most of what a merge needs already exists in pieces:

- the merge hook's incoming-tree checks: live-check marker, full-scope `ci`, taint and
  acceptance;
- `gates integration`, which prints the declared mode;
- `gates ledger record-merge`;
- ledger-grade commits;
- `/specloop:archive`.

What's missing is the sequence, the recovery when a step fails, and the one-at-a-time
rule. #36's adopter wrote all three by hand. This change writes them once, in code.

## Decisions

### D1. The shim drives the steps, and applies the hooks' checks itself

`gates merge` is a subcommand, not a prompt. Ordering, rollback and publishing are
decisions the loop mustn't improvise ("selection in code").

Because the shim invokes `git` as a subprocess, the Bash `PreToolUse` hooks don't see
its `git merge` or `git commit`. The design doesn't treat that as a bypass:
- step 1 calls the same functions the merge hook calls (`gate-marker check`,
  `acceptance check`, the taint check), on the same incoming tree;
- step 3 calls the same `discipline check-commit` the commit hooks call;
- the git-layer pre-commit hook still fires on its commits when `CLAUDECODE` is set.

`loop-enforcement`'s "rephrasing to get past a denial" rule is about getting around
a check. `gates merge` runs the checks itself, and it's the sanctioned path.

### D2. Step by step (local-squash-merge)

In this section, "target" is the tip of the integration target, as
`_resolve_merge_target` resolves it (for example `origin/main`), and "primary" is the
worktree `gates merge` runs in.

0. **Preconditions.**
   - Acquire the `merge` lock (D4).
   - `<change>` resolves to a directory-backed change (`hook-correctness` D6), and
     the branch `<change>` exists.
   - The primary worktree is clean, apart from untracked files.
   - Record where HEAD is, so it can be restored.
1. **Prove the head.**
   - If `.specloop/runs/<change>.jsonl` is modified on the branch, commit it there at
     ledger grade ("record trailing ledger rows"). Only a checkout of the branch in
     this worktree is used; if the branch is checked out elsewhere, commit it there
     with `git -C <that worktree>`, since that is the lane's worktree.
   - Run the incoming-tree checks against `<change>^{tree}`. Any refusal exits
     non-zero with the checks' own text.
   - Print `gates acceptance brief <change>`'s coverage lines. They are advisory
     unless an acceptance policy is declared, in which case the acceptance check has
     already enforced them. This is #35 C: coverage is no longer on request, it is
     printed at every merge.
2. **Integrate.**
   - `git fetch` (skipped when the target is local-only), then
     `git checkout --detach <target>`, then `git merge --squash <change>`.
   - On a conflict: `git merge --abort` (or `git reset --merge`), restore HEAD, and
     exit 2 with the conflicting paths.
3. **Prove the merged tree.**
   - `gates run ci` with nothing scoped: the full oracle, on the staged squash.
   - Red: `git reset --hard <target>`, restore HEAD, exit 3.
   - Green: commit the squash with the message "`<change>`: `<proposal title>`", plus
     the change's task commit subjects as a body.
4. **Record.**
   - `gates ledger record-merge <change> --sha <squash sha>`.
   - Commit the row at ledger grade, on top of the squash.
5. **Confirm.**
   - If `confirm` is declared, run `gates run confirm` on the merged tree.
   - Red or 75: `git reset --hard <target>`, restore HEAD, append a `confirm` failure
     row to the change's ledger on its branch and commit it there, then exit 5.
6. **Archive and publish.**
   - `openspec archive <change> --yes`, then the archive commit, including the
     `openspec/specs` sync, as `commands/archive.md` does.
   - `git push origin HEAD:<target branch>`.
   - Rejected as non-fast-forward: `git reset --hard <target>`, restore HEAD, and go
     back to step 2 once. A second rejection exits 6.
   - Success: restore HEAD to the recorded position. When that position was
     `<target branch>` itself, fast-forward it to the pushed tip.

Each exit code names its step, so an orchestrator can route on it without parsing
prose. The step's own message is always printed too.

**Only one push, at the end,** because the remote target never sees an unconfirmed
tree. That is #36's "nothing lands until proven", and the reason local mode is worth
owning.

### D3. `confirm` is a gate, not a recipe name

#36 proposed `merge: { confirm: <recipe name> }`. Specloop already maps an abstract
name to a project command through `gates:`, so `confirm` becomes one more optional
gate. It runs through `gates run confirm`, which gives it the same precondition
(`requires`), ledger and output treatment as every other gate.

A project's lane-up, smoke and lane-down steps belong in that one command body, or in
its `requires` precondition. No `merge:` block is added; `integration:` already holds
the mode.

### D4. The merge lock

The lock reuses `_gate_lock`'s mechanism under the name `merge`. It is always
serialized, with no manifest declaration needed, because two local merges into one
target from one machine can't both be right. The bound is
`concurrency.max-wait-seconds`, from `lock-and-ledger-hygiene`. On a busy lock the
command exits 75 with `specloop: lock busy`.

### D5. Triggers: a command for people, an agent for orchestrators

- **`commands/merge.md` (`/specloop:merge <change>`).** It shows the acceptance
  brief, confirms with the person once, runs `gates merge`, and reports the step
  outcome. On exit 2 (conflict), it offers to sync the target into the branch.
- **`agents/merge-runner.md` (Sonnet).** Tools: `Bash`, `Read`, `Edit`. It runs
  `gates merge <change>`. On exit 2 it merges the target into the change branch. That
  is ungated since `hook-correctness` D2, and it happens in the lane's worktree when
  one exists. It resolves only mechanical conflicts: both sides added different lines
  to a list, or the imports are reordered. It then re-runs `gates run ci` and `gates
  run live-check` on the branch head and retries `gates merge` once. Anything else,
  or a second failure, halts with cause `other` and the paths.
- **`tdd-apply` 7.5.** Its local-squash branch becomes `gates merge <change>` and
  nothing else. Steps 5 ("record the merge") and the archive hand-off are now inside
  the command. The pull-request branches are unchanged until `merge-pull-request`.
- **`tdd-implementer`.** Unchanged, apart from one sentence saying it never runs
  `gates merge`.

### D6. What stays the adopter's

The environment that `confirm` and `live-check` run on, and whatever recipes bring it
up, stay the adopter's. SETUP.md says so in the merge section. `gates-init` offers to
bind `confirm` when the project already binds `live-check`. `adoption-prompts` gains
a `confirm-gate` item (since 0.5.0, detector `manifest-key gates.confirm`, applies
when `gates.live-check` is declared).

## Risks

- **A crash between the local commits and the push** leaves the primary worktree
  detached with unpushed commits. Nothing was published. A rerun of `gates merge`
  detects a detached HEAD whose tip carries this change's merge row, and restores the
  recorded HEAD before starting. The previous HEAD position is written under
  `.git/specloop/merge-state`, so that detection doesn't depend on memory.
- **The archive step fails** (an OpenSpec error). Nothing has been pushed at that
  point. The merge halts with exit 6 and the OpenSpec message.

## Out of scope

- Pull-request mode, commit statuses and a CI action: `merge-pull-request`.
- Dispatching merges from an orchestrator: `dispatch-lanes`.
