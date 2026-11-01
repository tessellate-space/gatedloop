## Context

The `pre-push` hook (git-layer-enforcement D3) runs `gates discipline check-push <sha> --remote-ref <ref>` for each ref a push updates, inside an agent session only. An update of the merge target passes when the pushed commit is proven, in one of two ways:
- a `merge` row names it, or names an ancestor followed only by ledger and planning paths;
- the merge gate's incoming-tree checks hold for its tree: a `live-check` marker, a full `ci` marker, `verify` where declared, and per-change taint, lock and acceptance.

`_push_changes` decides which changes a pushed commit "carries in". It lists local branches merged into the pushed commit whose `openspec/changes/<name>/` is still in its tree. The refusal names that change in `gates merge <name>`, or prints `<change>` when there are none or several.

A release commit changes only `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and `CHANGELOG.md`, so no merge row ever names it. In this repository it has no live-check marker either, because no surface declares one.

## Goals / Non-Goals

**Goals:**
- `scripts/release publish` never leaves a half-published release because an agent session ran it.
- A push refusal names a change only when the push actually carries that change's commits.

**Non-Goals:**
- Letting an agent session publish a release.
- A general "release-grade" push allowance for adopters.

## Decisions

### D1. No release-grade push allowance in the shim; `publish` refuses up front instead

The alternative was a third proof in `check-push`. It would allow a pushed commit whose diff against its parent is only version fields plus a changelog, with a green unscoped `ci` row on its tree and a version above the latest tag. It fails the rejection test:
- **It would have to know a stack.** Which files hold the version is a binding: `.claude-plugin/*.json` exists only in a Claude Code plugin, an adopter's release bumps `package.json`, `pyproject.toml` or nothing at all, and the changelog's name and format vary.
- **It would open a hole.** "Only these files changed" written generically is a path allow-list, and a path allow-list on the merge target is a way past the gate.
- **It enforces no stated guarantee.** The guarantee the hook enforces is that an agent can't put unproven commits on the target. A release commit is the maintainer's act, and the maintainer is a human.

So the fix stays in this repository's tooling. `publish_preconditions` gains one more precondition: run `gates discipline agent-session`, which is the same check the hooks use and reads `discipline.agent-env`, and refuse when it exits 0. It refuses before the first write, alongside the other failed preconditions, as RELEASING.md already promises. The refusal:
- writes the release notes to a stable path, `.gatedloop/out/release-notes-vX.Y.Z.md`, which is ignored and per-checkout;
- prints the full command sequence, the same commands `publish_steps` would run, to paste into a terminal outside the agent session.

It doesn't print a `env -u CLAUDECODE` form. The point is that a human runs it.

`publish` already requires a clean, current `main`. A maintainer who follows the printed commands outside a session gets the same fixed step order and the same tag-after-push guarantee.

### D2. A change branch is carried in only if it brings commits the target lacks

`_push_changes` additionally drops a branch whose tip is an ancestor of the merge target's remote-tracking ref, `<remote>/<branch>` from `_resolve_merge_target`, when that ref resolves. Such a branch adds nothing to the push. This is the case of a freshly created change branch, or a change already merged.

If the remote-tracking ref doesn't resolve, as in a repository with no fetch, behaviour is unchanged. This needs no git-hook template change and no new argument, because the hook's `remote_sha` isn't needed.

### D3. A refusal that carries no change says so

When `_push_changes` returns nothing, the refusal's last line is no longer "integrate through `gates merge <change>`". It reads: "commit X belongs to no change in flight — nothing `gates merge` can prove. A commit like this reaches the target through a pull request, where the forge's checks apply, or a push outside an agent session." With several changes it keeps `gates merge <change>` and lists them by name.

The unmet checks are still listed above the last line, unchanged.

## Risks / Trade-offs

- **[A maintainer who wants to publish from a session can't]** → Intended. A release is the maintainer's act, and the refusal prints everything needed to finish it in one paste.
- **[D2 misses a carried-in change when the remote-tracking ref is stale]** → A stale ref is behind the true remote tip. A branch whose tip is an ancestor of a *behind* ref is also an ancestor of the true tip, so D2 can only drop branches the push truly doesn't carry. The worst case is the old behaviour, naming too many.
- **[D3's wording mentions pushing outside a session]** → This is the documented boundary of the hook: SETUP and AUTOMATION already say a human's push isn't gated here and the forge covers it. It's addressed to the maintainer reading a refusal, not offered to the agent as a route.
