## 1. Spikes that could change the design (do these first)

- [x] 1.1 Read a schema's on-disk shape closely enough to inspect it in code: artifact fields, `requires` edges, and exactly how an `apply` block is expressed when present
- [x] 1.2 Clone <https://github.com/intent-driven-dev/openspec-schemas> and read `intent-driven` and `minimalist` `schema.yaml` in full; confirm `intent-driven` is the right recommended default and record any gap
- [x] 1.3 Decide how a tool-name-shaped string is recognised — curated list or heuristic (D8 open question) — and record the choice
- [x] 1.4 Confirm the catalog's `AGENT_INSTALL.md` procedure still works as documented, and that `openspec schema which --all` reports a freshly installed schema
- [x] 1.5 Informational: record what `openspec instructions apply` returns for an apply-less schema — no longer blocking, since dispatch refuses on inspection (D4)

## 2. Recommend upstream, do not duplicate

- [x] 2.1 Document `intent-driven` as the recommended default for feature work, with `minimalist` and `spec-driven-with-adr` as named alternatives — and cite the catalog URL, since `openspec schemas` does not mention it
- [x] 2.2 State in SETUP that schema selection is per change (`.openspec.yaml`) and how to choose one at change creation
- [x] 2.3 Confirm nothing shipped duplicates an upstream feature workflow (rejection test, from `reposition-specloop`) — confirmed: this change ships `bugfix` (report → spec-delta → tasks) and `architecture` (explore → design → adr, no apply), neither of which exists in the community catalog (`spec-driven-with-adr` is the closest and is a strict subset of `intent-driven`, which this change recommends rather than reimplements); re-checked at 7.3 once both packs are authored

## 2b. Schema acquisition as a standing capability (D7)

- [x] 2b.1 Build workflow selection as its own reachable capability, not a branch inside onboarding: present the bundled schema, the community catalog, and the shipped packs, each with a one-line "use this when…" — `skills/workflow-select/SKILL.md`, directly invocable (`/specloop:workflow-select`), not nested inside gates-init
- [x] 2b.2 Install the chosen schemas into `openspec/schemas/`, activate them, and validate with `openspec schema validate` — skill step 2 (install) and step 3 (activate, asked separately from install)
- [x] 2b.3 Make declining a first-class path — it completes with the bundled schema alone and installs nothing — skill step 1
- [x] 2b.4 Report installed workflows from `openspec schema which --all`, never from a list Specloop maintains — skill step 5
- [x] 2b.5 Disclose the drift limitation at the moment of install, not only in SETUP — skill step 4
- [x] 2b.6 Have onboarding invoke this capability rather than carry its own copy of the procedure — `commands/gates-init.md` step 2b now delegates to the skill
- [x] 2b.7 Test in a throwaway project: select some, select none, select all — and adding a workflow to a project that was onboarded earlier — verified live against the community catalog (none/bundled-only, multiple at once, and adding `behaviour-driven` to a project that already had `intent-driven` from spike 1.4); the packs half of "select all" is re-verified end-to-end once `bugfix`/`architecture` exist (task 6.3)
- [x] 2b.8 Choose where packs are published (in-repo or sibling bundle) on the basis of which keeps the install one step; record it as reversible — **in-repo**, at `packs/<name>/` (kept out of this repo's own `openspec/schemas/`, which is Specloop's own active project, not distributed content); recorded as reversible in SETUP.md — the install path is a copy either way, so moving to a sibling bundle later is a source-URL change, not a design change

## 2c. Inspect a workflow before trusting it (D8)

- [x] 2c.1 `gates` gains schema inspection: resolve a schema, enumerate artifacts in dependency order, report cycles and unsatisfiable `requires` — `gates schema inspect <name>` / `--path <dir>`, `bin/gates` (`detect_requires_issues`, DFS cycle detection)
- [x] 2c.2 Report deterministically whether an `apply` block exists and what it tracks — this is the fact dispatch refuses on (D4) — `schema_apply_info`
- [x] 2c.3 Scan templates and instructions for tool-name-shaped strings using the method chosen in 1.3 — `scan_tool_names` (curated list ∪ command-shaped regex over code spans)
- [x] 2c.4 Cross-check those against the gates declared in `.gates.yaml`; report any that nothing binds — `cross_check_gate_binding`
- [x] 2c.5 Add a read-only inspection agent for the judgement half: fit for this project, coherence of the instructions, whether a flagged name is real coupling or a passing mention — `agents/schema-review.md`
- [x] 2c.6 Findings are advisory — the schema installs unmodified regardless, and the report says so — every `gates schema inspect` report ends with that line; `schema-review`'s own instructions repeat it
- [x] 2c.7 Run the inspection over all five community schemas plus both shipped packs; confirm it flags `behaviour-driven`'s Cucumber.js coupling and the architecture pack's absent `apply` block — ran (with PyYAML present — `_mini_yaml` cannot safely parse a third-party `schema.yaml`, confirmed live and now a loud refusal, see `bin/gates` `cmd_schema_inspect`) over all five current community schemas plus both packs. `behaviour-driven`'s Cucumber coupling is gone upstream (see design.md's spike-1.2 note) so that specific assertion no longer applies, but the inspector still earns its keep: `intent-driven`/`spec-driven-with-adr` flag `postgres` (a passing mention — an example ADR filename, `0042-use-postgres-for-catalog.md`), `event-driven` flags `asyncapi-cli` as real coupling unbound by this project's `.gates.yaml`, and `bugfix` finds nothing (clean, as authored). The architecture pack's absent `apply` block is confirmed both by the inspector (`apply: NO`) and live against a real change (`openspec instructions apply` returns the plausible "ready"/"Proceed with implementation" trap D4 named).
- [x] 2c.8 Wire inspection into the install flow so a newly installed schema is reported on at the moment it lands — `skills/workflow-select/SKILL.md` step 2 now runs `gates schema inspect --json` plus the `schema-review` subagent right after `openspec schema validate`

## 3. Author the bugfix pack

- [x] 3.1 `schema.yaml`: `report` (failing repro + root cause) → `spec-delta` → `tasks`; `apply.tracks: tasks.md` — `packs/bugfix/schema.yaml`; also added `packs/**` to `.gates.yaml`'s `prompts` surface so pack content is convention-reviewed like every other shipped prompt
- [x] 3.2 Templates for `report` and the spec delta; the report must capture a runnable reproduction, not a prose description — `packs/bugfix/templates/{report,spec-delta,tasks}.md`
- [x] 3.3 Matched apply flow: run the repro FIRST and require RED; halt if it passes (it does not reproduce the bug) — `schema.yaml`'s `apply.instruction` (portable) and `tasks.md` template's section 1; Specloop's own enforcement of this wired in task 5.3
- [x] 3.4 Fix, then require the same repro GREEN; commit fix and repro together — `apply.instruction` steps 3-4, `tasks.md` template section 3
- [x] 3.5 Require a spec delta on every bug fix — ADDED scenario when the specs had a gap, MODIFIED restatement when they were already correct and only the implementation was wrong; no bug fix lands without one — enforced structurally by the artifact DAG itself (`tasks` requires `spec-delta` requires `report`), not just by instruction prose; `spec-delta.md` template presents both shapes explicitly
- [x] 3.6 `openspec schema validate bugfix` passes; audit templates and instructions for stack-specific tool names — validated live in a throwaway project (`✓ Schema 'bugfix' is valid`); `gates schema inspect --path packs/bugfix` finds no tool-name-shaped strings

## 4. Author the architecture pack

- [x] 4.1 `schema.yaml`: `explore` → `design` → `adr`, with **no** `apply` block — `packs/architecture/schema.yaml`
- [x] 4.2 Templates; ADR immutable-and-supersedable, consistent with the upstream ADR convention — `packs/architecture/templates/{explore,design,adr}.md`; the `adr` artifact's instruction states the same IRON RULE (never edit a prior ADR, record a new one with `Supersedes:` instead) in this pack's own wording, not copied from a community schema (no-forked-upstream-assets)
- [x] 4.3 `openspec schema validate architecture` passes with no apply block — validated live (`✓ Schema 'architecture' is valid`); caught and fixed a real YAML parse error along the way (an unquoted `description:` containing a bare colon)
- [x] 4.4 Verify a change using it reaches completion with no `tasks.md` and no implementation expected — confirmed live: with all three artifacts present, `openspec status` reports `isComplete: true` and `openspec instructions apply` returns `state: "ready"`, `tasks: []`, `"Proceed with implementation."` — the exact plausible-looking apply-less trap spike 1.5 predicted, now reproduced against the real pack. `gates schema inspect --path packs/architecture` reports `apply: NO` — the fact task 5.4's dispatch refusal reads instead of this response

## 5. Dispatch in the apply flow

- [x] 5.1 `skills/tdd-apply/SKILL.md`: read `schema:` from the change's `.openspec.yaml` and route to the matching flow — new step "2b. Dispatch on the change's schema"; reads the RESOLVED name from `openspec status`'s `schemaName` (already the `--schema` flag → `.openspec.yaml` → project-default resolution OpenSpec itself performs) rather than re-parsing `.openspec.yaml` by hand and duplicating that order
- [x] 5.2 Feature schemas → the existing per-task TDD loop, unchanged — step 5 body untouched; 2b routes here for anything that isn't apply-less and isn't `bugfix`
- [x] 5.3 `bugfix` → the regression-first flow — new "5-bugfix" section: same gates/review/commit machinery, entry condition inverted (RED-first, halt-if-green-on-first-run), and the three task groups collapse to one commit unit so the fix and its regression test never split across commits (D3)
- [x] 5.4 Apply-less schema → refuse cleanly with an explanation, deciding from 2c.2's inspection rather than from an instruction response; never improvise a task list — 2b step 3: `gates schema inspect`'s `apply.has_apply`, never `openspec instructions apply`'s response; refuses before branching, no tasks.md invented
- [x] 5.5 Confirm gates, convention review, commit discipline and stop-before-merge are identical across every route (D1) — stated as an explicit guardrail; 5-bugfix reuses 5f/5h's gate+review+commit steps verbatim rather than restating them, and step 7.5 (completion/merge) is untouched and shared by every route

## 6. Install path

- [x] 6.1 `AGENT_INSTALL.md` following the community convention: enumerate, copy preserving structure, activate, validate — at plugin root, modeled on (not copied from) the community catalog's own file; original prose, `packs/<name>` in place of `openspec/schemas/<name>`
- [x] 6.2 Disclose at install time that installed schemas have no upstream update path and will drift — `AGENT_INSTALL.md`'s closing section, plus `workflow-select`'s step 4 for the interactive path
- [x] 6.3 Install both packs into a throwaway project end-to-end and run one change through each — verified live: `bugfix` (`fix-null-pointer`, a realistic null-guard report → spec delta → tasks) and `architecture` (`decide-caching-strategy`, explore → design → a real superseding-capable ADR at `adr/0001-...md` → adr.md manifest); both `openspec schema validate` clean, both `openspec status`/`instructions apply` behave as designed (`architecture` reproduces D4's completion trap again, on real content this time)

## 7. Docs and close-out

- [x] 7.1 README/SETUP: the pack menu, when to use which, and how selection works — SETUP.md's "Choosing a schema" (task 2), README.md's new "Choosing a workflow pack" plus `workflow-select`/`schema-review` added to the component tables
- [x] 7.2 Audit every shipped pack file for project-specific tool names — none may appear — `gates schema inspect --path packs/bugfix` and `--path packs/architecture` both report no tool-name-shaped strings (confirmed with PyYAML present, task 3.6/4.3); re-confirmed clean after this task's README edits (which don't touch `packs/`)
- [x] 7.3 `claude plugin validate .` passes; re-check the whole change against the rejection test — `claude plugin validate .` → `✔ Validation passed`. Rejection test re-check: `workflow-select` and `gates schema inspect` select/install and report, never author change content or bind a stack command — ours. The two packs' *artifacts* are the one honest exception, not a clean pass — see design.md's new Open Question (7.4) recording exactly that, rather than papering over it
- [x] 7.4 Open the question of contributing the bugfix pack's artifacts upstream (no equivalent exists in the catalog) — recorded in design.md's Open Questions, tied explicitly to D2's own "not ours" concession and `unfork-commands`' precedent for what happens if it's ever filled upstream
