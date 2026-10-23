# Design

## Context

- **The serialized-gate lock.** Gates named in `concurrency.serialize` take a machine-wide `flock` under the common git dir. A waiter polls every 0.2 s up to `concurrency.max-wait-seconds` (default 480), then raises `_LockBusy`. The gate exits 75 with the stable prefix `specloop: lock busy`, without running. A precondition (`requires`) failure is also exit 75, with its own message.
- **Step 3 of `gates merge`** calls `cmd_run(ci, full)` and treats every `rc != 0` as a red merged tree. Step 5 does the same for `confirm`.
- **Permission scaffolding** (`gates-init` step 9) writes `allow: [Bash(gates *), Bash(openspec *), Bash(git commit *)]` and `ask: [Bash(git merge *)]`. In Claude Code an `ask` rule is evaluated before an `allow` rule, so a more specific `ask` still prompts under a broad `allow`.

## Decisions

### D1. Exit 75 at a merge step is "not run"

In `_merge_prove_merged_tree` (step 3) and the confirm step (step 5), `rc == 75` is handled before the red branch:
1. abandon the integration, restoring the checkout and committing nothing, exactly as for red;
2. raise `_MergeHalt` with exit **75**, not the step number;
3. use a message built from the captured gate output:
   - **lock busy:** `step 3 (prove the merged tree) did not run: the 'ci' lock is still held by <holder> after <wait>. Nothing was committed; the checkout is restored. Re-run gates merge <change>; nothing about the merged tree is known yet.`
   - **precondition:** the same, with the precondition's own message.

Exit 75 from `gates merge` then means what it means for every gate: not judged, retry when the environment allows. `merge-runner` and the tdd-apply 7.5 text already treat 75 as retryable; their wording is checked and updated if it says otherwise.

### D2. A merge's priority claim

When `gates merge` waits on a serialized gate's lock, at step 3 or step 5 via `cmd_run`:
- **It holds a claim.** Before its first acquire attempt, it writes `<lockfile>.priority` with `{"pid": <merge pid>, "ts": …}`, and removes it once it acquires the lock or gives up.
- **Other waiters defer to it.** A non-merge waiter checks for the file before each acquire attempt. If the claim's pid is alive and isn't itself, it doesn't try to acquire even when the lock is free; it keeps polling, and its own wait clock keeps running.
- **A claim with a dead pid is ignored and removed** by the next waiter that sees it.
- **Only one claim at a time.** A second merge cannot be waiting, because merges are already serialized by the `merge` lock.

The holder is never interrupted. The merge waits at most for the run in progress, plus nothing queued behind it.

`gates lock status` shows the claim, as `ci: held by pid N; merge pid M waiting with priority`.

### D3. The merge's wait bound

`concurrency.merge-wait-seconds` is an optional positive integer. It bounds `gates merge`'s own lock waits and defaults to `max-wait-seconds`. The merge already holds priority, so its wait is one holder's run. A project whose full `ci` is longer than the general bound can raise this alone.

### D4. The checkpoint moves to `gates merge`

`gates-init` step 9 writes:

```json
{ "permissions": {
    "allow": ["Bash(gates *)", "Bash(openspec *)", "Bash(git commit *)"],
    "ask":   ["Bash(gates merge *)"] } }
```

The prose says why:
- integration happens through `gates merge` (local) or the forge (pull-request mode);
- the merge hook still gates a raw integration `git merge`;
- an `ask` on every `git merge` stalls unattended lanes on a routine sync.

The human checkpoint is unchanged in intent: the command that integrates still always asks.

### D5. Diagnosing the old rule

- **Doctor.** A new row, `merge-checkpoint`. It warns when `.claude/settings.local.json` exists and its `permissions.ask` contains `Bash(git merge *)`, naming the replacement and that unattended lanes stall on it. It is ok otherwise, including when the file is absent.
- **Detector.** A new detector kind, `file-contains`, with fields `path` and `text`. It counts as acted on unless the file at `path`, relative to the repo root, contains `text`. Pure, like the others.
- **Catalogue item.** `merge-checkpoint`: since 0.6.0, recurring, applies when `.claude/settings.local.json` exists, detector `file-contains` for `"Bash(git merge *)"`. Its action is `confirm`, describing the one-line edit for the adopter to make. Specloop never edits permission files without a yes.

## Risks

- **A waiter starved by a long merge queue.** Merges are serialized and each claim lives only while one merge waits, so a lane waits at most for the merges queued at that moment, bounded by its own `max-wait-seconds`. Past that bound it gets the usual lock-busy 75 and retries.
- **#44 had another cause.** The refusal text isn't in the issue, so this can't be confirmed from here. D4 is right on its own merits, because an `ask` on routine syncs stalls any unattended lane.
