# Proposal

## Why

The repository is going public, and issue #31's name collision now blocks it. Re-verified on 2026-10-22, the name is crowded in exactly this niche:
- ten exact-name `specloop` / `spec-loop` repositories on GitHub;
- a `SpecLoop` Rust CLI published as `specloop-cli` on crates.io;
- an OpenSpec → loop project for Claude Code;
- a Claude Code spec plugin.

The maintainer chose **gatedloop**, the README's own phrase for what the plugin runs. On 2026-10-22 it was free on npm, PyPI and crates.io, and no GitHub repository had that exact name. The research also covered and rejected `gatecloser`, `specgates` and an `oracle…` name, which raised a trademark risk.

A name is more than text here. Adopters' repositories hold Specloop's committed state:
- `.specloop/` ledgers and authored tests;
- `x-specloop-*` approval and epic keys in `.openspec.yaml`;
- `specloop/<gate>` commit statuses their branch protection requires;
- `specloop.*` rule ids;
- Specloop's markers in composed git hooks.

So the rename follows `rename-to-gates`. The old names keep working **loudly** for exactly one release, with a stated expiry, and a migration command moves a project across.

## What Changes

- **Plugin, marketplace and command namespace.** These become `gatedloop`, so commands are `/gatedloop:*`. The `gates` shim keeps its name.
- **Every Specloop-owned identifier is renamed:**

  | Was | Now |
  |---|---|
  | `.specloop/` | `.gatedloop/` |
  | `x-specloop-*` | `x-gatedloop-*` |
  | `specloop/<gate>` statuses | `gatedloop/<gate>` |
  | `specloop/record-merged-*` branches | `gatedloop/record-merged-*` |
  | `specloop.*` rule ids | `gatedloop.*` |
  | `SPECLOOP_HOOK_BEGIN` / `_END` markers | `GATEDLOOP_HOOK_BEGIN` / `_END` |
  | `specloop:` message prefixes | `gatedloop:` |
  | the `specloop` workflow and its docs | `gatedloop` |
- **One release of read-both, loud.** Through 0.7.x, the shim reads both spellings of every renamed identifier, preferring the new one, and warns once per command when it reads an old one. Approval and epic keys use the existing field-by-field fallback. Statuses are published under both contexts, so branch protection doesn't break mid-migration.
- **`gates migrate-name`.** It moves a project across in one go:
  - `git mv .specloop .gatedloop`;
  - rewrites `x-specloop-*` keys in active changes;
  - rewrites composed hook markers.

  It **prints** the edits it won't make: `enabledPlugins`, the permission `ask` rule, and branch-protection contexts. `gates doctor` warns while anything old remains, and `/gatedloop:upgrade` offers the migration through a recurring catalogue item.
- **A forwarder for the old plugin name.** For one release the marketplace also lists a `specloop` plugin. Its only content is a SessionStart notice and a stub for each old command, each naming the install command for `gatedloop`. It never runs the loop, so an adopter can't keep using the old name without seeing the notice.
- **The repository** becomes a fresh public `tessellate-space/gatedloop`. This private repository stays as the archive. Every issue moves and is remapped, and the history is not published (`go-public-migration`). Every link points to the new repository. That includes `AGENT_INSTALL.md`, which still clones the long-gone `radub21/specloop`.
- **Expiry.** A follow-up change, `remove-specloop-forwarders`, is created alongside this one. It removes read-both, the forwarder plugin and the old-name warnings in 0.8.0.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-positioning`: the plugin is named `gatedloop`; the earlier name is read loudly for one release and migrated by command.

## Impact

Almost every shipped file changes:
- `.claude-plugin/` manifests;
- commands, skills and agents;
- hooks;
- `bin/gates`;
- templates, schema and the adoption catalogue;
- the workflow;
- README, SETUP, AUTOMATION, RELEASING, CLAUDE.md, `docs/`, `AGENT_INSTALL.md`;
- the test suite.

Archived changes and past CHANGELOG sections are history, and are not rewritten.
