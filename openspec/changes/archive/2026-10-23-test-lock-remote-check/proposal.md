# Proposal

## Why

The authored-test lock is checked in exactly one place: the staged index at commit time, by the two commit hooks. Nothing checks it at the merge head, and nothing checks it in CI. A locked test edited through any path the commit hooks did not see (a `--no-verify`, a human edit on the branch, a commit from a host with no hook) reaches `gates merge` and the forge with the lock silently broken, and the "implementer can only make the tests pass or file a defect" guarantee stops at the laptop. The 2026-10-22 survey found one competitor (a test-step integrity kit) whose hash lock is re-verified server-side in CI; that is the half of the lock this plugin is missing.

## What Changes

- **The lock is checkable at any commit.** `gates tests check --ref <commit>` evaluates the lock against a commit's tree and the ledger at that commit, for every task of the change, instead of the staged index: each placed path holds exactly its placed content (or its base content where a defect or halt voided the placement), the holding area matches the handoff, and every placed task with tests has a red `unit` run recorded after placement. A change with no handoff passes with "no authored tests".
- **Proving the head includes the lock.** `gates merge` step 1 runs the check against the change branch's head in both integration modes; a broken lock refuses the merge with the path and the task named.
- **A `tests` commit status.** `gates marker publish tests` runs the check against the sha's tree and posts a `<prefix>/tests` status carrying the tree, success only when the lock holds; `gates marker check-remote tests <sha>` verifies it. The prefix is the plugin's status prefix, whatever the pending rename makes it.
- **CI and the example follow.** This repository's workflow publishes the `tests` status on every pull request, the documented branch protection requires it next to `ci`, and `docs/running-at-scale.md` shows the same step.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-discipline`: the lock becomes verifiable at a commit, not only at the staged index.
- `merge-step`: proving the head requires the lock to hold on the incoming tree.
- `loop-enforcement`: `tests` joins the publishable statuses, with computed evidence instead of a marker.

## Impact

- `bin/gates`: `tests check --ref`; the check in `_merge_prove_head`; `marker publish tests` and `check-remote tests`.
- `.github/workflows/gatedloop.yml`, `docs/running-at-scale.md`, AUTOMATION.md (branch protection list), SETUP.md (the `--ref` form and the status), README.md (the agent table row for `test-author`); tests.

Rejection test: authors nothing, names no stack command, and makes a stated guarantee (locked tests) enforceable where it is not today: at the merge and at the forge.
