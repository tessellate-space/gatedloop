# Proposal: release-docs-sync

## Why

Adopters learn Specloop from README.md, SETUP.md and AUTOMATION.md. Those files drift,
because keeping them current is nobody's step:

- Most change plans carry a docs task, but only for the surface that change touches.
  Nothing checks that the whole set still describes the whole plugin.
- The release procedure (`RELEASING.md`) goes status → cut → publish. No step asks
  whether the docs match what is about to ship.
- `CLAUDE.md`, the guide every session in this repo reads, is already stale. Its
  "In-flight work" section still lists five changes that were archived long ago.

0.5.0 ships about ten changes at once, and the maintainer asked for a docs step before
release.

## What Changes

- **Per change: a convention rule, `docs-follow-surface`,** in this repo's
  `docs/conventions.md`. A change that adds, removes or alters something an adopter
  uses must update README.md and SETUP.md in the same change, and AUTOMATION.md when it
  changes enforcement. That covers a command, agent, skill, `gates` subcommand,
  manifest key, gate, exit code or hook behaviour. The rule has two tags:
  - `Applies to: tasks, code`, so `gates conventions sync` adds it to the rules
    OpenSpec shows when authoring `tasks.md`, and plans get a docs task by default;
  - `code`, so convention review checks it on this repo's `prompts` and `shim`
    surfaces.
- **At release, deterministically: `scripts/release docs`.** An inventory check
  compares what ships with what the docs mention:
  - every `/specloop:<command>`, agent, skill, `gates` subcommand, gate name and
    top-level manifest key must be mentioned in README.md or SETUP.md;
  - every such name the docs mention must still exist, so removed commands and
    renamed keys are caught.

  It lists each gap with a file and line. `cut` runs it first and refuses while it
  finds gaps.
- **At release, with judgement: a repo-local `/release-docs` command** in
  `.claude/commands/`, which is this repo's own tooling and never shipped. It:
  - reads the archived changes and shipped diff since the last tag;
  - updates README.md, SETUP.md, AUTOMATION.md, `docs/field-guide.md` and
    `CLAUDE.md` to match;
  - opens a docs PR for the maintainer to review.

  The procedure becomes: status → `/release-docs` (PR reviewed and merged) →
  `docs` → cut → publish.
- **The reminder says so.** The SessionStart "Release due" line names the docs pass
  as the next step.

## Capabilities

### Modified Capabilities

- `plugin-release`: the docs inventory check gates `cut`, and the documented procedure
  includes a docs pass.

## Impact

- `docs/conventions.md` gains the rule. `.gates.yaml` gains it on the `prompts` and
  `shim` surfaces. `openspec/config.yaml` is regenerated with `gates conventions
  sync`.
- `scripts/release`: `docs` subcommand, `cut` calls it, and the `status --hook` text
  changes.
- New `.claude/commands/release-docs.md`.
- RELEASING.md and CLAUDE.md's release paragraph.
- `tests/test_release.py`: the inventory, both directions.
- Nothing shipped to adopters changes, since this is maintainer tooling. It is used
  first for 0.5.0.
