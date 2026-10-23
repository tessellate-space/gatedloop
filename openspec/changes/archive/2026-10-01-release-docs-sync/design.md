# Design: release-docs-sync

## Decisions

### D1. Two layers: prevent per change, catch at release

A rule applied per change is cheap, and it keeps each change's docs next to its code.
It misses whole-set drift: a README section describing a flow three changes have
since reshaped, or a CLAUDE.md "in-flight" list nobody owns. A release-time pass
catches that, but it's expensive if everything is left to it. Both layers are kept:
the rule prevents, and the release pass reconciles.

### D2. `docs-follow-surface`

```
### docs-follow-surface
Applies to: tasks, code
Rule: A change that adds, removes or alters an adopter-facing surface updates README.md and SETUP.md in the same change (and AUTOMATION.md when it changes enforcement).
```

Its prose defines the surfaces:
- a command, agent or skill;
- a `gates` subcommand or flag;
- a manifest key;
- a gate name;
- an exit code, or a hook's allow/deny behaviour.

Internal refactors, tests and `openspec/` content are excluded. The rule is added to
the `prompts` and `shim` surfaces in `.gates.yaml`, and `gates conventions sync`
regenerates `openspec/config.yaml` so the `tasks` artifact instruction carries it.

### D3. The inventory

`scripts/release docs` builds the inventory from the files themselves, never from a
hand-kept list:

| Kind | Source | Mention form searched |
|---|---|---|
| command | `commands/*.md` stems | `/specloop:<stem>` |
| agent | `agents/*.md` stems | `<stem>` as a word |
| skill | `skills/*/SKILL.md` directory names | `<name>` as a word |
| `gates` subcommand | `./bin/gates --help`'s `{…}` choice list | `gates <sub>` |
| gate name | `schema/gates.schema.json` gate properties | `` `<gate>` `` |
| manifest key | `schema/gates.schema.json` top-level properties | `` `<key>` `` or `<key>:` |

- **Forward check.** Each item must appear in README.md or SETUP.md. Items listed in
  a small `DOCS_EXEMPT` set in the script, each with a one-line reason, are skipped.
  Examples are internal subcommands such as `hook` or `gate-marker`, which only hooks
  call.
- **Reverse check.** In both files, every `/specloop:<x>` and every `gates <x>` that
  names no inventory item is reported as stale, with file and line.

The output is one line per gap, and the script exits 1 on any. It uses stdlib Python
only, like the rest of `scripts/release`.

It doesn't try to judge whether a mention is *accurate*. That needs reading, which
D4 does.

### D4. `/release-docs`

This is `.claude/commands/release-docs.md`, a project-level command in this repo, next
to the OpenSpec-installed `opsx` commands. It never ships. Its steps:

1. Run `scripts/release status --json`, and read each archived change's `proposal.md`
   "What Changes" and the shipped diff since the tag.
2. For each doc, list the sections the changes affect, then edit them:
   - README.md: component table, how-it-works diagram, prerequisites;
   - SETUP.md: contract, keys, procedures;
   - AUTOMATION.md: enforcement;
   - `docs/field-guide.md`;
   - `CLAUDE.md`: commands, architecture, and in-flight work. That last section is
     rewritten from `openspec list`, never hand-kept.
3. Run `scripts/release docs` until it's clean.
4. Branch `docs-<version>`, commit, and open a PR listing the sections changed per
   archived change.

The maintainer reviews and merges. Then `cut`.

### D5. Procedure and reminder

RELEASING.md's procedure block becomes:

```
status → /release-docs (review + merge the PR) → scripts/release docs → cut → publish
```

It also explains why the docs pass sits before `cut`: `cut` refuses on a dirty tree,
and docs are shipped paths.

The `status --hook` line becomes: "Release due: … Run /release-docs, then
`scripts/release cut <level>`."

## Out of scope

- Checking prose accuracy mechanically.
- Adopter projects' docs. This is Specloop's own release tooling.
