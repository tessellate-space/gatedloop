## 0. Preconditions

- [x] 0.1 Confirm `unfork-commands` is merged — the shipped command set must match the boundary these docs state — archived `2026-08-17-unfork-commands`
- [x] 0.2 Confirm `rename-to-gates` is merged — these docs are written once, in the final vocabulary — merged `650035d`, archived `2026-08-18-rename-to-gates`; write `gates` / `.gates.yaml` / `gatesVersion` throughout, and mention `harness` only where describing the deprecation forwarder

## 1. Fix the conventions defect first (it is verifiable independently)

- [x] 1.1 Choose the conventions source path, jointly with `rename-to-gates`'s open question about where `.gates.yaml` lives — one decision about where the plugin's owned files sit, not two.

      **Decided 2026-08-18: split by who writes the file, not by what it is about.**

      | Path | Written by | Committed |
      |---|---|---|
      | `.gates.yaml` (repo root) | the adopter, constantly | yes |
      | `docs/conventions.md` | the adopter, authored prose with `### <rule-id>` anchors | yes |
      | `.specloop/runs/<change>.jsonl` | the tool | yes (durable ledger) |
      | marker files under `.git/` | the tool | never |

      Rationale: hand-edited configuration belongs where adopters look for
      configuration — root, beside `.gitignore` and every other tool's config —
      while tool-written state belongs in a directory that can be reasoned about
      wholesale. This is the `.eslintrc` / `.eslintcache` split.

      The rejected alternative was moving everything under `.specloop/`. It is
      tidier, but it would relocate `.gates.yaml` a *second* time within days of
      the harness→gates rename, requiring a second compat path while the first
      one is still shipping. `rename-to-gates` design left this open on the
      grounds that "moving later is a one-line loader change" — true of the
      loader, false of the adopters, and the migration window argument that
      justified renaming *now* applies against moving again.

      Consequence for `harden-unattended-loop`: `.specloop/runs/` as already
      specified in its §1b is correct and needs no change.
- [x] 1.2 Move the rule-id prose out of `openspec/config.yaml` into that file, unchanged in content; point `conventions.rules-doc` at it
- [x] 1.3 Give each `### <rule-id>` section an `Applies to:` line (`proposal` / `specs` / `design` / `tasks`, or `code` for review-only) and a one-line imperative statement of the rule
- [x] 1.4 Add `gates conventions sync`: read the source, emit `config.yaml`'s `rules:` keyed by artifact id as arrays of strings, omitting `code`-only rules
- [x] 1.4a The artifact ids are **not a fixed set** — they come from the *active schema*, and they differ per schema. Measured 2026-08-18 across the whole catalog: `minimalist` has only `specs`/`tasks` (no `proposal`); `event-driven` adds `asyncapi`, `event-storming`, `event-modeling`; `intent-driven` and `spec-driven-with-adr` add `adr`. Upstream's own `AGENT_INSTALL.md` Step 4 tells installers to hand-edit `rules:` to match `artifacts[].id` for exactly this reason. So the generator must read the active schema's ids rather than emit a hard-coded key set — and **switching or installing a schema invalidates a previously generated block**, which is a second drift source 1.5's check must catch alongside edits to the source itself
- [x] 1.5 Add the drift check to `gates validate` — fail loudly, naming the command that fixes it, when the generated block no longer matches its source
- [x] 1.6 Verify: `openspec new change <throwaway>` prints **no** "must be an array of strings" warning
- [x] 1.7 Verify: `openspec instructions proposal --change <throwaway> --json` returns a non-empty `rules` array; delete the throwaway change
- [x] 1.8 Verify: rule resolution still resolves every rule-id, and manifest validation still fails loudly on a dangling one
- [x] 1.9 Verify the generator against a throwaway *adopter* project — the source is Specloop's, the target is theirs
- [x] 1.10 Document the rule-id rationale in the conventions source (D4a): citable findings, per-surface selection, detectable dangling refs, one source rendered for two consumers
- [x] 1.11 Reconcile the workaround this defect already produces in the field. Observed live during `unfork-commands` task 7.1: run against a real adopter project, `/specloop:harness-init` hit the unresolvable `conventions` rule-id, correctly declined to edit the project's existing `openspec/config.yaml`, and wrote a **second** conventions source (`docs/specloop-conventions.md`) with `### <id>` anchors distilled from it. That is onboarding routing around the very defect this section fixes, and it creates exactly the duplicated source of truth D4a argues against. Decide whether onboarding should generate the conventions source by design once 1.1's path is chosen — and if so, this is that behaviour's specification, not an accident
- [x] 1.12 Reconcile with `harden-manifest-parser`, which has **landed** and changed the ground here. The starter template used to reference the same undefined `conventions` rule-id (so `harness validate` failed on a freshly dropped template); it now defaults to a single **inline prose** rule, which needs no rules-doc and is why it validates as shipped, with the rule-id + `rules-doc` form demoted to commented guidance. Once this change gives the plugin a real conventions source, decide whether the template should point new adopters back at the rule-id form — and do not simply restore `rules-doc: openspec/config.yaml`, which is the exact reference that was broken

- [x] 1.13 Make onboarding report the gate it just bound. Observed live: `/specloop:harness-init` bound `ci: "just ci"` in a real project and reported success — `harness validate` passed, so its stated goal was met — but that gate was **already red** in that project (a BDD recipe missing its codegen step, so the suite found no tests). A required gate that is red at bind time means `tdd-apply` can never commit a single task: the loop correctly refuses, and the user sees an unexplained no-op with nothing connecting cause to effect. After writing the manifest, run `ci` once and report its exit code. Do **not** make a red gate an onboarding failure — binding a gate the project cannot yet pass is legitimate and common, and is often exactly why someone is adopting a harness. The defect is the silence, not the red

## 2. Record approval in change metadata

- [x] 2.1 Document the `.openspec.yaml` approval keys (`approved_by`, `approved_at`, `approved_sha`) in `SETUP.md`, including what `approved_sha` is computed over
- [x] 2.2 Re-verify against the current OpenSpec version that the extra keys pass `openspec validate --strict` and leave `status --json` / `instructions --json` unaffected
- [x] 2.3 State explicitly that `tasks.md` is derived from the other artifacts and is not separately approved
- [x] 2.4 Cross-reference `harden-unattended-loop` as the change that populates and enforces these keys — this change only defines them

## 3. State the boundary in the manifests

- [x] 3.1 Rewrite `description` in `.claude-plugin/plugin.json` around closing the loop + "bring your own schema, bring your own stack"
- [x] 3.2 Mirror it in the `plugins[]` entry of `.claude-plugin/marketplace.json`; keep `name`, `version`, `category`, `keywords` consistent
- [x] 3.3 Verify `claude plugin validate .` still passes

## 4. Restructure the reader-facing docs

- [x] 4.1 `README.md`: lead with what Specloop closes; add the three-owner split (upstream / project / Specloop)
- [x] 4.2 `README.md`: justify OpenSpec as a prerequisite by naming the four things the loop consumes and what breaks without each
- [x] 4.3 `README.md`/`SETUP.md`: present onboarding as an owned surface beside enforcement (D9), not as a mitigation
- [x] 4.4 `SETUP.md`: make the two adopter inputs explicit and ordered — select a schema, then write the gate manifest
- [x] 4.5 `SETUP.md`: give the brownfield path an ordered sequence from unconfigured project to first passing gate, with a named command per step
- [x] 4.6 `SETUP.md`: state that schemas are selected per change via `.openspec.yaml`, and that installed schemas have no upstream update path
- [x] 4.7 Remove any wording in either doc implying Specloop authors proposals, specs, designs, or workflow shapes

## 4b. Position on the ladder (D3, D10)

- [x] 4b.1 `README.md`: state the 0–4 rungs before using them, then the three levels, then "Specloop is the advanced rung, prefabricated"
- [x] 4b.2 `README.md`: name the two owned jobs as **climb** and **close**, and map each shipped component to the advanced-level need it satisfies
- [x] 4b.3 State the limit in the same place as the claim — Requirements never moves, System design stops at `act`; four phases close, not six
- [x] 4b.4 Define gate / oracle / hook where the gate contract is introduced in `SETUP.md`, and say why the contract is an exit code and nothing else
- [x] 4b.5 Use "oracle" consistently wherever the docs currently say "the exit code" as a standalone concept
- [x] 4b.6 Relate the rung ladder to the six-stage organisational ladder in the memo rather than presenting two unconnected scales

## 5. Record the rejection test

- [x] 5.1 Add the four-question scope test to the conventions source as a stable, citable rule
- [x] 5.2 Include the forked-commands case as the worked example — the test's first real application, and one it got right against interest
- [x] 5.3 Record the single question the four are instances of: does it move a phase from `act` to `close`, or move a team up a rung faster?
- [x] 5.4 Cross-reference it from `README.md` (contributing/scope) so a proposal author meets it before writing

## 6. Land the memo and close out

- [x] 6.1 Add `docs/specloop-map.html` (two-axis model, two gate families, ladder scoring, errata)
- [x] 6.2 Link the memo from `README.md` as the reasoning behind the boundary
- [x] 6.3 Add the errata entry for the adoption talk — found late, and it reframed the positioning
- [x] 6.4 Re-read all changed docs against the rejection test; fix any surviving claim to upstream's or the project's work
- [x] 6.5 Confirm the loop is untouched: `git diff --name-only` touches no `skills/`, `agents/` or `hooks/` path, and the only `bin/` change is conventions generation and its drift check
