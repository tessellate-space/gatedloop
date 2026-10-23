---
name: workflow-select
description: "Select and install OpenSpec workflow schemas — the bundled default, the community catalog, or gatedloop's own bugfix/architecture packs. Reachable at any time, not only at onboarding: a team can add a workflow the moment the need for it shows up. Declining is a first-class outcome."
argument-hint: "[schema-name]"
---

# Workflow select

Present every workflow schema a project can run, install whichever are chosen, and disclose the one limitation that comes with all of them. This is a **standing capability**, callable on its own at any point in a project's life — `/gatedloop:gates-init` calls it rather than carrying its own copy of this procedure, because the need for a new workflow arrives when the cracks do, not only at setup.

**Stack independence**: every name below is offered as a candidate the adopter confirms, never invoked as a command — the same carve-out `commands/gates-init.md`'s task-runner detector relies on. Nothing here writes a schema into `openspec/config.yaml` or a change's `.openspec.yaml` without the adopter choosing it.

**Input**: optionally a schema name to install directly (skips the menu, still confirms it exists before installing). With no argument, present the full menu.

---

## 1. Present the menu

Three groups, each with a one-line "use this when":

- **Bundled** — `spec-driven` (`proposal → specs → design → tasks`). Already the default; nothing to install. Fine for most feature work.
- **Community catalog** — maintained at <https://github.com/intent-driven-dev/openspec-schemas>, not vendored here (D6: no version pin, drift is theirs to solve, not ours to pre-empt):
  | Schema | Flow | Use when |
  |---|---|---|
  | `intent-driven` | `proposal → specs → design → adr → tasks` | Feature work with meaningful behaviour, technical design, and durable decisions — the recommended non-default choice |
  | `minimalist` | `specs → tasks` | Small, well-scoped, low-risk changes |
  | `spec-driven-with-adr` | `proposal → specs/design → adr → tasks` | `spec-driven` plus durable ADRs, without `intent-driven`'s richer specs |
  | `behaviour-driven` | `proposal → (specs, design) → tasks` | Gherkin-style behaviour specs carry the intent |
  | `event-driven` | `event-storming → event-modeling → specs → design → asyncapi → tasks` | Event-driven/AsyncAPI-first systems |
- **gatedloop packs** — ship in this plugin at `packs/<name>/`, cover the two gaps the catalog leaves:
  | Pack | Flow | Use when |
  |---|---|---|
  | `bugfix` | `report → spec-delta → tasks`, declares `gatedloop.flow: regression-first` | The starting point is a failing reproduction, not a proposal |
  | `architecture` | `explore → design → adr`, no `apply` | The work ends at an accepted decision, not code |

Ask via **AskUserQuestion**: install none (bundled only), one, or several. **Declining is complete, not a partial state** — a team that wants only `spec-driven` is done here; do not treat it as skipped work.

If an argument named a schema, skip straight to confirming it exists in the relevant source (below) rather than re-presenting the menu; still allow declining if it's not what they meant.

## 2. Install each selected schema

For a **community catalog** schema:
```bash
rm -rf /tmp/openspec-schemas && git clone --depth 1 https://github.com/intent-driven-dev/openspec-schemas.git /tmp/openspec-schemas
ls /tmp/openspec-schemas/openspec/schemas/<schema-name>   # confirm it exists before copying
mkdir -p ./openspec/schemas
cp -R /tmp/openspec-schemas/openspec/schemas/<schema-name> ./openspec/schemas/<schema-name>
```

For a **gatedloop pack**, copy from this plugin instead of cloning:
```bash
mkdir -p ./openspec/schemas
cp -R "${CLAUDE_PLUGIN_ROOT}/packs/<pack-name>" ./openspec/schemas/<pack-name>
```

Then, for every schema just installed:
```bash
openspec schema validate <schema-name>
```
A validation failure is reported to the adopter verbatim — do not silently drop the schema or retry with a modified copy (that would be authoring, not installing).

**Companion skills (community schemas only):** check `./openspec/schemas/<schema-name>/skills.txt`. If present, follow the catalog's own Step 6 (`AGENT_INSTALL.md`): clone `https://github.com/intent-driven-dev/skills.git` to a tmp dir and copy each listed skill into `./.agents/skills/<skill-name>`, asking before overwriting one that already exists. If absent, there is nothing to do — most schemas, and both gatedloop packs, have no companion skills.

**Inspect it the moment it lands (design D8) — never skip this.** A schema installed from a catalog is third-party code that will shape every artifact a team writes from here on; nothing else tells an adopter what they just installed.
```bash
gates schema inspect <schema-name> --json
```
Then run the **`schema-review` subagent** (`subagent_type: schema-review`) over that output for the judgement half — fit for this project, instruction coherence, and whether each flagged tool name is real coupling or a passing mention. Show the adopter both the deterministic facts (artifact flow, whether the schema is `implementable` — an `apply` block that tracks a file — the declared `flow`, any `warnings`, flagged names) and the subagent's judgement. `implementable` and `flow` are what `/gatedloop:tdd-apply` routes on: a schema that is not implementable is refused as decision-terminal, and one declaring `gatedloop.flow: regression-first` runs the regression-first route whatever it is named. A fork keeps its pack's flow only if it keeps that declaration. **This is advisory, both halves** (D8's two limits) — report and move on; never refuse to finish the install over a finding.

## 3. Activate (only if the adopter wants it as the project default)

Installing is not the same as activating. Ask separately whether this becomes `openspec/config.yaml`'s project-wide `schema:`, or is only available for individual changes to opt into via their own `.openspec.yaml` (`--schema` flag at change creation, or hand-set after). Most installs are the latter — a project rarely wants every change on the same schema.

## 4. Disclose drift, at this moment — not only in SETUP.md

State plainly, every time a schema is installed: **installed schemas have no upstream update path.** This is a snapshot at today's commit of the catalog; there is no registry, no version pin, and no `openspec schema update`. A later upstream improvement reaches this project only by re-running this skill and re-applying any local fork changes by hand. This is an ecosystem-wide limitation (D6), not something this skill works around.

## 5. Report what is actually installed

Never keep a gatedloop-side list of installed schemas — it would be a second source of truth that can silently disagree with the first. Report the real one:
```bash
openspec schema which --all
```
Show its output as the final confirmation of what this project can now select, regardless of what was just installed in this run — a schema installed by hand or by a previous run shows up here too.
