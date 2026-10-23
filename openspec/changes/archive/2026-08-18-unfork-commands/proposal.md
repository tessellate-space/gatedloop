## Why

Specloop ships three commands — `commands/explore.md`, `commands/propose.md`, `commands/archive.md` — that are **copies of OpenSpec's own Claude Code commands with the name swapped**.

Running `openspec init --tools claude` in a clean repo installs:

```
.claude/commands/opsx/{apply,archive,explore,propose,sync}.md
.claude/skills/openspec-{apply,archive,explore,propose,sync}-*/SKILL.md
```

Our `explore.md` is 174 lines against upstream's 175. The diff is the frontmatter title, `/opsx:` → `/specloop:`, and one ASCII-art box indented three spaces differently.

This is not merely duplication — **the fork has already rotted**. Measured against current upstream, our copies have dropped:

| Lost in the fork | Consequence |
|---|---|
| `--store` support (all three commands) | stores are invisible to Specloop users — and the store is one of the two answers to multi-repo adoption, so the fork removed the flag the multi-repo story depends on |
| `planningHome`, `changeRoot`, `artifactPaths`, `actionContext` | our copies hard-code `openspec/changes/<name>/`, with upstream's own warning *"Use these instead of assuming repo-local paths"* deleted |
| `allowed-tools: Bash(openspec:*)` | broader tool surface than upstream intends |
| `/opsx:sync` entirely | no Specloop equivalent exists |

Every future upstream improvement to artifact authoring lands in files we shadow. The `namespaced-refs` convention rule calls `/opsx:` "the legacy prefix" — it is not legacy, it is the **current upstream namespace**, and that rule is a marker we wrote to justify the fork.

The rejection test recorded in `reposition-specloop` already decides this: *does it author an artifact? → not ours.* `explore`, `propose` and `archive` author artifacts. Repositioning the plugin in prose while `commands/` contradicts the boundary in code would describe a boundary rather than draw one.

## What Changes

- **Delete the two forked authoring commands.** Remove `commands/explore.md` and `commands/propose.md`. Adopters use `/opsx:explore` and `/opsx:propose`, installed and maintained by OpenSpec.
- **Reduce `commands/archive.md` to a delegation.** The fork carries one behaviour upstream does not have — it commits the archive move, and stops loudly if that commit fails. That is a guarantee, so it stays; the other ~150 lines are a copy of upstream's prompt, so they go. What remains runs `/opsx:archive` and commits. See design D7 for why this one command is wrapped rather than deleted, and what bounds the cost.
- **Keep the three commands that are genuinely ours.** `harness-init` (onboarding), `start` (session brief), and the `tdd-apply` skill — none has an upstream equivalent. `/opsx:apply` is a different thing: it applies a task list; `tdd-apply` runs a gated red→green→commit loop with enforcement.
- **Make the upstream command surface a prerequisite, checked at onboarding.** `/specloop:harness-init` verifies `.claude/commands/opsx/` is present and offers to run `openspec init --tools claude` when it is not — turning an implicit assumption into a preflight step. The same preflight warns when those generated commands have been modified locally, since `openspec update` may overwrite them.
- **Name the supported customisation surface.** An adopter who wants different artifacts or different authoring prompts forks the *schema* (`openspec schema fork`), which survives `openspec update` because it is their own file. Editing a generated command is the wrong lever, and the docs say so rather than leaving people to discover it at the next update.
- **Retire the `namespaced-refs` rule and replace it with `no-forked-upstream-assets`.** The new rule forbids shipping a command, skill, or template that *reproduces* a maintained upstream asset, and requires cross-references to point at `/opsx:` for artifact authoring. It permits a command that delegates to an upstream one to add a guarantee, so long as it holds no copy of the upstream prompt — which is exactly the line `archive` must stay on.
- **Rewrite every cross-reference.** `README.md`, `SETUP.md`, `commands/start.md`, `hooks/_session_brief.py`, `skills/tdd-apply/SKILL.md` and `agents/*.md` refer to `/specloop:propose` and friends throughout; each becomes `/opsx:…` or is dropped.
- **Re-cut the README's workflow diagram** so it shows the seam: upstream authors, Specloop executes and enforces.

## Capabilities

### New Capabilities
- `command-surface`: Specloop's shipped commands are exactly those with no upstream equivalent, and the artifact-authoring commands are deferred to OpenSpec and kept current by it.

## Impact

- **Files removed**: `commands/explore.md`, `commands/propose.md`.
- **Files modified**: `commands/archive.md` (reduced to a delegation), `commands/harness-init.md` (preflight), `commands/start.md`, `README.md`, `SETUP.md`, `openspec/config.yaml` (rule swap), `hooks/_session_brief.py`, `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`.
- **BREAKING for existing users**: `/specloop:explore|propose` stop existing; `/specloop:archive` survives with the same name and a much smaller job. Adoption is one project, so the migration cost is bounded now and grows with every install — this is the cheapest moment to do it.
- **Recovers upstream features for free**: stores, `planningHome`-aware paths, and `/opsx:sync` become available the moment the shadowing stops.
- **Unblocks**: `reposition-specloop`, whose stated boundary is otherwise contradicted by the shipped command set.

## Non-goals

- **Removing `tdd-apply`.** It is the loop, and the loop is the product.
- **Contributing our edits upstream in this change.** The delta audit found the fork is almost entirely staleness, with one exception: the archive commit is behaviour worth an upstream issue asking for a commit affordance. Filing it is not blocking, and until it lands the delegation in `archive.md` carries the guarantee.
- **Renaming `harness` / `.harness.yaml`.** That is `rename-to-gates`.
- **Vendoring or wrapping `/opsx:` commands.** Deferring means pointing at them, not re-exporting them under our namespace — that would be the same mistake with an extra indirection.
