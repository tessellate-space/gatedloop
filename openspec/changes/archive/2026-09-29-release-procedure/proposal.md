# Proposal: release-procedure

## Why

Claude Code uses a plugin's `version` field to decide whether an installed copy has
changed. A change merged to `main` without a version bump does not reach adopters.
Releases are hand-made today, with no procedure behind them. 0.2.0, 0.3.0 and 0.4.0
were each an ad hoc commit editing three version fields across two manifests, and
nothing reminds anyone to cut one. Before 0.4.0, two merged changes sat on `main`
unreleased (the `_normalize_tree` fix for #21, and workflow-packs), so the field-trial
adopters who reported #21 were still running the broken marker key.

There is also no record of what a release contains. There is no changelog, no GitHub
release, and until 0.4.0 no tag. Only 0.4.0 is tagged, and that tag was added by hand.

## What Changes

- **One maintainer script, `scripts/release`**, stdlib Python. It is not in `bin/`,
  which is on every adopter's PATH, and not a command, which would ship as
  `/specloop:release`. It has four subcommands:
  - `status` lists what is unreleased since the latest `v*` tag and suggests a bump
    level.
  - `cut <patch|minor|major>` bumps all three version fields together and writes a new
    top section to `CHANGELOG.md`. Then it stops, so a human reviews the diff.
  - `publish` commits the reviewed release, creates an annotated tag, pushes both, and
    creates the GitHub release with the changelog section as notes. It checks every
    precondition before its first write, so a missing `gh` or a dirty tree leaves
    nothing half-done.
  - `check` verifies that the three version fields agree and that the version is not
    behind the latest tag.
- **Releases are batched and human-triggered.** The maintainer decides when to cut.
  This avoids version collisions between parallel lanes, and each release still goes
  through a reviewed diff.
- **Unreleased work is made visible.** A SessionStart hook in this repo's own
  `.claude/settings.json` runs `scripts/release status` and injects one line when
  shipped files changed since the last tag. That file is project-level settings for
  sessions in this repo only. Claude Code does not load it from an installed plugin, so
  adopters never see the nag.
- **`check` joins this repo's `ci` gate.** Mismatched version fields become a red gate.
- **`CHANGELOG.md` is seeded** with 0.2.0–0.4.0 from their existing release commit
  messages.
- **CLAUDE.md and a short `RELEASING.md`** document the procedure, the bump rule and
  the shipped-path set.

## Capabilities

### New Capabilities

- `plugin-release`: how this repository versions and publishes the plugin. It covers
  the single-source version rule, the unreleased-change report and suggested level,
  the two-step cut/publish, the changelog, the tag and GitHub release, the repo-local
  reminder, and the consistency check.

### Modified Capabilities

_None._ No adopter-facing behaviour changes.

## Impact

- New: `scripts/release`, `CHANGELOG.md`, `RELEASING.md`, `.claude/settings.json`,
  `tests/test_release.py`.
- Edited: `.gates.yaml` (`ci` gains `python3 scripts/release check`), `CLAUDE.md`
  (Commands and a "Releasing" note).
- Adopters: nothing to do. They get releases more often, and each release has notes.
- Rejection test: this is not an adopter feature. It is how this repository ships
  itself, the same category as `tests/`. It follows the repo's own conventions:
  `zero-dep-shim` (stdlib only), `fail-loud-gates` (every refusal exits non-zero with
  the reason), and `self-contained-plugin` (nothing outside the repo root).
