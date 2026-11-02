## Why

Publishing 0.10.0 from a Claude Code session failed at `git push` (#125). The pre-push hook gates every push to `main` inside an agent session, and only a `merge` ledger row or the merge gate's incoming-tree checks prove a commit. A release commit (`Release X.Y.Z`: the version fields and `CHANGELOG.md`) belongs to no change, so it can never be proven. `scripts/release publish` found that out after its commit step, which leaves a half-published release for the maintainer to finish by hand.

The refusal also named the wrong change: "integrate through `gates merge loop-hardening`". `_push_changes` counts every local change branch whose tip the pushed commit contains. A change branch freshly created from `main`, with no commits of its own yet, is contained in anything later, so it gets named for a commit it has nothing to do with.

## What Changes

- **`scripts/release publish` refuses up front inside an agent session**, before its first write, and prints the exact command sequence for the maintainer to run outside one, with the release notes written to a stable path. This is repo tooling, not shipped behaviour. RELEASING.md says that `publish` runs outside an agent session.
- **The push gate counts a change branch as carried in only when it brings commits the merge target doesn't already have.** A branch whose tip is already an ancestor of the target's remote-tracking ref is left out.
- **A refused push that carries no change says so** ("commit X belongs to no change in flight") instead of naming one or printing `<change>`, and says what proves such a commit: a pull request through the forge, or a push outside an agent session, where the forge's branch protection applies.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `loop-enforcement`: the push gate's change attribution and its refusal for a commit no change owns.
- `plugin-release`: `publish` refuses inside an agent session before any write.

## Impact

- `bin/gates`: `_push_changes` and the refusal text in `_check_push`.
- `scripts/release`: a new `publish` precondition.
- `RELEASING.md`.
- `tests/`: the push-gate attribution and the publish refusal.
- No git-hook template changes, so adopters don't need to re-run `gates hook install`.
