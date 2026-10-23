# Design: release-procedure

## Context

See proposal.md — Why. Current state:

- **The version lives in three fields**: `plugin.json` `version`, and in
  `marketplace.json` both `metadata.version` and `plugins[0].version`. Past releases
  (`7abcdb5` for 0.2.0, `9fe73de` for 0.3.0, `2898ba5` for 0.4.0) edited them by hand.
- **Tags**: only `v0.4.0` exists (annotated), created by hand on 2026-09-29. It is the
  anchor for everything this change computes.
- **CI**: GitHub runs only a mirror-to-ADO workflow on push. Branch protection is
  unavailable on this private free-tier repo (API 403), so no required check can gate
  a merge. The `ci` gate in `.gates.yaml` runs locally before every loop commit.
- **Merges** happen in the GitHub UI by the maintainer, as squash commits whose subjects
  read like release notes ("Workflow packs: schema dispatch, …").
- **Archives** land on `main` as `archive change: <name>` commits that add
  `openspec/changes/archive/YYYY-MM-DD-<name>/` and may create or modify
  `openspec/specs/<capability>/spec.md`.
- **`.claude/`** in this repo holds generated OpenSpec skills and commands and a
  personal `settings.local.json`. There is no shared `.claude/settings.json`.
- Constraints: `zero-dep-shim` in spirit (stdlib only), `fail-loud-gates`, and the
  standing rule that the maintainer reviews before anything is published.

## Goals / Non-Goals

**Goals:**

- One command sequence cuts a release. It never half-publishes.
- The release notes are generated from data the repo already has, and a human edits
  them before they are published.
- Forgetting to release becomes visible at the start of every session in this repo.
- Mismatched version fields cannot pass `ci`.

**Non-Goals:**

- Automatic publishing on merge or archive (rejected in D2).
- A GitHub Actions release pipeline. Publishing needs the maintainer's review anyway,
  and Actions cannot gate merges here.
- Any adopter-facing command, hook or prompt.
- Fixing the stale `homepage`/`repository` URLs in the manifests, which still point at
  the pre-move owner. That is noted as a follow-up; it is metadata, not procedure.

## Decisions

### D1: A maintainer script in `scripts/`, not a shim subcommand or a command

`scripts/release` is an executable stdlib Python file with the subcommands `status`,
`cut`, `publish` and `check`.

- It does not belong in `bin/gates`. `bin/` is on every adopter's PATH, and `gates
  release` would offer adopters a command that releases *Specloop*.
- It does not belong in `commands/`. Every file there ships as `/specloop:<name>`.
- `scripts/` is copied into the plugin cache like every other directory, but nothing
  loads or advertises it. It is inert there, like `tests/`.

**Alternative — a Makefile or justfile:** rejected, because it adds a tool dependency
to a repo whose rule is stdlib only. **Alternative — a GitHub Action:** rejected as the
primary path (D2). A thin Action that runs `check` is a possible follow-up.

### D2: Batched and human-triggered, not per-PR or per-archive

This was the maintainer's decision on 2026-09-29, among three options.

- **Per-PR bumps** collide. Two parallel lanes both bump 0.4.0 to 0.5.0, the same
  failure #20 records for ADR numbers.
- **Release-on-archive** removes collisions, but it takes away the ability to batch
  small fixes. It would also turn the archive command, which is upstream-delegating by
  design (`no-forked-upstream-assets`), into something that publishes.
- **Batched releases** keep the decision human and the diff reviewable. The cost is
  that the maintainer can forget, and D5 makes forgetting visible instead of relying on
  memory.

### D3: What counts as shipped, and how the level is suggested

Shipped paths are one constant in the script: `.claude-plugin/`, `commands/`,
`skills/`, `agents/`, `hooks/`, `bin/`, `templates/`, `schema/`, `README.md`,
`SETUP.md` and `AUTOMATION.md`. These are the paths whose content changes what an
adopter's installed plugin does or tells them. `openspec/`, `docs/`, `tests/`,
`scripts/` and `.specloop/` are excluded. `docs/` is excluded because nothing in the
plugin reads it at runtime.

Two commands supply the evidence:

- `git log <tag>..HEAD -- <shipped paths>` lists the commits.
- `git diff --name-status <tag>..HEAD -- openspec/changes/archive/` lists the added
  archive directories.

The suggested level comes from the spec deltas of the archived changes, read from
their archived `specs/**/spec.md`. Any `## ADDED Requirements` section, or a delta for
a capability absent at the tag, suggests `minor`. Otherwise `patch`. The script never
suggests `major`.

This follows semver as it is usually read before 1.0: new behaviour is a minor bump,
fixes are a patch. The suggestion is advisory, and `cut` takes the level as an
argument, so the maintainer can override it.

**Alternative — derive the level from conventional-commit prefixes:** rejected. This
repo's squash subjects are prose, and adopting a prefix convention only for this
purpose would be a new rule to enforce.

### D4: Two steps — `cut` writes, a human reviews, `publish` ships

`cut <level>` computes the next version and rewrites the three fields. It edits the
JSON as text, replacing the exact `"version": "X.Y.Z"` occurrences and asserting that
exactly three were replaced, so key order and formatting survive. It then renders the
changelog section and stops.

The changelog section has two parts:

1. One bullet per archived change: `**<name>**`, then the first sentence of its
   archived `proposal.md` `## Why`. The sentence is cut at the first `. ` or at 200
   characters, whichever comes first.
2. "Other changes": shipped-path commit subjects that do not start with a bookkeeping
   prefix and are not already the squash commit of a listed change.

The output is a draft. The maintainer is expected to edit it before `publish`, which
is the point of the pause.

`publish` checks every precondition first:

- the only changed paths are the three fields and `CHANGELOG.md`;
- `check` passes;
- the tag `vX.Y.Z` exists neither locally nor on the remote;
- `gh auth status` succeeds;
- the current branch is `main` and matches `origin/main`.

Then it runs the writes in a fixed order: commit, annotated tag, push the commit,
push the tag, create the GitHub release with notes read from the file. On a failure
after the commit, it prints which steps are done and the exact command to finish. The
tag is created locally only after the commit, and it is pushed only after the commit
push succeeds, so there is never a tag without its commit.

**Alternative — a single `release <level>` that does everything:** rejected, because
it would publish notes nobody read. The maintainer reviews every PR before merge; a
release deserves the same.

### D5: The reminder is a project-level SessionStart hook, invisible to adopters

A new shared `.claude/settings.json` in this repo:

```json
{"hooks": {"SessionStart": [{"matcher": "startup|resume",
  "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/release\" status --hook", "timeout": 10}]}]}}
```

`status --hook` prints SessionStart `additionalContext` JSON with one line, for
example: *"Release due: 2 archived changes and 9 shipped commits since v0.4.0,
suggested minor. Run `scripts/release cut minor`."* When the release is current, or
anything fails, it prints nothing and exits 0. A reminder must never block a session.

This works because Claude Code reads `.claude/settings.json` as project settings for
sessions whose project is this repo. An installed plugin's `.claude/` directory is not
loaded as settings; plugin hooks come only from `hooks/hooks.json`. The spec pins that
boundary with a scenario.

**Alternative — put it in the plugin's session brief:** rejected. Every adopter would
run Specloop's release check. **Alternative — make `status` fail `ci`:** rejected.
Every loop commit on `main` would go red whenever a release is due, which punishes the
wrong actor at the wrong time.

### D6: `check` in `ci`, backfilled changelog

`.gates.yaml`'s `ci` becomes `python3 -m unittest discover -s tests -q && python3
scripts/release check && claude plugin validate .`. `check` is cheapest after the unit
tests, and it fails loudly when a hand edit missed a field.

`CHANGELOG.md` is seeded with 0.4.0, 0.3.0 and 0.2.0, taken from the bodies of their
release commits. Only 0.4.0 is tagged. The procedure does not backfill tags for 0.2.0
and 0.3.0, because tagging history now would invent dates the repo never recorded.

## Risks / Trade-offs

- [The maintainer ignores the reminder] → It shows at every session start with a
  concrete count and command. Beyond that, releasing is a human decision by design
  (D2).
- [The suggested level is wrong] → It is only a suggestion; `cut` takes the level
  explicitly.
- [The first-sentence extraction reads a proposal badly] → The draft is edited before
  `publish`. That is the reason for the pause.
- [`.claude/settings.json` is shared, so every contributor gets the hook] → That is
  intended. It only reads git state and prints one line.
- [A tag push succeeds but release creation fails] → `publish` prints the `gh release
  create` command to finish. The tag and commit are consistent either way.

## Migration Plan

Land the change, then run `scripts/release status` on `main` once. It should report
exactly what has shipped since `v0.4.0`. The first scripted release is whichever comes
next. Rollback means deleting `scripts/release`, the settings file and the `ci` clause.
The changelog and tags stay valid.
