## Context

Specloop ships one loop shape. The mechanism for more already exists upstream and is not ours to build:

- An OpenSpec **schema is a workflow definition** — artifacts with `id`, `generates`, `template`, `instruction`, `requires`, plus an `apply` block naming the implementation gate and its tracking file.
- **Selection is already per change**: resolution runs `--schema` flag → change metadata (`.openspec.yaml`) → project config → default `spec-driven`.
- **Five schemas are maintained upstream** at <https://github.com/intent-driven-dev/openspec-schemas>, distributed as standalone repositories and installed by copying into `openspec/schemas/<name>/`. A sixth, `spec-driven`, is bundled with the CLI.

Two facts shape what is left to do. First, **no upstream schema is a bugfix workflow** — `minimalist`, `intent-driven`, `behaviour-driven`, `event-driven` and `spec-driven-with-adr` are all feature work at varying rigour. Second, **a schema may omit `apply` entirely** — verified by validating a two-artifact `design → adr` schema with no apply block.

## Goals / Non-Goals

**Goals:** right-size the loop for bug fixing and architecture work; dispatch the apply flow on the change's schema; adopt rather than duplicate upstream feature workflows; keep stack commands out of pack prose.

**Non-Goals:** authoring a feature schema; vendoring upstream schemas; authoring gates; a pack update/versioning mechanism; benchmarking.

## Decisions

### D1: Only the front half varies — gates are pack-invariant
```
   VARIES BY PACK              │  SHARED BY EVERY PACK
   ───────────────────────────────────────────────────────
   the artifact DAG            │  gates run ci
   the entry condition         │  convention-review
   (what "red" means at task 1)│  commit discipline
   whether code exists at all  │  verify / live-check
                               │  STOP BEFORE MERGE
```
This is what makes packs cheap and safe: they add no enforcement surface and can land in parallel with `harden-unattended-loop`. It also sets the authoring rule — **if it produces an exit code it is a gate, not an artifact.**

### D2: Adopt upstream for feature work; author only the gaps
`intent-driven` (proposal → specs → design → adr → tasks) was exercised as an experiment on a prior personal project with good results, which is the empirical basis for recommending it. Authoring our own equivalent would create two competing definitions of the same workflow — and this repository has already demonstrated where that leads, in three shipped commands that turned out to be stale copies of upstream's. We recommend and install; we do not fork and carry.

Applying the rejection test recorded in `reposition-specloop`: the bugfix pack's **artifacts** answer "authors an artifact?" → not ours → contributable upstream. Its **gates** answer "makes a guarantee enforceable?" → ours.

### D3: The bugfix pack inverts TDD's direction
In feature work the test is derived from a spec. In a bug fix the failing reproduction exists **first**, and the spec delta is derived *from it* — it is the scenario that should have caught the bug.

```
   feature   spec ──────────► test ──────► implementation
   bugfix    repro (RED) ───► root cause ─► spec delta ──► fix ──► repro (GREEN)
```

Consequences: the reproduction must be RED before the fix, and a reproduction that passes is a halt condition, not a pass — it does not reproduce the reported bug. And a bug fix that changes no spec is worth surfacing: either the specs had a gap, or they were right and only the implementation was wrong. Both are informative, so the flow reports it rather than silently skipping.

**Resolved: the spec delta is mandatory for every bug fix.** The safer default, because the alternative fails silently. If a delta is optional, the path of least resistance on a "trivial" fix is to skip it — and the fixes most likely to be called trivial are exactly the ones where the spec quietly diverges from behaviour. Mandating it converts every bug into one of two recorded outcomes:

- the specs had a **gap** — the delta closes it, and `verify` gains a scenario that would have caught the bug; or
- the specs were **already correct** — the delta is a MODIFIED requirement restating existing behaviour, and the record shows the defect was purely in implementation.

The second case is where the ceremony objection bites: on a one-line typo fix, restating a requirement is real overhead for a small return. Accepted deliberately — the cost is bounded (one scenario) and it buys a spec corpus that cannot silently rot, which is the entire premise of a spec-anchored workflow. The `verify` gate is only as good as the scenarios in it, and bug fixes are the highest-signal source of missing ones.

### D4: The architecture pack ends at a decision, with no apply block
`explore → design → adr`, terminal. The alternative — a token `tasks.md` saying "record the ADR" — would misrepresent the work and give the loop a cursor pointing at nothing. Since an apply-less schema validates, the honest shape is available and should be used.

The cost is that `/specloop:tdd-apply` can now be handed a change it must refuse. That refusal has to be **explicit and clean**, because the failure mode otherwise is an agent improvising a task list for work that has none.

An earlier revision made this depend on a spike: *what does `openspec instructions apply` return for an apply-less schema?* That framing was wrong, because every possible answer is a bad thing to build on. If the command errors, the refusal reads an exit code; if it returns an empty instruction, an exit code is not enough; and if it returns something generic and plausible-looking, an agent proceeds — finds no `tasks.md`, and invents one. The dangerous case is not the crash, it is the plausible answer.

**Decision: the schema is inspected before the command is invoked.** D8's deliverable check resolves the schema and reports whether an `apply` block exists, in code. `tdd-apply` refuses on that fact, and never has to interpret a response. The spike still runs — the behaviour is worth knowing and it is one command — but it no longer decides anything.

### D5: Install by the ecosystem's convention, not our own
Upstream installs schemas by directing an agent to read an `AGENT_INSTALL.md`: clone, enumerate, copy preserving structure, activate in `config.yaml`, validate. Adopting this verbatim means users installing a Specloop pack and a community schema follow one procedure, and it suits a plugin better than a bash installer.

### D6: Accept drift; do not solve it first
No versioning or update path exists anywhere in the OpenSpec schema ecosystem — confirmed in the docs, the catalog and the install guide. Drift after install is an ecosystem-wide accepted limitation, not a Specloop problem to solve before shipping. Disclose it at install time. A `pack update` would be a differentiator later, and solving it first would delay the Stage 5 breadth that is the point of this change.

A lockfile-plus-drift-check was considered as a differentiator — record each installed schema's source and commit, then report installed / upstream-moved / locally-modified. It passes the rejection test cleanly. **Rejected for now on the same principle as the rest of this change:** the ecosystem accepts this cost, and building a versioning mechanism for a format whose owners have not versioned it means guessing at a convention they may later contradict. Revisit when either upstream signals a direction or drift actually bites an adopter.

### D7: Acquisition is a standing capability, and the registry already exists
Two related questions — *how does a user get a schema?* and *what tracks which schemas are installed?* — have concrete answers that are easy to miss.

**Acquisition: there is no install mechanism.** `openspec schema` offers `which`, `validate`, `fork` and `init`; there is no `add`, no `install`, no registry, and no marketplace. The community procedure is to hand an agent a raw `AGENT_INSTALL.md` URL and have it clone, enumerate, copy preserving structure, activate in `config.yaml`, and validate. Resolution then runs project `openspec/schemas/` → user `~/.local/share/openspec/schemas/` → bundled.

That is a real friction point of exactly the kind `reposition-specloop` D9 puts inside our boundary, so **onboarding asks which workflows the project wants and performs the install**, rather than leaving the user to discover a catalog that `openspec schemas` does not mention. Declining is a first-class answer — a team may deliberately want only the bundled `spec-driven`, and an onboarding flow that force-feeds five community schemas is friction of its own making.

**Installation is a standing capability, not an onboarding branch.** The need for a new workflow does not arrive at onboarding time — it arrives when the cracks do, at the first bug fix that does not fit or the first decision with nowhere to live. A team that onboarded six months ago must be able to add `behaviour-driven` in one step, without re-running setup and without re-finding a catalog they were shown once. So the selection-and-install flow is reachable on its own, and onboarding calls it rather than containing it.

This also settles where packs live, which was previously open. If the install path is a URL and the procedure is the same either way, the repository boundary stops mattering: in-repo keeps packs versioned with the plugin, a sibling bundle matches how every other community schema is published and lets non-Specloop users adopt the bugfix workflow. **Decision: pick whichever keeps the install one step, and treat the choice as reversible** — it is a repository move plus a URL change, not a design commitment.

**Registry: `openspec schema which --all` is it.** It reports every resolvable schema and where each resolves from. Maintaining our own list of installed schemas would create a second source of truth that can disagree with the first, and the disagreement would be silent. So we surface the existing command rather than tracking state ourselves — the same reasoning that makes dispatch read OpenSpec's resolved schema rather than inventing a parallel selector.

### D8: Inspect a pack before trusting it — deliverables in code, fit by judgement
A schema installed from a catalog is third-party code that will shape every artifact a team writes. Nothing today tells an adopter what they just installed, and two of this change's own problems are instances of that gap: an apply-less schema that the loop must refuse (D4), and `behaviour-driven` hard-coding Cucumber.js into instruction prose (D1's authoring rule, violated upstream). Both are discoverable by reading the schema. Neither is discovered today.

The check splits along the seam Specloop already uses everywhere else — **selection in code, judgement in an agent**:

```
   DETERMINISTIC (shim)                │  JUDGEMENT (agent)
   ────────────────────────────────────┼──────────────────────────────────
   enumerate artifacts, resolve the    │  does this workflow suit this
     DAG, detect cycles                │    project's kind of work?
   does an `apply` block exist,        │  are the instructions coherent,
     and what does it track?           │    or contradictory?
   scan templates/instructions for     │  is a flagged tool name a real
     tool-name-shaped strings          │    coupling or a passing mention?
   cross-check those against the       │
     gates the project declares        │
```

The deterministic half is not a convenience. It is the same reasoning that put hot-surface selection in `bin/gates`: an agent reading YAML can silently fail to notice a missing `apply` key, and the consequence here is the loop improvising implementation for a change that has none. Code notices, or nothing does.

The judgement half is `convention-review`'s shape applied to a schema instead of a diff — cheap, read-only, and citing what it found rather than pronouncing on quality in the abstract. The most valuable thing it produces is the coupling report: *"this schema names `cucumber` and `gherkin-lint`; your `.gates.yaml` binds neither"* is actionable at install time and invisible at first use.

> **Spike update (task 1.2, 2026-09-23):** re-cloning the catalog shows upstream fixed this exact coupling on 2026-08-03 (`decouple-stack-docs-to-skill`) — `behaviour-driven`'s `schema.yaml` no longer names Cucumber or `gherkin-lint` anywhere; the stack-specific detail moved to a companion skill (`acceptance-test-authoring`, installed separately via `skills.txt`) outside the schema artifacts the inspector scans. The precedent that motivated D8 no longer reproduces upstream. This does not weaken the case for inspection — a schema that couples to a stack tool inside its own `artifacts[].instruction` is still a real risk class, task 2c.7 just cannot use `behaviour-driven` as its confirming example anymore. 2c.7 records whatever the inspector actually finds across the five current schemas instead of asserting this specific historical finding.

Against the rejection test: inspection authors nothing and names no stack command; it makes a stated guarantee enforceable (the loop never improvises implementation for a decision-only workflow) and it gets a team running faster (a bad fit is flagged before it shapes a quarter's artifacts). Ours on both counts, and it is the **climb** job from `reposition-specloop` D3.

Two limits, stated so they are not discovered as disappointments. Inspection reports; it never edits or refuses to install a schema — the adopter may have good reasons, and a tool that blocks third-party content on a heuristic will be worked around. And a flagged tool name is a *finding*, not a verdict: a schema mentioning `npm` in an example is not the same as one that requires it.

## Risks / Trade-offs

- **Pack proliferation** → three or four packs, never ten. Every pack is a schema plus a matched flow plus maintenance. Bugfix and architecture cover the work types actually named; anything further needs its own justification.
- **Dispatch becomes a second selection mechanism** → mitigated by reading the schema OpenSpec already resolved, never inventing a parallel selector.
- **Inspection becomes a schema linter with opinions** → bounded by D8's two limits: it reports rather than blocks, and a flagged tool name is a finding rather than a verdict. If it starts prescribing how schemas should be written, it has crossed into authoring and the rejection test rejects it.
- **Schema format churn upstream** → packs track the format; a format change is upstream's release and our follow-up. Fewer authored packs means less exposure, which is another argument for adopting rather than writing.
- **A pack quietly reintroducing stack coupling** → the spec requires an audit for tool names; `behaviour-driven` embedding Cucumber.js is the concrete precedent for how easily this happens.

## Open Questions

- ~~**Is a spec delta mandatory in the bugfix pack?**~~ — **RESOLVED (D3)**: yes, always. Optional means skipped on exactly the fixes where the spec is most likely already wrong.
- ~~**Do packs live in this repo or a sibling `openspec-schemas`-style repo?**~~ — **RESOLVED (D7)**: the requirement is that installation is one step and available at any time, not only at onboarding. Given that, the location is reversible and not worth blocking on.
- ~~**What does `openspec instructions apply` return for an apply-less schema?**~~ (D4) — **RESOLVED (spike 1.5, 2026-09-23)**: confirmed the dangerous case named in D4. A minimal `explore → adr` schema with no `apply:` block, once all artifacts exist, makes `openspec instructions apply --json` return `"state": "ready"`, `"tasks": []`, `"instruction": "All required artifacts complete. Proceed with implementation."` — plausible-looking and exactly the shape an agent would act on. This is not a crash and not an empty response; it is the "proceeds and invents a task list" failure D4 predicted, observed directly. Confirms dispatch must never call this command before D8's inspection has checked for an `apply:` key.
- ~~**How is a "tool-name-shaped string" recognised?**~~ (D8) — **RESOLVED (spike 1.3, 2026-09-23)**: both, not either — a small curated list of known ecosystem tool/product names (seeded from `docs/conventions.md`'s own examples: pytest, npm/yarn/pnpm, jest, mocha, cucumber, gherkin-lint, maven, gradle, cargo, docker, kubectl, terraform, webpack, vite, rspec, junit, pip, poetry, eslint, prettier, keycloak, shadcn, postgres, redis) catches product/library nouns a heuristic would miss (nothing about "shadcn" looks command-shaped in prose); a regex over fenced/inline code spans for command-shaped tokens (`<word> (install|run|test|build|lint|exec|add)`) catches invocations not on the list. Findings from either path are advisory (D8's two limits), which is why the noisier union is acceptable rather than a single precise method.
- **Should the `bugfix` pack's artifacts be contributed upstream to the community catalog?** (D2, task 7.4) The rejection test's own logic makes this pack a *tolerated* exception, not a settled one: D2 already concedes that "authors an artifact?" answers *not ours* for `bugfix`'s artifact shape (`report`/`spec-delta`) — it stays here only because "no equivalent exists in the catalog" today, the same reasoning that makes `architecture`'s decision-terminal shape tolerated. If either gap gets filled upstream, or a contribution is accepted, this pack becomes a duplicate under `no-forked-upstream-assets` and D2's own precedent (three stale command forks, `unfork-commands`) says what happens next: it gets recommended-and-deleted, the same way this design recommends `intent-driven` over authoring a competing feature schema. Left open rather than resolved here because it depends on an upstream maintainer's willingness, not on anything this change controls.
