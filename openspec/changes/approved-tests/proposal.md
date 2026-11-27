# Proposal: approved-tests

## Why

0.12.0's plan loop authors and reviews every task's tests before approval. Those tests are then thrown away. The approval doesn't cover them, nothing hands them off, and the test author runs again after approval for the same tasks. 0.12.0's notes list this as "Not yet", together with the second gap: the `gatedloop/preflight/<change>` snapshot branch has to be deleted by hand once the change is archived. An adopter running `loop.plan-preflight: run` pays for the author twice per change and keeps a list of branches to prune.

Rejection test: this makes a stated guarantee enforceable. The tests the approver saw are the tests the implementation is held to. It also gets a team running faster, because one author run per change replaces two. It authors no artifact and names no stack command.

## What Changes

- **The approval covers the snapshot.** `gates plan save` records the snapshot's tree in the change's `.openspec.yaml` as `x-gatedloop-preflight-tree`. When that key is present, the approval sha covers it, so changing the held tests after approval invalidates the approval like any other plan edit. A change without the key hashes exactly as today.
- **`gates tests adopt <change>`.** On the change branch after approval, it finds the approved snapshot on the local or remote preflight branch and checks its tree against the bound one. It then copies into the holding area every task whose brief digest still matches. It prints the adopted tasks and the stale ones, which are tasks whose inputs moved since approval. Only the stale tasks go to the test author. The usual `gates tests handoff` follows, and its row records the snapshot tree and the adopted tasks.
- **The loop adopts before it authors.** `/gatedloop:tdd-apply` and the orchestrator run `gates tests adopt` first, and dispatch the author only for the tasks it reports stale.
- **The branch is deleted after archive.** In direct mode, `gates merge` deletes the local and remote `gatedloop/preflight/<change>` after its push succeeds. In pull-request mode, `gates record-merged` does it once the archive is recorded. A failed deletion is reported and never fails a merge that has already published.
- Opt-in by construction: only a change whose plan carries the key is affected, and only `loop.plan-preflight: run` writes it.

## Capabilities

### Modified Capabilities

- `plan-preflight`: the approval binds the snapshot, and its branch is cleaned up.
- `test-discipline`: adoption into the holding area, and what the handoff records.
- `merge-step`: the snapshot branch is deleted after the push.

## Impact

- `bin/gates`:
  - `_plan_save` writes the key;
  - the approval sha functions read it;
  - a new `tests adopt` subcommand;
  - `_tests_handoff` records the adoption;
  - `_merge_publish`'s caller and `cmd_record_merged` delete the branch.
- `skills/tdd-apply/SKILL.md`, `commands/orchestrator.md`, `agents/test-author.md` (author only the tasks it is given), `commands/propose.md` and `commands/planner.md` (commit the key after the final save).
- `tests/` and `tests/contract.json`: a new subcommand and two new handoff-row fields, both additive.
- `SETUP.md`, `AUTOMATION.md`, `docs/status.md`: the "delete by hand" line goes.
