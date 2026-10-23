## Why

Specloop currently describes itself as a self-contained spec-driven workflow. Reading the OpenSpec schema format and the intent-driven corpus showed that most of the front half of that workflow — proposal, specs, design, ADRs, glossary, adversarial review — **already exists upstream, is maintained there, and is more developed than anything we would write**. An OpenSpec schema is not a template folder; it is a workflow definition (an artifact DAG with prompts and an apply contract), and five of them ship in a community catalog today, alongside the one bundled with the CLI.

Without a stated boundary, the next scope argument gets decided by whoever is talking. The proof that this is not hypothetical is in this repository: three of the five shipped commands are renamed copies of OpenSpec's own, and they have already fallen behind their originals. `unfork-commands` removes them; this change writes down the rule that would have stopped them being added.

The boundary that survives contact with the ecosystem is narrower and more defensible: **Specloop is the enforcement and onboarding layer for OpenSpec.** Upstream decides *what* to build and in what order; the project decides what "tests pass" means; Specloop carries a change from an approved plan to verified-on-main, and gets a team onto that loop in the first place.

There is already a frame for saying this, and it was written without reference to Specloop. An existing OpenSpec adoption model scores each SDLC phase 0–4 — `none`, `advise`, `observe`, `act`, `close` — across three levels: rookie (install and go), intermediate (fork a schema, write the constitution), advanced (subagents, hook-enforced gates, oracles). Its own answer to *"how do I get a gate?"* is that **the gate only exists because a team builds one**, and the coverage audit built on its scale diagnoses every phase stuck at `act` as *held there by missing oracles, not missing tools*. **Specloop is that third rung, prefabricated** — the same boundary, in a unit that can be scored, phrased for an audience that has already been taught it.

This change writes that boundary into the artifacts a reader actually encounters, and fixes a defect found while deriving it: the `rules:` block in `openspec/config.yaml` is silently ignored by the OpenSpec CLI.

## What Changes

- **State the boundary in the manifests.** Rewrite `description` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` around closing the loop and delegating both axes ("bring your own schema, bring your own stack") rather than describing a whole SDLC.
- **Restructure `README.md` and `SETUP.md` around delegation.** Make explicit what Specloop owns (execution gates, enforcement, the loop, onboarding), what it delegates upstream (artifacts, authoring, workflow shape), and what it delegates to the project (commands, probes, conventions). Document that OpenSpec is a prerequisite and *why* — the four things the loop needs from a task source.
- **Give onboarding equal billing with enforcement.** It is one of the two things the rejection test says are ours, and setup friction is the main reason teams never reach a working spec-driven loop. Docs treat it as an owned surface, not as compensation for a narrower scope.
- **Add the rejection test as a stated rule.** Record the four-question test (authors an artifact → not ours; knows a stack command → not ours; makes a guarantee enforceable → ours; gets a team running faster → ours) in the conventions rules-doc, so future scope arguments have a written arbiter.
- **Position on the ladder.** README, SETUP and the manifests describe Specloop as the advanced rung prefabricated, and name the two owned jobs in ladder terms: **climb** (get a team up the levels without building the machinery) and **close** (supply the gate, oracle and hook that turn `act` into `close`). State the limit honestly too — Requirements never moves and System design stops at `act`, because neither has a machine-readable verdict.
- **Adopt gate / oracle / hook as shipped vocabulary.** Define all three where a reader meets the gate contract. "Oracle" is the missing word: it is *why* the contract is an exit code and nothing else, which the docs currently assert without arguing.
- **BREAKING (to the conventions format): fix `openspec/config.yaml` by taking the conventions out of it.** The current `rules: conventions: |` block is rejected at runtime — `openspec new change` prints *"Rules for 'conventions' must be an array of strings, ignoring this artifact's rules"*. The cause is one file serving two consumers with incompatible shapes. Move the rule-id prose to its own **conventions source file**, and **generate** `config.yaml`'s `rules:` from it, keyed by artifact id as arrays of strings.
- **Make the generated block checkable.** `gates validate` fails loudly when `config.yaml`'s `rules:` no longer match what the source would produce — a generator nobody runs is worse than no generator. The same command targets an adopter's project, not just this repo, which makes conventions an onboarding deliverable rather than hand-written YAML.
- **Keep the rule-ids working for their other consumer.** `convention-review` resolves rule-ids against the conventions source directly via the shim; that path must keep working after the move.
- **Document why rule-ids exist.** Their rationale — citable findings, per-surface selection, detectable dangling references, one rules-doc serving two consumers — is currently unwritten, which makes "just inline the prose" a recurring and superficially reasonable proposal.
- **Record approval in `.openspec.yaml`.** Each change carries `approved_by`, `approved_at` and `approved_sha` in its metadata file, so approval is traceable from the repository itself rather than from PR history, is machine-readable, and is pinned to the exact artifact content that was approved. Verified that OpenSpec tolerates the extra keys. The matching *enforcement* belongs to `harden-unattended-loop`.
- **Land the design memo** at `docs/specloop-map.html` as the durable record of the boundary and the ladder scoring.

## Capabilities

### New Capabilities
- `plugin-positioning`: the plugin states its boundary in a machine-and-human readable way — manifest descriptions, README/SETUP structure, a written rejection test, and a documented rule-id rationale — and its conventions rules-doc is in a form the OpenSpec CLI actually accepts.

### Modified Capabilities
<!-- None. No loop behaviour, gate, or agent contract changes here. -->

## Impact

- **Files**: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`, `SETUP.md`, `openspec/config.yaml`, the new conventions source file, `docs/specloop-map.html` (new).
- **One shim change**, the sole exception to "docs only": `gates` gains conventions generation and the matching drift check in `validate`. The loop, its gates, and every agent contract are untouched.
- **Fixes a live defect**: config rules are currently ignored, so any project copying Specloop's config layout inherits a rules block that never reaches an artifact step.
- **Depends on**: `unfork-commands` (the command set must match the stated boundary) and `rename-to-gates` (the docs should be written once, in the final vocabulary).
- **Unblocks**: `workflow-packs` — its scope arguments ("do we author this or adopt it?") are decided by the rejection test this change records.

## Non-goals

- **Authoring or forking any workflow schema.** That is `workflow-packs`.
- **Deleting the forked commands.** That is `unfork-commands`; this change records the rule, that one applies it.
- **Executing the `harness` → `gates` rename.** The decision is recorded here (design D8); `rename-to-gates` carries it out.
- **Adding authoring gates** (adversarial review, grill-me). Whether those belong in Specloop at all is recorded as a decision in principle (design D6), but building one is a later change.
- **Any change to enforcement, the ledger, or hooks.** That is `harden-unattended-loop`.
