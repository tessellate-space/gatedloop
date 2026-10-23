---
name: "Release: docs pass"
description: Reconcile README, SETUP, AUTOMATION, the status page and CLAUDE.md with what shipped since the last tag, and open a docs PR (this repo's release tooling; never shipped)
category: Release
tags: [release, docs, maintainer]
---

The docs pass of gatedloop's release procedure (RELEASING.md): status → **/release-docs**
(review + merge the PR) → `scripts/release docs` → cut → publish.

This is maintainer tooling for this repository. It lives in `.claude/commands/`, not
`commands/`, so it never ships as a `/gatedloop:*` command. It reconciles the docs with
what is about to ship; it does not cut or publish anything.

**Input**: optionally the version about to be cut (e.g. `0.5.0`). Without one, use
`scripts/release status`'s suggested level applied to the current version.

## Why it runs before `cut`

`cut` refuses on a dirty tree, and README.md, SETUP.md and AUTOMATION.md are shipped
paths, so docs edits have to be merged before the release is cut. `cut` also runs
`scripts/release docs` first and refuses while it reports a gap.

## Steps

1. **Read what shipped.** Run from the repository root, on an up-to-date `main`:

   ```bash
   python3 scripts/release status --json
   ```

   Exit 1 means a release is due; exit 0 means nothing shipped, so stop and say so. From
   the document, take `tag`, `archived_changes` and `shipped_commits`. For each archived
   change, read its `openspec/changes/archive/<dir>/proposal.md` "What Changes" section.
   Then read the shipped diff since the tag:

   ```bash
   git diff --stat <tag>..HEAD -- .claude-plugin commands skills agents hooks bin templates schema README.md SETUP.md AUTOMATION.md
   ```

   and open the diff of each path the stat shows, for the surfaces the proposals name.

2. **Plan, per doc, before editing.** For each doc below, list the sections the
   archived changes affect and why, one line each. A doc nothing affects is left alone.

   - `README.md`: the component tables, the how-it-works diagram, prerequisites.
   - `SETUP.md`: the gate contract, manifest keys, the `gates` command reference,
     procedures.
   - `AUTOMATION.md`: enforcement — hooks, markers, what is denied and when.
   - `docs/status.md`: the sharp edges and their labels, what has been exercised, the upstream coupling and the tested OpenSpec version.
   - `CLAUDE.md`: the commands block, the architecture section, and "In-flight work".
     Rewrite "In-flight work" from `openspec list --json`; never keep it by hand. A
     change no longer listed is archived and leaves the section.

3. **Edit** those sections to match what ships. Describe the plugin as it is after the
   release, not the history of how it got there; a rename keeps its migration-table
   row. Do not touch a doc section that no archived change affects.

4. **Run the inventory check until it is clean:**

   ```bash
   python3 scripts/release docs
   ```

   Each line is one gap with its file and line. An undocumented item gets a mention in
   README.md or SETUP.md. A stale mention is removed or corrected. An item no adopter
   types (a subcommand only hooks call, a retired name kept in a migration table) goes
   in `DOCS_EXEMPT` in `scripts/release` with a one-line reason instead — say so in the
   PR.

5. **Open the docs PR.** Branch `docs-<version>` from `main`, commit the edits, push, and
   open a PR whose body lists, per archived change, the doc sections it changed (and
   the changes that needed none). Hand the maintainer the link and stop. Do not merge
   it, and do not run `cut`: the maintainer reviews and merges, then runs
   `scripts/release docs` and `scripts/release cut <level>`.
