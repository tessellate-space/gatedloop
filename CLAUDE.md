# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

gatedloop is a **Claude Code plugin**, not an application. Its deliverable is prompt
assets (commands, skills, agents), hook scripts, and one Python shim. There is no
build step, no package manager and no dependency install. "Editing the product"
means editing markdown prompts, `hooks/*.sh`, or `bin/gates`.

The one exception is `tests/` — a stdlib-only `unittest` suite covering the shim
(`bin/gates`) and the hook scripts, which it drives with real git repositories and
worktrees. It began with `_mini_yaml`, a *conditional* code path (it runs only where
PyYAML is absent), so a defect there is invisible to anyone whose machine has PyYAML
and corrupts silently for everyone whose machine does not. Prompts stay untested;
branching Python does not. Tests set `CLAUDECODE` explicitly rather than inheriting
it, so they behave the same locally and in CI.

## Commands

Everything is exercised by running the shim or the OpenSpec CLI directly.

```bash
python3 -m unittest discover -s tests   # the whole suite, serially (~14 min)
python3 scripts/test-parallel          # the same suite, one process per module (~3 min); what `ci` runs
python3 scripts/test-parallel --affected   # only modules the branch's changes reach; a surface's scoped `ci`
./bin/gates validate               # validate a .gates.yaml (exits 1 with all errors listed)
./bin/gates run ci                 # run a declared gate, exit with its code
./bin/gates surfaces               # which surfaces are hot for the current diff
./bin/gates rules                  # which rule-ids apply to the current diff
./bin/gates init                   # drop templates/gates.yaml.template as .gates.yaml

openspec list --json              # active changes (the session brief + most commands read this)
openspec status --change <name> --json
openspec instructions <artifact> --change <name> --json
```

- **This repo now has its own `.gates.yaml`** and runs its own loop. It had none
  for a real reason — the deliverable is prompts, and prompts have no oracle — which
  changed once `tests/` gave the shim one. Read the manifest's header before trusting
  a green: `ci` covers the branching Python and the plugin manifest only. It says
  nothing about whether a prompt is right, and must not be grown into a proxy for
  prompt review. Convention review remains the only meaningful gate on the `prompts`
  surface.
- In an *installed* plugin, `bin/` is on the Bash tool's PATH, so adopters type
  `gates …`. Inside this repo, use `./bin/gates`.
- To test the plugin end-to-end: `/plugin marketplace add <local path or tessellate-space/gatedloop>`
  then `/plugin install gatedloop`. Hook changes require a new session to take effect.
- **Releasing** — `python3 scripts/release status` shows what shipped since the
  latest `v*` tag; then the **docs pass**: `/release-docs` (a project command in
  `.claude/commands/`, never shipped) reconciles README, SETUP, AUTOMATION, the
  status page and this file with the archived changes and opens a docs PR, which
  is reviewed and merged; `scripts/release docs` checks README/SETUP mention every
  shipped command, agent, skill, `gates` subcommand, gate and manifest key (and
  nothing removed), and `cut` refuses while it reports a gap. `cut
  <patch|minor|major>` bumps all three version fields and drafts a `CHANGELOG.md`
  section; review and edit it, then `publish` commits, tags and creates the
  GitHub release. `check` (run by `ci`) keeps the three
  fields in agreement. Releases are batched and the maintainer decides when;
  adopters get a change only on a version bump. A project-level SessionStart
  hook in `.claude/settings.json` (this repo only, never `hooks/hooks.json`)
  says when one is due. Full procedure: `RELEASING.md`.
- The SessionStart hook can be run standalone: `bash hooks/session-brief.sh` (it
  prints SessionStart `additionalContext` JSON; with no OpenSpec it offers onboarding
  rather than a menu, and it gates every entry on the command being installed).

## Architecture

### Two delegated axes, one owned loop

The whole design follows from refusing to own two kinds of variation:

- **Axis A — what varies by project** (test/build/probe commands, conventions):
  answered by the adopter's `.gates.yaml`.
- **Axis B — what varies by kind of work** (which artifacts, in what order):
  answered by an OpenSpec schema, selected per change in `.openspec.yaml`.

gatedloop owns only the loop between them: `tasks.md` → gated atomic commits →
verify → live self-check → verified on main. OpenSpec is a hard prerequisite, not
a variable.

### The gate contract (the core abstraction)

Shipped prompts never name a real command. They call **abstract gate names**
through the shim and read the exit code:

| Gate | Required | Called at | Blocking |
|---|---|---|---|
| `ci` | **yes** | before every commit | yes |
| `unit` | no | inner red→green loop | — |
| `integration` | no | after implementation tasks | — |
| `verify` | no | change completion | — |
| `live-check` | no (per surface) | change completion | yes |
| `eval` | no | change completion | advisory only |
| `confirm` | no | merge step 5 (merged tree) | yes |

An *undeclared optional* gate is skipped cleanly (exit 0, not a failure); a missing
**required** gate fails loud at `gates validate`. See `schema/gates.schema.json`
for the manifest's authoritative shape and `SETUP.md` for the adopter-facing contract.

### Surfaces and the "hot set"

`surfaces[]` maps globs → `rules` + `live-check`. The changed-file set selects the
hot surfaces, and that one selection drives **two** things: the convention-review
scope (union of hot `rules`) and which live-check probes run. This selection is done
in `bin/gates` — deterministically, in code — precisely so an agent reading YAML
can't silently skip a blocking gate. The *judgement* (convention review) stays an
LLM; the *selection* does not.

### How the components compose

```
/opsx:explore       → thinking only, never implements          ┐ upstream's,
/opsx:propose       → openspec new change + artifacts          │ not ours —
/opsx:apply         → walks a task list, ungated               │ we ship no
/opsx:sync          → push edited specs back                   ┘ copy of these
/gatedloop:tdd-apply → skills/tdd-apply/SKILL.md — the loop itself
      per task: red (gates run unit) → green → gate → atomic commit
      gate = gates run ci green AND convention-review agent clean
      completion: gates run verify → gates run live-check (blocking) → squash-merge
/gatedloop:propose   → /opsx:propose authors; this adds the plan branch, commit and PR
/gatedloop:merge     → gates merge <change>: prove the head, squash, ci, confirm, archive, one push
                      (pull-request mode: publish gatedloop/* statuses and hand the PR to the forge)
/gatedloop:upgrade   → walk the settings a new plugin version asks this project to decide
/gatedloop:archive   → delegates to /opsx:archive, then commits the move
```

- `agents/test-author.md` (Sonnet) writes every task's failing tests for the whole change
  before implementation starts; the tests are held, placed per task and locked, and a
  red run is enforced after placement (`gates tests …`). `agents/merge-runner.md`
  (Sonnet) runs `gates merge` for an orchestrator.
- `agents/tdd-implementer.md` (Sonnet) runs that same skill autonomously. It differs
  in four load-bearing ways: it cannot ask the user (HALTs instead of guessing), it
  is resumable because **done ⟺ committed** (a task's `[x]` flip is committed with
  its code), it always halts with a clean tree at a task boundary, and it **stops
  before the merge**.
- `agents/convention-review.md` (Sonnet, read-only) is deliberately cheap: diff →
  `gates rules` → read only those rules → judge. Under ~10 tool calls; every
  finding cites its rule-id.
- `skills/verify/SKILL.md` is the pre-archive gate: spec `#### Scenario:` →
  acceptance coverage, then `gates run verify`. It reports; it never fixes.
- `hooks/session-brief.sh` + `hooks/_session_brief.py` inject a tailored menu at
  SessionStart; `commands/start.md` is the manual equivalent of the same brief.

### One branch per change

Branch name = change name. Every task commit lands there; squash-merge to `main` at
completion. Never branch per task. OpenSpec git discipline: **propose on `main`**
(from a branch, OpenSpec loses sight of other in-flight changes) and **merge before
archive**.

## Conventions for this repo's own code

This repo's rules live in `docs/conventions.md`, its `conventions.rules-doc` — each
`### <id>` is a stable rule-id that `gates rules` resolves and a review finding cites.
`openspec/config.yaml`'s `rules:` block is generated from it, and `gates validate`
fails on drift. The load-bearing ones:

- **stack-agnostic-prompts** — no project-specific tool name (pytest, npm test,
  keycloak, shadcn, …) may appear in a shipped prompt. All invocation goes through
  `gates run <gate>`. This is the single most important rule in the repo.
- **zero-dep-shim** — `bin/gates` is stdlib-only. PyYAML is used *if importable*,
  otherwise `_mini_yaml` (a minimal parser for the manifest subset) handles it.
  Never add a hard third-party runtime dependency.
- **plugin-relative-paths** — reference bundled files via `${CLAUDE_PLUGIN_ROOT}`,
  never an absolute path or a `../` escape (the plugin dir is copied to a cache on
  install).
- **no-forked-upstream-assets** — ship nothing that reproduces an upstream OpenSpec or
  community-schema asset; authoring references point at `/opsx:*`, and `/gatedloop:*` is
  reserved for what has no upstream equivalent. A command may *delegate* to an upstream
  one to add a guarantee (only `commands/archive.md` does) provided it holds no copy of
  the upstream prompt.
- **commands-flat-skills-nested** — commands are flat `.md` files in `commands/`;
  skills are `skills/<name>/SKILL.md`. The plugin name is already the namespace.
- **fail-loud-gates** — validation and marker/gate checks exit non-zero with an
  explicit message. Never silently skip.
- **self-contained-plugin** — nothing reads from outside the plugin root;
  `plugin.json` stays in `.claude-plugin/`, everything else at root.

### The rejection test (scope arbiter)

Before adding a feature, apply the four questions from
`openspec/changes/archive/2026-08-18-reposition-gatedloop/design.md` D2 (also
`docs/conventions.md` `### rejection-test`):

| Question | Verdict | Belongs instead in |
|---|---|---|
| Does it author an artifact? | not ours | an upstream OpenSpec schema |
| Does it know a stack command? | not ours | a gate in `.gates.yaml` |
| Does it make a stated guarantee enforceable? | **ours** | — |
| Does it get a team running faster? | **ours** | — |

"Not ours" means it belongs upstream or in the adopting project — never that it's a
bad idea.

The four are instances of one question, recorded in the same design: **does it move a
phase from `act` to `close`, or move a team up a rung faster?** Authoring an artifact
is a 0→3 move and OpenSpec's; naming a stack command is a binding and the adopter's.
Use the four questions at review speed and the single one when they disagree.

Ideas that pass the test but aren't scheduled live in `docs/candidates.md`, with the
reason for waiting recorded next to the reason for wanting them.

### Where gatedloop sits

OpenSpec adoption is a ladder, and the useful part is its measuring stick: each SDLC
phase scores 0–4 — `none`, `advise`, `observe`, `act`, `close` — across three levels.
**Rookie** is install and go. **Intermediate** is forking a schema and writing the
constitution in `config.yaml`. **Advanced** is subagents running unattended,
hook-enforced gates, and oracles — and the honest answer to "how do I get a gate?" is
that the gate only exists because a team builds one.

**gatedloop is that advanced rung, prefabricated.** Two owned jobs follow: **climb**
(onboarding, `gates-init`, workflow packs, pack inspection) and **close** (the loop,
the subagents, the enforcement). Three terms come with it and are used deliberately —
a **gate** is the required checkpoint, an **oracle** is the machine-readable verdict
it reads back (which is why the contract is an exit code and nothing else), and a
**hook** is what makes the gate non-optional.

## In-flight work

`openspec list --json` is the source; this list is a snapshot from 0.7.0. Read a change's
`design.md` before touching the area it covers:

- `git-layer-enforcement`, `token-ledger`: approved plans from the competitive survey (specloop PR 142),
  implemented after the public move.
- `role-commands`: `/gatedloop:planner` and `/gatedloop:orchestrator`, prompt commands over shipped
  primitives.
- `remove-specloop-forwarders`: the 0.8.0 expiry of the earlier name's read-both and forwarder.

Ideas that pass the rejection test but aren't scheduled live in `docs/candidates.md`.

The five upstream community schemas live at
<https://github.com/intent-driven-dev/openspec-schemas>; `spec-driven` is bundled
with the CLI, which is why `openspec schemas` lists only one in a fresh project.

The reasoning behind the boundary is in the archived `reposition-specloop` design.
