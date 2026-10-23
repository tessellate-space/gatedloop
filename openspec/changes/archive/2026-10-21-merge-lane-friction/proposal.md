# Proposal

## Why

Two friction reports from a multi-lane loop on 0.5.0: one orchestrator merging serially, and up to three implementer lanes running `ci` on the same machine.

**#43: a lock-wait timeout is reported as a red merged tree.** Step 3 of `gates merge` treats any non-zero `ci` exit as "the unscoped `ci` is red … The merged tree is what failed". But exit 75 with the `specloop: lock busy` prefix means the gate **never ran**: the machine-wide lock was held by a lane's own `ci` past `concurrency.max-wait-seconds`. The verdict is wrong, and so is the advice ("sync the target into the change branch and fix it there"). Merges also get no priority over lane `ci` runs, so with lanes running `ci` back to back a merge can time out again and again, and the merge queue stalls behind work that isn't merging.

**#44: a lane can't sync the target into its branch.** An agent fast-forwarding an empty change branch to `origin/main` was refused. I reproduced the merge hook against both `main` and v0.5.0, with every shape tried, including an empty branch at the same commit as a stale local `main`, and a detached HEAD. The hook allows all of them: a sync into a change branch is not an integration merge. The issue doesn't quote the refusal.

The likely source is Specloop's opt-in permission scaffolding. It writes `"ask": ["Bash(git merge *)"]` into `.claude/settings.local.json`, so **every** `git merge` an agent issues prompts, including a lane's sync. A background or unattended agent can't answer a prompt, so to it the prompt is a refusal. That rule predates `gates merge`. Integration merges are now performed by `gates merge` (local mode) or the forge (pull-request mode), and the merge hook already gates any raw integration merge. The human checkpoint belongs on `gates merge`, not on every `git merge`.

## What Changes

- **`gates merge` reports what actually happened when a gate didn't run.** At step 3 (`ci`) and step 5 (`confirm`), an exit 75 is a "not run" outcome, never a red verdict:
  - for a lock-busy 75, it names the gate, the holder and the wait;
  - for a precondition 75, it names the environment.

  It still restores the checkout, commits nothing, and exits 75 instead of the step number, so a caller's retry-on-busy rule applies as for any gate. A red exit keeps today's message.
- **A merge waiting on a serialized lock goes first.**
  - While `gates merge` waits on a serialized gate's lock, it holds a **priority claim** beside the lock. Any other waiter that sees a live claim keeps waiting, even when the lock comes free, so the merge takes it next.
  - The holder is never pre-empted.
  - A stale claim, left by a dead pid, is ignored.
  - The merge's own wait may be bounded separately by `concurrency.merge-wait-seconds`, which defaults to `max-wait-seconds`.
- **The scaffolding's checkpoint moves to `gates merge`.**
  - `gates-init` step 9 writes `"ask": ["Bash(gates merge *)"]` instead of `"Bash(git merge *)"`, and the docs say why.
  - `gates doctor` warns when `.claude/settings.local.json` still asks on `Bash(git merge *)`, naming the replacement.
  - A recurring `0.6.0` catalogue item offers the edit in `/specloop:upgrade`, using a new detector kind, `file-contains`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `merge-step`:
  - a gate that didn't run is reported as not run;
  - a waiting merge has lock priority;
  - the permission scaffolding's checkpoint is `gates merge`, and doctor flags the old rule.

## Impact

- `bin/gates`:
  - `_merge_prove_merged_tree` and the step-5 confirm handling;
  - the lock wait (`_gate_lock`) and its priority claim;
  - `concurrency.merge-wait-seconds` in validation and the schema;
  - the doctor row;
  - the `file-contains` detector.
- `commands/gates-init.md`, `adoption/catalog.json`.
- SETUP, AUTOMATION.
- Tests.
