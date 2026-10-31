# Releasing gatedloop

This is how this repository ships the plugin. It is maintainer tooling, not a
plugin feature: `scripts/release` is not on an adopter's PATH and is not a
`/gatedloop:*` command.

## Why a release matters

Claude Code updates an installed plugin only when its `version` changes. A
change merged to `main` without a version bump does not reach adopters. They
get it in the first release after the merge, and at no other time.

## When to release

Releases are batched and the maintainer decides when to cut one. Nothing
publishes on merge or on archive. Two parallel lanes that each bumped the
version would collide, and batching lets small fixes ship together.

To make a forgotten release visible, `.claude/settings.json` runs
`scripts/release status --hook` at the start of every session in this repo. When
shipped work is unreleased, the session opens with one line such as:

> Release due: 2 archived changes and 9 shipped commits since v0.4.0, suggested
> minor. Run /release-docs, then `scripts/release cut minor`.

When the release is current, or the script fails, the hook prints nothing and
never blocks the session. The hook is in this repo's project settings, not the
plugin's `hooks/hooks.json`, so adopters never see it.

## The procedure

```
status → /release-docs (review + merge the PR) → scripts/release docs → cut → publish
```

Run these from the repository root, on an up-to-date `main`.

```bash
python3 scripts/release status          # what shipped since the latest v* tag; exit 1 when a release is due
/release-docs                           # in Claude Code: reconcile the docs, open a docs PR; review and merge it
git pull                                # back on main, with the docs PR merged
python3 scripts/release docs            # the docs mention everything that ships; exit 1 on any gap
                                        # check: an adoption item for every new decision (see "Adoption items")
python3 scripts/release cut minor       # bump all three version fields and draft the CHANGELOG.md section
git diff                                # review; edit the draft section into release notes
python3 scripts/release publish         # commit, push, tag, push the tag, create the GitHub release
```

The docs pass sits before `cut` for two reasons. `cut` refuses on a dirty tree,
and README.md, SETUP.md and AUTOMATION.md are shipped paths, so docs edits must
already be merged when the release is cut. And the docs are part of what ships:
an adopter who updates reads them, so they must describe the release they got.

`python3 scripts/release check` verifies that the three version fields agree, are
`MAJOR.MINOR.PATCH`, and are not behind the latest `v*` tag. This repo's `ci`
gate runs it, so a hand edit that misses a field goes red.

### `status`

`status` compares `HEAD` with the highest `vX.Y.Z` tag reachable from it. It
reports:

- **shipped commits**: commits since the tag that touch a shipped path;
- **archived changes**: directories added under `openspec/changes/archive/`
  since the tag.

A release is due when at least one shipped commit exists. An archived change
with no shipped commit, such as a planning-only or decision-only change, does
not make a release due. `--json` prints the same report as one document.

### The docs pass: `/release-docs`

`/release-docs` is a project command in `.claude/commands/release-docs.md`. It is
this repo's tooling and never ships. It reads `status --json`, each archived
change's proposal and the shipped diff since the tag, then updates the sections
those changes affect in README.md, SETUP.md, AUTOMATION.md, `docs/status.md`
and `CLAUDE.md`. `CLAUDE.md`'s "In-flight work" is rewritten from `openspec
list`, never kept by hand. It runs `scripts/release docs` until that is clean,
then opens a PR on a `docs-<version>` branch that lists the sections changed per
archived change. It stops there: the maintainer reviews and merges.

### `docs`

`docs` is the mechanical half of the pass. It builds an inventory from the
plugin's own files and checks README.md and SETUP.md against it in both
directions:

| Kind | Source | Counts as mentioned |
|---|---|---|
| command | `commands/*.md` | `/gatedloop:<name>` |
| agent | `agents/*.md` | the name as a word |
| skill | `skills/*/SKILL.md` | the name as a word |
| `gates` subcommand | `bin/gates --help` | `gates <name>` |
| gate | `schema/gates.schema.json`, `gates` properties | `` `<gate>` `` |
| manifest key | `schema/gates.schema.json`, top-level properties | `` `<key>` `` or `<key>:` |

- **Forward**: every item is mentioned somewhere in README.md or SETUP.md.
- **Reverse**: every `/gatedloop:<name>` in either file names a command or skill,
  and every `gates <name>` in their code (fenced blocks and inline code) names a
  subcommand the shim has. Prose such as "the gates are" is not a reference.

It prints one line per gap, with a file and line, and exits 1 on any. The
`DOCS_EXEMPT` set in `scripts/release` lists the few names the check skips, each
with its reason: an internal subcommand only hooks call, or a retired name kept
in a migration table. It does not judge whether a mention is accurate; that is
what the reviewed PR is for.

### Shipped paths

These are the paths whose content changes what an installed plugin does or
tells an adopter. They are the `SHIPPED_PATHS` constant in `scripts/release`:

`.claude-plugin/`, `commands/`, `skills/`, `agents/`, `hooks/`, `bin/`,
`rules/`, `templates/`, `schema/`, `adoption/`, `README.md`, `SETUP.md`,
`AUTOMATION.md`.

`openspec/`, `docs/`, `tests/`, `scripts/` and `.gatedloop/` are excluded.
Nothing in the plugin reads them at runtime.

### The level rule

`status` suggests a level. The suggestion is advisory, and `cut` takes the level
you give it.

- **minor**: an archived change adds a requirement (its archived
  `specs/**/spec.md` has an `## ADDED Requirements` section), or it creates a
  capability that `openspec/specs/` did not have at the tag.
- **patch**: shipped paths changed and no archived change qualifies for minor.
- **major**: never suggested. A major release is always an explicit choice.

### `cut <patch|minor|major>`

`cut` runs the `docs` check first and refuses while it reports a gap. It then
refuses on a dirty tree, off `main`, when nothing is due, or when `CHANGELOG.md`
already has a section for the next version. Every refusal happens before any
file is written.

When no refusal applies, `cut` rewrites the three `"version"` values as text,
which keeps key order and formatting. It asserts that exactly three values were
replaced. It then inserts a `## X.Y.Z — YYYY-MM-DD` section at the top of
`CHANGELOG.md`, which lists:

1. each archived change as `**<name>**` and the first sentence of its
   proposal's `## Why`;
2. under "Other changes", the remaining shipped commit subjects. Bookkeeping
   subjects (`propose:`, `attest approval:`, `archive change:`, `candidates:`,
   `Release`) are left out, and so is the squash commit of a change already
   listed.

When `schema/gates.schema.json` changed since the tag and no item in
`adoption/catalog.json` has the new version as its `since`, `cut` prints a
warning naming both files and still completes; see "Adoption items" below.

`cut` commits nothing. The section is a draft, and you should edit it before
`publish`, which is the reason for the pause.

### Adoption items

An adopter gets the code of a release, but nothing tells them what it asks them to
*decide*. `adoption/catalog.json` is that list: `gates adoption status` and
`/gatedloop:upgrade` read it in every adopter's project.

- **Add an adoption item for every new decision**: a new manifest key, a new
  rules-doc target, or any setting whose default an adopter should choose
  deliberately. Add it in the change that introduces the setting, with `since`
  set to the next release's version.
- **A change to the git hook template needs no new item.** `git-hook-refresh` is
  recurring (`"recurs": true`): its detector compares an adopter's installed copy
  with the shipped template on every run, so any template change offers the
  refresh again, whatever was recorded for an earlier release.
- `approval-keys` (0.5.1) is recurring too. It offers `gates approval migrate`
  while an active change carries approval keys in the 0.5.0 spelling, which
  `openspec validate --strict` fails on from OpenSpec 1.14. Name it in the
  release's upgrade notes.
- Before `cut`, check that every item for this release carries the version you
  are about to cut. If you cut a different number than the items assumed, correct
  their `since` in the draft.
- `cut` warns when the schema changed and no item carries the new version. It is
  a warning, because a schema change can be a fix rather than a decision.
- `publish` refuses while any item carries a version later than the one being
  published.

### `publish`

`publish` checks every precondition before its first write and lists every one
that fails:

- the branch is `main` and `HEAD` matches `origin/main`;
- nothing differs from `HEAD` except the two manifests and `CHANGELOG.md`;
- `check` passes, and `CHANGELOG.md` has a section for the version;
- no item in `adoption/catalog.json` has a `since` later than the version being
  published (an item is added with the change that introduces its setting, so it
  carries the next version until `cut`; one tagged for a later release is named);
- the tag `vX.Y.Z` exists neither locally nor on `origin`;
- `gh auth status` succeeds.

It then runs these steps in a fixed order:

1. commit `Release X.Y.Z`;
2. push the commit;
3. create the annotated tag `vX.Y.Z`;
4. push the tag;
5. `gh release create vX.Y.Z --title "gatedloop X.Y.Z"`, with the version's
   changelog section as its notes.

The tag is created only after the commit is on the remote, so a tag never
exists without its pushed commit.

## Breaking changes

What adopters may rely on is written down in [`docs/stability.md`](./docs/stability.md)
and recorded in `tests/contract.json`, which ci compares with the code. Retiring a
covered surface takes three steps:

1. Deprecate it with a warning on use, naming the replacement.
2. Keep it for at least one further release.
3. Remove it, regenerate the snapshot (`python3 tests/test_contract.py --write`), and
   ship the removal under `### Breaking` with a migration step.

`status` lists each public entry removed from the snapshot since the latest tag, and a
raised ledger row version, under breaking (in text and in `--json`). It still suggests
only `minor` or `patch`: while the version is 0.x a removal may ship in a minor, and
from 1.0 only in a major, so the level stays your call. `cut` drafts one
`- <entry>: TODO` line per removal under `### Breaking`; replace each `TODO` with the
migration step. `publish` refuses, before its first write, while a `TODO` remains in
that subsection. A tag that predates the snapshot skips the comparison, and `status`
says so.

## Publishing the public repository

gatedloop is published as a fresh public repository, `tessellate-space/gatedloop`, and this private one, `tessellate-space/specloop`, stays as the archive (`go-public-migration`). Renaming would expose the full history: most commits carry the maintainer's personal email, and every closed PR's `refs/pull/*` keeps the old commits reachable. `scripts/go-public` does the move. Like `scripts/release`, it is repo-local and never shipped. Every subcommand takes `--dry-run`, which prints each outward action (`gh issue transfer`, `gh api -X PATCH`, the git steps of `push`) instead of running it.

The steps run in this order. The transfer comes before the tree, because the tree's remapping needs the real new numbers.

1. Merge the changes that must ship from this repository first (`rename-to-gatedloop`, `public-status`, `role-commands`), and cut 0.7.0 here. `push` never edits a version.
2. Create the empty public repository.
3. `scripts/go-public plan` lists every issue (open and closed) and every PR. It writes `map.json`, the predicted old-to-new map for an oldest-first transfer, and prints what each later step would do. Review it. `plan` moves nothing, and it refuses to overwrite a map whose transfer has started.
4. `scripts/go-public transfer` moves every issue, oldest first, and records each real new number in `map.json` as it goes. A real number overrides the prediction. It then remaps the references in every moved issue's body and comments, which needs admin rights on the public repository, because some comments are by other people. Each edited comment is printed with its author. A failed run is resumed by running it again: it skips the issues and edits the map records as done.
5. `scripts/go-public tree <dir>` exports `HEAD` into `<dir>` with no history. It replaces the personal email with the GitHub noreply address in every text file, and remaps references. It then runs `python3 -m unittest discover -s tests` in the export, and writes `<dir>.report.txt` beside it. The report lists every rewrite and every email replacement (`file:line old -> new`), every unknown `#NN` (left alone), and every binary file (skipped). It refuses until the transfer has recorded every real number. `--keep-refs <glob>` leaves the references in matching files as they are, for a file whose `#NN` is data, such as a test's expected string.
6. `scripts/go-public push <dir>` refuses unless design D5 holds: the report is complete and recorded passing tests for exactly this tree, the personal email appears nowhere, the public repository is empty, and `plugin.json` reads `--expect-version` (default 0.7.0). It then commits the tree once as the noreply identity, which it also sets in the new clone's git config, pushes `main`, and pushes the annotated tag `v<version>`. It creates no GitHub release; run `gh release create v0.7.0 --repo tessellate-space/gatedloop` with the 0.7.0 notes afterwards.
7. Add one line to this repository's README that points at the public repository.

How references are remapped (design D3), outside fenced code blocks and inline code spans:

| In the archive | In the public repository |
|---|---|
| `#NN` or `tessellate-space/specloop#NN`, an issue | `#<new>` |
| `#NN`, a PR | `specloop PR NN` |
| `github.com/tessellate-space/specloop/issues/NN`, an issue | `github.com/tessellate-space/gatedloop/issues/<new>` |
| a `/pull/NN` link, or `tessellate-space/specloop#NN` naming a PR | unchanged: it points at the archive |
| `#NN` that is neither | unchanged, and listed as unknown in the report |

Before `tree`, the README must say that issue numbers before 0.7.0 were remapped from the private archive, and that PR references name it. The export carries the README as it stands.

## Releasing through the rename

The 0.7.x and 0.8.x releases carried the rename from Specloop (`rename-to-gatedloop`), and three things about them differed from an ordinary release.

- **A fourth version field, through 0.8.x.** `.claude-plugin/marketplace.json` listed a second plugin, the `specloop` forwarder at `forwarder/specloop/`, and its entry's `version` moved with the plugin's. `scripts/release check` read it as a fourth field, and `cut` bumped it with the other three. From 0.9.0 the entry is gone, and `check` and `cut` read the three fields again.
- **Where the forwarder shipped from.** An existing install updates from the repository its marketplace was added from, `tessellate-space/specloop`. So the release that first carried the forwarder had to reach that repository's `main` before `go-public-migration` made it a private archive.
- **The expiry.** `remove-specloop-forwarders` removes the forwarder, the read-both readers, the dual status posting and the earlier-name warnings in 0.9.0 (`defer-earlier-name-expiry` moved it from 0.8.0, so the #56 fix could ship in 0.8.0). `gates migrate-name` stays one release longer. Cut 0.9.0 only with that change archived, and have its release notes repeat that branch protection requiring `specloop/ci` must require `gatedloop/ci` instead: from 0.9.0 only `gatedloop/<gate>` is posted.

## A partial publish

If a step fails after the commit, `publish` exits non-zero and names the
completed steps. It says whether the release commit exists locally or on the
remote, and whether a tag was created or pushed. It then prints one command,
under "Finish with:", that runs the remaining steps. Fix the cause (network,
authentication, a rejected push) and run that command. Do not re-run `publish`:
its preconditions no longer hold once the release commit exists.

The notes file named in that command is kept in the system temp directory for
this purpose. If it is gone, recreate it from the version's section of
`CHANGELOG.md`.
