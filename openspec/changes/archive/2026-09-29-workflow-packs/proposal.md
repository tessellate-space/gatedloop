## Why

Specloop's loop assumes one shape of work: a feature, planned as proposal → specs → design → tasks, implemented test-first. Real teams also fix bugs and make architectural decisions, and those are not features with fewer sections. A bug fix's test **precedes** the plan — the failing repro *is* the oracle. Architecture work's deliverable is an accepted decision and may touch no code at all.

Forcing both through the feature loop produces ceremony on one end and a lie on the other: an architecture change gets a `tasks.md` describing implementation that will never happen. The symptom is the escape hatch: people stop putting the awkward work through the workflow at all. That is fine occasionally and diagnostic in aggregate — **frequent escapes are a signal to pick a different workflow, not a reason to abandon the loop.**

The mechanism to fix this already exists and we do not have to build it. An OpenSpec **schema is a workflow definition** — an artifact DAG with prompts and an apply contract — and workflow selection is already per change (`.openspec.yaml` carries `schema:`; resolution is `--schema` → change metadata → project config → default).

**Five schemas are maintained upstream** in the community catalog at <https://github.com/intent-driven-dev/openspec-schemas>:

| Schema | Shape |
|---|---|
| `minimalist` | specs + tasks only; user stories with Given/When/Then |
| `intent-driven` | proposal → specs → design → adr → tasks |
| `behaviour-driven` | proposal-led, Gherkin GIVEN/WHEN/THEN scenarios |
| `event-driven` | Event Storming discovery → AsyncAPI specification |
| `spec-driven-with-adr` | spec-driven plus persisted architecture decision records |

A sixth, `spec-driven`, ships with the CLI itself — which is why `openspec schemas` in a fresh project lists exactly one, and why the catalog is easy to miss.

So the work is much smaller than "build workflow support": **adopt what exists, author only the two gaps, and teach the loop to dispatch on the change's schema.** Notably, no upstream schema is a bugfix workflow — every one is feature work at varying rigour — so that gap is real and contributable back.

This is also the Stage 5 breadth the plugin exists for: it widens who can adopt the loop without touching enforcement. And it is a prerequisite for any later Stage 6 benchmarking, which grades *per workflow* — with one workflow, a benchmark has one axis and measures almost nothing.

## What Changes

- **Recommend upstream schemas rather than authoring feature workflows.** Document `intent-driven` as the recommended default for feature work, and name the catalog alternatives — `minimalist` for low-ceremony, `spec-driven-with-adr` for decision-heavy repos. `intent-driven` was run as an experiment on a prior personal project with good results, which is the basis for the recommendation.
- **Make schema acquisition a guided step, available at any time.** There is **no registry, marketplace, or install command** in OpenSpec — `openspec schema` offers `which`, `validate`, `fork` and `init`, but nothing that fetches. The community procedure is to point an agent at a raw `AGENT_INSTALL.md` URL and have it copy folders. So selection-and-install becomes a standing capability: onboarding calls it, and a team that onboarded months ago reaches it directly the first time a bug fix does not fit. Declining is a first-class answer, since a team may deliberately want only `spec-driven`.
- **Inspect a workflow before trusting it.** Nothing today tells an adopter what an installed schema actually delivers. A deterministic check enumerates its artifacts, resolves the DAG, and reports whether it has an implementation phase and what that phase tracks; an agent then assesses fit and coherence, and flags stack coupling against the gates the project declares — *"this schema names `cucumber` and `gherkin-lint`; your `.gates.yaml` binds neither"*. It reports, it never blocks an install.
- **Treat `openspec schema which --all` as the registry.** It reports every resolvable schema and whether it came from the project, the user directory, or the package. That is the "what is installed here" answer, so we surface it rather than maintaining a parallel list that could disagree with reality.
- **Author the `bugfix` pack.** `minimalist`-shaped, plus a `report` artifact carrying the failing repro and root cause. The loop **inverts**: the repro exists before the task list and must be RED at task 1, rather than the test being derived from a spec.
- **Author the `architecture` pack.** `explore → design → adr`, ending at an accepted decision with **no `apply` block** — verified possible: a schema omitting `apply` passes `openspec schema validate`.
- **Dispatch the apply flow on the change's schema.** `/specloop:tdd-apply` reads `.openspec.yaml`, routes to the matching flow, and refuses cleanly when a change's schema has no implementation phase. The refusal is decided by inspecting the schema, not by interpreting what `openspec instructions apply` returns — the dangerous response is not an error but a plausible one, which an agent would follow into improvising a task list.
- **Ship packs the way the ecosystem does.** Copy into `openspec/schemas/<name>/` via an agent-readable install doc, following the established `AGENT_INSTALL.md` convention rather than a bash installer.
- **Keep gates out of schema prose.** Packs declare artifacts only. Where an upstream schema hard-codes stack commands into its `tasks` instruction (`behaviour-driven` embeds Cucumber.js, `gherkin-lint` and an `acceptance-tests/` directory), our packs name `gates run <gate>` and let `.gates.yaml` bind it.

## Capabilities

### New Capabilities
- `workflow-packs`: right-sized workflows for work that is not feature work — a bugfix pack whose oracle is a failing repro, an architecture pack that ends at an accepted decision, per-change dispatch of the apply flow, and an install path consistent with the OpenSpec community-schema convention.

### Modified Capabilities
<!-- None yet. If `/specloop:tdd-apply`'s contract is specced by then, dispatch becomes a MODIFIED requirement against it. -->

## Impact

- **Files**: new `templates/packs/bugfix/` and `templates/packs/architecture/` (schema.yaml + templates); new `AGENT_INSTALL.md`; `skills/tdd-apply/SKILL.md` gains schema dispatch; a standing workflow selection/install command plus a schema-inspection agent; `bin/gates` gains schema inspection; `README.md`/`SETUP.md` document selection and installation.
- **Enforcement is untouched.** Only the front half varies by pack — gates, convention review, commit discipline and stop-before-merge are shared by every pack. This change can land in parallel with `harden-unattended-loop`.
- **Extends onboarding**, which `reposition-specloop` D9 establishes as an owned surface: schema selection is one of the named places a team currently stalls.
- **Known ecosystem cost**: installed schemas have **no versioning or update path** anywhere in OpenSpec — confirmed in the docs, the catalog and the install guide. Packs will drift after install. Accepted here; a `pack update` command is a later differentiator, not a prerequisite.
- **Contributable upstream**: the bugfix pack's *artifacts* have no equivalent in the catalog. Its *gates* stay here, per the rejection test.

## Non-goals

- **Authoring a feature-work schema.** `intent-driven` exists and is maintained; duplicating it is the exact failure the rejection test forbids.
- **Vendoring upstream schemas into the plugin.** We recommend and install, we do not fork and carry.
- **Adding authoring gates** (adversarial review, grill-me, glossary). Whether those belong in Specloop is an open question owned by `reposition-specloop`.
- **A `pack update` / versioning mechanism.** Named as the accepted cost above.
- **Benchmarking packs.** Needs the headless entry point and a ledger first; packs are its prerequisite, not its delivery.
