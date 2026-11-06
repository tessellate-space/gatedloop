# Design

## Context

See proposal.md, Why. These facts in the shim shape the approach:

- **Neither the brief nor the handoff checks approval.** `_render_tests_brief` reads only the change directory. `_tests_handoff` reads `x-gatedloop-approved-by` only to copy it into the row (`_read_approved_by`), and never refuses on it. Approval is enforced at `check-implement` and at the merge. So a preflight on an unapproved plan needs no approval bypass.
- **The handoff has one check that is wrong for a plan under amendment.** `_oracle_handoff_problems` starts with `_oracle_drift_problems`, which compares each task's tag in the working tree with the merge target's `tasks.md` (task-oracle D9). For a new plan the change is not on the target and the check is a no-op. For an amendment to a plan that is already merged, though, every retag would be refused, and the retag is the whole point of the amendment.
- **A real handoff writes in two places.** It appends a ledger row, and `_hash_blob` runs `git hash-object -w` for every held file and every base.
- **The holding area is tracked by design** (split-test-author D3): it is committed in the authoring commit on the change branch. `gates tests check` resolves the change from the branch (`_resolve_change_name`). On `plan/*`, on the target and on any branch that names no change, it prints "no change branch checked out, nothing to check" and passes. Nothing stops held files from riding along on a plan branch.
- **`gates tests show` reads only the ledger** (`_tests_show_doc` folds `_authoring_state(rows)`). With no handoff recorded, it says the tests are not authored yet.
- **`.gatedloop/out/` already ignores itself.** `_run_gate_captured` writes a nested `.gitignore` containing `*`, and `_rotate_out_logs` only removes `<gate>-*.log`.
- **A ledger already exists before implementation.** `_record_merged_plan` and `approval attest` append an approval row to `.gatedloop/runs/<change>.jsonl` on the target, and `discipline check-commit` already allows a planning-grade commit with ledger paths ("with N ledger path(s)"). So plan-time rows on a plan branch follow an existing route.
- **The approval digest does not cover task prose.** `_approval_sha_worktree` hashes `proposal.md`, `design.md`, the spec files and only the oracle tags of `tasks.md` (`_update_with_oracle_tags`), so that ticking a box never voids an approval. A task's wording, which is the test author's main input, is not in it.
- **Built-in rules resolve from the plugin, not the project.** `BUILTIN_RULES_FILE` is `rules/loop-rules.md` beside `bin/`. `_builtin_rules_error` fails loud when the file or a listed `### <id>` heading is missing.
- **`_mini_yaml` reads nested mappings** (the `economics.prices` shape is three levels deep), and it reads a scalar `loop.plan-preflight: run` as the string `"run"`. A scalar-or-mapping key is within what both parsers read alike. `on`/`off` are not: PyYAML reads `on` as `True`, while `_scalar` turns only `true`/`false` into booleans.
- **`review-provenance`** (in flight) writes `review` and `review-provenance` rows, writes nothing on a `plan/*` branch, and narrows the convention reviewer's Bash to `git diff|show|log|status`, `gates rules` and `gates tests show`, with any flags.
- **The oracle-tag grammar has no deletion clause.** test-rewrites D1 rejected `removes:` and parked it in `docs/candidates.md`.

## How it connects end to end

```
/gatedloop:propose (planner or not), on plan/<change>, after /opsx:propose authors
  gates plan check <change>                         ← always; free; deterministic
  under loop.plan-preflight: run
    gates plan tier <change>                        ← floor + signals; runs a declared classifier
      light floor, no valid classifier verdict: plan-review --lens gatedloop.blast-radius
        gates plan classify <change> --verdict <json>   ← validated against schema/plan-tier.schema.json
      effective tier = max(floor, classifier), then any Plan tier line or --tier full
    loop (round budget: full = loop.plan-preflight.rounds, default 3; light = 1):
      gates plan round <change> [--tier full]       ← static checks; opens round N or refuses (stalled)
      plan-review × each lens of the tier           ← light: implementability; full: + zero-decision
        gates plan brief <change> --lens <id>
        gates plan record <change> --checker lens:<id> --verdict … --report …
      full only, when every lens was clean:
        test-author (preflight mode)
          gates tests brief <change> --preflight    ← names the stale tasks; reuses the rest
          gates tests handoff <change> --dry-run    ← same refusals; no row, no object
        gates plan record <change> --checker dry-run          ← the shim runs it and records the exit
        convention-review (authored-set) over gates tests show <change> --preflight [--diff]
        gates plan record <change> --checker authored-review --verdict …
      green → exit;  question → record, exit;  findings → planner amends → next round
  gates plan status <change> --markdown → PR body;  git add openspec/changes/<change> .gatedloop/runs/<change>.jsonl
  gates run ci → commit → push → PR (a draft unless the loop ended green)
… a human answers a question or reviews the PR → amend → gates plan resume <change> --reason … → loop …
… approval, merge of the plan …
/gatedloop:planner step 4: gates plan check <change> --against <target> → gates handoff
… the real test author runs on the change branch, as today …
```

## Goals / Non-Goals

**Goals:** the test author's and the handoff's objections, and two fresh reads of the plan, reach the planner before approval. Planning ends in a verdict: green, a recorded question, or stalled. Depth follows blast radius, and the shim decides it. Output carries across rounds. The approver sees which checks ran on which content. Drift is visible at handoff. Preflight output cannot reach a commit.

**Non-Goals:**
- moving any guarantee: approval, attestation, `gates handoff`, the real `gates tests handoff`, the lock and `gates merge` are unchanged, and no plan-loop row is read by any of them;
- handing the loop's tests off after approval (change #3, `approved-tests`);
- per-surface lenses bound in the manifest (change #2, `plan-review-lenses`);
- running any gate in a preflight;
- a deletion clause in the tag grammar;
- making the orchestrator re-check drift (it already verifies each payload);
- pairing with, or naming, any external design-review tool.

## Decisions

### D1. The preflight is a convergent plan loop, and judging a plan is now ours

The maintainer's direction, recorded here: the preflight is not an advisory check whose output is discarded. It is a loop that the planner runs before the plan PR asks for approval, and it converges on a verdict. The planner is the deep-context agent: it wrote the plan and knows why each line is there. The checkers are fresh-context agents: each reads the plan cold, through one lens, and has none of the planner's reasons to forgive a gap. This is the split implementation already uses, where the implementer holds the context and the convention review and test author read cold.

gatedloop builds this loop and its plan-review agent itself. It does not pair with, depend on, or name any external design-review tool. A shipped prompt naming one would bind adopters to a tool choice, in the spirit of `stack-agnostic-prompts`.

This deliberately revises the boundary recorded in `docs/candidates.md` ("Pair with an upstream design reviewer"), which held that judging a design is not ours. Under the single question of the rejection test, judging a plan before approval moves the planning phase from `act` (a human reads it) to `close` (a verdict the loop reads back). The evidence is tessellate's 20 of 24 plan PRs amended after approval. The boundary that stays: authoring an artifact is still not ours. The loop never writes a plan. It returns findings, and the planner amends through its own authoring flow. The candidates entry is rewritten to say so (task 8.2).

### D2. Names: `gates plan …`, `gates tests handoff --dry-run`, and the `--preflight` flags

`plan` is a top-level noun beside `approval` and `handoff`, for operations on a plan's artifacts that are neither approval nor tests. Its verbs are `check`, `tier`, `digest`, `classify`, `brief`, `round`, `record`, `resume` and `status`. `check` and `--dry-run` were promised provisionally to an adopter's planner, and nothing found argues against them.

`gates validate` was considered as the home of `check`. It already reports oracle-tag problems, but it runs in `ci` on the target for every active change. A check that fails one change's plan there would break every other change's `ci` (the same reasoning as test-rewrites D1). `plan check` is per change and is run by the planner, so it can fail.

`tests brief --preflight` and `tests show --preflight` are named after the area they read, not `--held`, because they read the preflight store and not the tracked holding area.

### D3. The tier: a floor computed in code, a classifier that may only raise it, and overrides that are never silent

A small change should not pay for the whole loop. The depth must not be the agent's choice, though, for the same reason the hot set is computed in `bin/gates`: an agent under budget pressure must not be able to quietly pick the cheap path. So the tier has three layers, and the shim combines them. `gates plan tier <change> [--json]` prints every layer, and `gates plan check --json` carries the same object as `tier`. `gates plan round` records it.

**Two tiers.**
- **light:** `gates plan check` plus one plan-review run through `gatedloop.implementability`. It is a single pass with a budget of one round: findings go to the planner, who amends, and the lens is not run again.
- **full:** the whole loop. Every lens runs, then the test author in preflight mode, the dry run and the authored-set review, with the three exits (D4) and the round budget.

A middle tier (for example, full without the test author) was considered and rejected for now. Most of the field defects that only the author's run catches are the tag, characterization and rewrite refusals (#110 #112 #122 #123 #128 #130). Those concentrate in exactly the changes that a full floor already selects: changes that modify existing behaviour, or that span several surfaces. A third tier would add a threshold to calibrate without evidence that it catches anything the other two miss.

**Layer 1: the floor, computed in code.** The floor is `full` when any one signal is high, and `light` otherwise:
1. **Tasks:** the number of task lines in `tasks.md` is at least `full-at.tasks` (default 20). This is a size backstop, not a risk signal (see "Calibration" below).
2. **Named files:** the number of repository paths the plan names is at least `full-at.files` (default 12). The paths come from `_named_paths` over the proposal, the design and the task lines, excluding the change's own directory.
3. **Surfaces:** the number of surfaces hot for those paths (`hot_surfaces`) is at least `full-at.surfaces` (default 2).
4. **Existing requirements:** a spec delta of the change has a `## MODIFIED Requirements`, `## REMOVED Requirements` or `## RENAMED Requirements` section.
5. **Costly oracle (adopter-declared, off by default):** any task's oracle tag names a gate listed in `full-at.oracles` (default: empty), or, when that list is non-empty, carries a `rewrites:` clause. Gate names are the adopter's, so the shim cannot know which gate is an end-to-end one; the adopter lists its costly gates (for example `full-at.oracles: [e2e]`). Read from the tags the plan already has, so it is deterministic and free.
6. **High blast radius:** a hot surface (as in 3) declares `blast-radius: high`. This is also how a **public contract** reaches the floor. What counts as a project's public contract is the adopter's to say, so the adopter marks the surface that covers it. This repository marks a `contract` surface over `tests/contract.json`, `docs/stability.md` and `schema/**` (task 4.3).

**Reach is left out.** Counting how many modules import a named file would need each language's import syntax. That is a stack fact, so by the rejection test it is not the shim's. A project that wants reach can bind it through the classifier slot below.

**Calibration (recorded 2026-11-06).** The maintainer judged a task floor of 8 too low, and the field data agrees:

| | gatedloop (67 archived changes) | tessellate-space (266 changes) |
|---|---|---|
| median tasks | 10 | 8 |
| p75 | 17 | 13 |
| p90 | 27 | 20 |
| share at 8 or more tasks | 64 % | 55 % |

A floor of 8 would have sent most changes to `full`. Task count also barely predicts which plans fail. tessellate-space's amendment-after-approval rate by task count (from `amend <change>` commit subjects, which undercount the history before November):

| tasks | 1–3 | 4–7 | 8–11 | 12–15 | 16–23 | 24+ |
|---|---|---|---|---|---|---|
| changes | 30 | 91 | 65 | 33 | 26 | 21 |
| amended | 20 % | 5 % | 13 % | 6 % | 15 % | 14 % |

The smallest plans are amended most often, and their failures were end-to-end and test mechanics (`staged-edits-are-visible`: 4 tasks, 3 amendments), not size. So task count is demoted to a size backstop at roughly the p90 (20).

Three oracle signals were then tested on the 33 tessellate-space changes whose tasks carried oracle tags at approval (the other 233 predate tags and are excluded; 17 of the 33 were amended):

| signal | amended, fired | not amended, fired |
|---|---|---|
| any gate other than `unit` | 11/17 (65 %) | 9/16 (56 %) |
| `rewrites:` alone | 3/17 | 5/16 |
| `rewrites:` or the project's `e2e` gate | 10/17 (59 %) | 9/16 (56 %) |

Read naively, none separates. But 7 of the 9 "not amended" hits for the last signal are plans never implemented, so "not amended" there means "not yet tested". Counting only implemented plans (n = 23), it fired on 7 of 14 amended plans (50 %) and on 2 of 9 that ran clean (22 %): about twice as often on amended plans, though it catches only half of them. The amended ones it caught include the costliest (`staged-edits-are-visible` and `workbench-modes-and-outline`, three amendments each). That is suggestive at a tiny n, not proof. So "any non-unit gate" is rejected as a default (it would send about 61 % of plans to `full` for no separation), and the end-to-end form ships as signal 5, **opt-in and empty by default**: an adopter declares its costly gates, and the round rows (D5) record every signal so a later change can calibrate it on real outcomes.

**Why these defaults.** Twelve named files, or two surfaces, is where a plan's claims about the code span parts of the tree that the planner did not write together. Changing an existing requirement means existing tests pin the old behaviour, so the plan needs `rewrites:` clauses and `characterization` tags: that is the family of handoff refusals in the field report. Blast radius is the adopter's own word for "important", so the shim does not guess it. A one-surface, additive change of up to nineteen tasks, with no costly oracle the adopter declared, gets a light floor, and its likeliest defect, a wrong claim about the code (#114 to #127), is the implementability lens's job. The thresholds are not calibrated on field data. That is why they are overridable, and why every round records its signals, so a later change can calibrate them from the rows.

**Layer 2: a classifier, which may only raise the tier.** A cheap judgement reads the plan digest and answers a set of narrow blast-radius questions. The shim combines the answers into `light` or `full`. It catches what no count sees: a two-task change to a data format other systems read, say. **The effective tier is max(floor, classifier).** The classifier can raise the tier and can never lower it, so whatever the classifier does, or fails to do, can only cost usage and never safety. That includes a fallback, a crash or a missing verdict.

The contract is typed answers, not prose, and has one shape for two providers. It is shaped to fit a classifier that answers typed questions (a choice among options, a probability, a score on ordered levels), returns a confidence for each, and returns no free text. A model that can write prose can always fill this shape. A typed-answer model could not fill a prose contract.

- **Dimensions, not one tier question.** Blast radius is asked as several narrow questions. They live in a shipped data file, `rules/plan-tier-dimensions.json`, never in a prompt. Each dimension has an `id`, a `kind` (`probability` 0 to 1, `choice` among listed options, or `score` on ordered levels 1 to 10), the question text, and its raise threshold. The built-in set:
  - `security-path` (probability), "changes an authentication, authorization or security path", raises at 0.5;
  - `persisted-data` (probability), "changes persisted data or its format", raises at 0.5;
  - `public-interface` (probability), "changes an interface other code or other systems call or read", raises at 0.5;
  - `irreversible` (probability), "performs or enables an operation that cannot be undone", raises at 0.5;
  - `overall-tier` (choice of `light` or `full`), raises on `full`.

  `loop.plan-preflight.dimensions` may override a dimension's threshold, or turn a built-in dimension off with `off`. Adding a dimension of one's own waits for `plan-review-lenses`. The same dimensions feed the built-in lens, so the two providers produce comparable evidence.
- **Input** (JSON on stdin): `{digest, dimensions}`. `digest` is the plan digest, a bounded summary that the shim builds deterministically: no prompt builds it, and no classifier receives whole artifacts (see "The digest" below). `dimensions` is the effective dimension list.
- **Output** (JSON on stdout), validated against `schema/plan-tier.schema.json`: `{"tier": "light"|"full", "confidence": <number 0..1>|null, "evidence": [{"dimension": <id>, "value": <number|bool|string>, "confidence": <number 0..1>|null}], "reason": <string>|null}`. `reason` is optional, because a typed-answer classifier cannot produce one. The built-in lens fills it.
- **The shim combines the answers deterministically.** The classifier's verdict is `full` when its `tier` is `full`, or when any evidence item for a known, enabled dimension meets that dimension's threshold. Otherwise it is `light`. An evidence item naming an unknown dimension is recorded and ignored. Each confidence is recorded with its answer. A low confidence never lowers anything, because the classifier only raises: confidences are evidence for the approver and for later calibration.
- **Providers.** An **external classifier**, which the adopter binds, or the **built-in lens** `gatedloop.blast-radius`, which the plan-review agent runs as one short read and which answers the same dimensions in the same JSON. No shipped prompt, data file or code names any vendor or model (`stack-agnostic-prompts`, Axis A).

**The binding is `loop.plan-preflight.classifier: <command>`, not a gate.** A gate's contract is its exit code and nothing else: an oracle is a machine-readable verdict read back as a status. The gate machinery around it (markers on a tree, `gate` ledger rows, surface-scoped overrides, `gates run`'s logs) assumes that. A classifier's verdict is the JSON on its stdout, and its exit code only says whether it produced one. Declaring it as a `gates.plan-classify` gate would give the gate contract a second meaning, and let it be scoped per surface, which a whole-plan classifier cannot use. So it is a command under the key that owns the loop, with `classifier-timeout` (seconds, default 60). The shim runs it with the input on stdin, in the repository root, and reads stdout.

**The shim ships no vendor client. The command is the adopter's adapter.** A typed-answer classifier is reached over an HTTP API, with a key, retries and a request shape of its own. Shipping a client for it would name a vendor and need a third-party or networking dependency (`zero-dep-shim`, `stack-agnostic-prompts`). So the adopter's `classifier` command is an adapter. It reads `{digest, dimensions}` on stdin, loads its own API key from its own environment or `.env`, builds the provider's request (for a typed-answer model: the digest as the state, each dimension as a typed question), retries rate-limit and overload responses with backoff, maps the answers back to the contract, and prints the contract JSON. SETUP.md gives such an adapter as a documented example, with the key's variable, the endpoint, retries and a gitignored `.env`. It is never shipped as plugin code.

**Secrets stay with the adapter.** The shim never reads `.env` or any secret. It passes its own environment through to the command unchanged, never prints or records that environment, and records only the command's exit, duration and validated stdout. The command's stderr is captured to `.gatedloop/out/plan-classifier-<ts>.log`, as gate output is, which `.gatedloop/out/` ignores. The residual risk is an adapter that echoes its key to stderr, which would put the key in that ignored log. SETUP.md tells adapter authors never to print the key or the request headers.

**Data leaves the machine, and the adopter is told so.** An external classifier sends the plan digest (file paths, requirement titles, task lines, decision headings) to a third party. Declaring a classifier is therefore an informed opt-in: the `plan-preflight` adoption question and SETUP.md's classifier section both say so explicitly. The built-in lens sends nothing beyond the Claude session the plan is already in.

**Timeout.** `classifier-timeout` defaults to 60 seconds. That is well above a typical client's per-call timeout (the field example's SDK uses 10 seconds) plus a few retries with backoff. On a timeout, the shim kills the command, falls back to the built-in lens, and records the cause `timeout 60s`.

**The digest.** An external classifier may have a small context window, so `bin/gates` builds its input as a bounded digest, in this priority order:
1. the computed signals and the floor;
2. the named paths, each with its hot surface and `blast-radius`;
3. the spec delta headers: each `## ADDED|MODIFIED|REMOVED|RENAMED Requirements` section with its requirement titles;
4. the task lines, without their oracle tags or checkboxes;
5. the proposal's "What Changes" bullets (first lines only);
6. the design's decision headings (`### D<n>. …`).

It is JSON, `{change, floor, signals, paths, spec_deltas, tasks, what_changes, decisions, trimmed}`, measured as the byte length of its compact UTF-8 serialization. `gates plan digest <change> [--json] [--limit N]` prints exactly what a classifier is given, so a person can see what it saw. The record stores the digest's hash, so the printed digest can be matched to a round.

**The adopter declares the limit.** `loop.plan-preflight.classifier-input-limit` is in bytes, with a default of 48000. The shim is stdlib-only and has no tokenizer, so SETUP.md gives a conservative rule: count 2.5 bytes per token. Plan digests are dense with paths and identifiers, which split into more tokens than prose does. A typed-answer classifier counts its context per question, as the state plus that one question, and the field example allows 32k tokens per question and 64k per request. By that rule, 48000 bytes is at most about 19k tokens of state, which leaves headroom under 32k for each question and keeps the whole request under 64k with the five built-in dimensions. A limit for another provider is its per-question window in tokens × 2.5 × 0.6. When the digest is over the limit, the shim trims from the bottom of the priority list: decisions first, then the "What Changes" bullets, then task lines, each from its last entry up. `trimmed` names each trimmed section and how many entries it lost, and the round row records it. No provider's long-context mode is assumed or recommended: those modes are documented as slower and less accurate, and a plan that needs one is `full` anyway (below).

**Over the limit after trimming, the tier is full and no call is made.** If items 1 to 3 alone do not fit, the plan is too large to classify cheaply, and that is itself a blast-radius signal. The effective tier is `full`, and the record says `classifier: skipped, cause: digest over limit`. This is sound because of raise-only: the most a classifier could ever do is raise the tier to `full`, so skipping the call and taking `full` gives the answer the call could at most have given. No fallback to the built-in lens runs, because its verdict could not change a full tier.

**The built-in lens reads the same digest.** `gates plan brief --lens gatedloop.blast-radius` prints `gates plan digest` with no limit: one contract for both providers. The lens has room, so it may also read the artifacts in full, and its prompt says so. The limit applies only to an external classifier.

**Chunking is left out.** Splitting items 4 to 6 across several calls that each carry items 1 to 3, and taking the highest tier any chunk returns, would also be sound under raise-only. It needs a chunk plan, a verdict merge, and a record of several calls per round. Trimming plus the over-limit rule already make every case safe, so chunking is a follow-up.

**Fallback is visible, never silent.** The built-in lens runs instead when no classifier is declared, or when the declared command exits non-zero, times out, or returns output that is not JSON or fails the schema. `gates plan tier` then prints `classifier: builtin` and the cause (`none-declared`, `exit 127`, `timeout 60s`, or `invalid: <first schema error>`). The planner dispatches the plan-review agent with `--lens gatedloop.blast-radius`, and passes its JSON to `gates plan classify <change> --verdict <file>`. The shim validates that against the same schema and keeps it in the preflight store, keyed on the plan digest. If the built-in output is invalid too, `plan classify` exits 1 naming the schema error, and the planner re-dispatches. `gates plan classify <change> --unavailable <cause>` records that no verdict could be had, and the effective tier is then the floor. Every round row records which provider ran, the fallback cause if any, and the verdict with its reason and evidence.

**When the classifier runs.** A declared external classifier runs on every `gates plan tier` and `gates plan round`, unless its digest is over the limit after trimming. It is cheap, and its verdict on a full floor is still worth recording, to calibrate the floor. The built-in lens runs only when the floor is light, because a verdict on a full floor cannot change the tier and the lens costs usage. `gates plan round` refuses to open a round on a light floor until it has a classifier verdict, or a recorded `--unavailable` cause, for the current plan digest. So the cheap path cannot be reached by skipping the classifier.

**Layer 3: overrides, never silent.**
- **Raising** is free and needs no reason. `gates plan round --tier full` raises the tier for that round. A line `Plan tier: full` in `proposal.md` or `design.md` raises it for every round. A human raises it the same way, or asks the planner to.
- **Lowering** is possible only from the plan, with a line `Plan tier: light — <reason>` in `proposal.md` or `design.md`. Both files are covered by the approval digest, so the approver reads the reason and the approval pins it. The line lowers the effective tier to light, whatever raised it: the floor or the classifier. A `Plan tier: light` line with no reason is a `gates plan check` finding, and `gates plan round` refuses to open a round while it stands. No flag lowers the tier.
- Every `plan-round` row records the signals, the floor, the classifier's provider, cause, verdict, reason and evidence, the override with its source (`raised-flag`, `raised-plan` or `lowered-plan`) and reason, and the effective tier. `gates plan status` prints all of them, so the PR body shows them to the approver.

**Known gap.** Signals 2, 3 and 5 read the paths the plan names, so a plan that names fewer paths computes a lower floor. Signals 1 and 4 do not depend on naming. The classifier reads the plan itself, and the implementability lens treats a task that changes code without naming it as a finding (D6, check 1). The gap is stated in SETUP, not claimed away.

### D4. Exits and the round budget, counted by the shim from ledger rows

The loop exits in one of three ways, each computed by `gates plan status` from the rows and never declared by the agent:
- **green:** the latest round has a `clean` verdict, on that round's digest, from every checker its tier runs. Only implementation remains.
- **question:** a checker's finding is one only a human can answer: a product choice, or a trade-off the specs do not settle. The planner records it with `--verdict question` and a report that states the question and its options. The loop stops, and the PR opens as a draft with the question at the top of its body.
- **stalled:** the planner asks for another round when the loop has already spent its budget. `gates plan round` appends a `plan-round` row with `outcome: stalled`, exits 1 and says so. The PR opens as a draft with the status.

The budget is the number of rounds in the current loop: `loop.plan-preflight.rounds` (default 3) under full, and 1 under light. It is counted from `plan-round` rows exactly as `_attempt_state` counts attempts from ledger rows, so a prompt cannot miscount it. A round is opened only by `gates plan round`, and only on a plan that passes `gates plan check`. Static findings are free and deterministic, so they cost no round. The planner amends and runs `gates plan round` again.

`gates plan resume <change> --reason <text>` starts a new loop with a fresh budget after a human has answered a question, reviewed the PR or decided to continue past a stall. It is the analogue of `_attempt_restart`. It requires a reason, and the row records it. It does not need a human's hand, because the rows are record-only, but every resume is listed in the PR body's status, so a loop that was resumed five times shows that it was.

Default 3: one round usually surfaces the lens findings, a second the author's and the review's, and a third confirms the amendments. A plan that still has findings after three rounds has a problem the planner cannot see, which is what a human is for.

### D5. Provenance: `plan-round` and `plan-review` rows in the change's ledger, committed on the plan branch

The record of which checkers ran, on which content and with which verdict goes in the change's own ledger, `.gatedloop/runs/<change>.jsonl`. The planner commits it with the plan on `plan/<change>`, and it reaches the target with the plan's merge. That is the route the approval row already takes (Context). The PR body is not the record: it is rendered from the rows by `gates plan status <change> --markdown`, so the record survives a lost or edited PR body. The record is in git, where the planner rebuilds its state from ("If unsure").

Two new row kinds:
- `plan-round`: `{loop, round, plan_sha, tasks_sha, signals, floor, classifier: {provider, cause, tier, confidence, reason, evidence, combined, trimmed, digest_sha}, override: {source, reason}, tier, outcome}`, where `provider` is `external`, `builtin` or `none`, `tier` is the effective tier, and `outcome` is `open`, `stalled` or `resume` (with its reason). The new fields are ledger row fields, so `tests/contract.json` records them (`docs/stability.md`).
- `plan-review`: `{loop, round, plan_sha, tasks_sha, checker, verdict, report}`. `checker` is `plan-check`, `lens:<lens-id>`, `test-author`, `dry-run` or `authored-review`. `verdict` is `clean`, `findings` or `question`.

**Shim-run checkers are recorded from the shim's own run.** `gates plan round` records the `plan-check` row. `gates plan record --checker dry-run` runs the dry run itself and records its exit, so the planner cannot claim it. LLM checkers (`lens:*`, `test-author`, `authored-review`) are recorded by the planner with `--verdict`, which is a claim, as a review row is before `review-provenance`. `gates plan record` refuses a row when no round is open, when the plan's digest has changed since the round opened (an amendment means a new round), or when the checker is not one the round's tier runs.

**The content is two digests.** `plan_sha` is the approval digest, `_approval_sha_worktree`, so the approver can compare the green round's content with what they are approving, and `gates plan status` says when the plan changed after its last green round. `tasks_sha` hashes the task lines without their checkbox state. The approval digest leaves task prose out by design, and task prose is what the author writes tests from. A round's identity is the pair.

**No collision with `review-provenance`.** The kinds are distinct from `review` and `review-provenance`. `review-provenance`'s `loop.review: isolated` check reads only `review` rows, and its `SubagentStop` hook writes nothing on a `plan/*` branch. So the authored-set review the planner dispatches leaves no provenance row, and none is expected. Its merge check never sees a plan-loop row.

**Record-only.** Nothing in `gates approval`, `gates handoff`, `gates tests handoff`, `gates merge`, `check-implement` or `gates stats --outcomes` reads these rows. A task (6.3) pins that a ledger holding them gives the same verdicts as one without them, including usage attribution and attempt counting.

### D6. `agents/plan-review.md` and the lens mechanism

A new agent rather than a mode of convention review. Convention review's unit is a diff and its scope discipline is "only the diff". A plan review's unit is a plan, and it must read code that no diff touches. One prompt with two opposite scope rules would weaken both.

**The agent** (Opus, `tools: Read, Grep, Glob, Bash`, Bash for `gates plan brief` only). The other shipped reviewers run on Sonnet because they run once per task and judge a diff against named rules. A plan review runs a few times per plan, reads code that no diff touches, and must notice what the plan does not say, such as an assumed interface or a task order that only fails three tasks later. A miss costs a halted lane, a plan amendment and a second approval, which is the cost this change exists to remove. `agents/schema-review.md` already runs on Opus, so the plugin has the precedent. Per run it:
1. runs `gates plan brief <change> --lens <lens-id>`, which prints the lens's checks (resolved from the path it names), the plan's artifact paths, and each path the plan names with whether it exists at `HEAD`;
2. reads the plan's artifacts;
3. reads only the files the brief names, and only the parts it needs to judge a specific check;
4. reports findings, each as `<lens-id> #<n>` — the task or artifact line — what is wrong — the amendment in one line. A finding it holds to be a human's decision is marked `question`, with the options.

It never edits anything, and never runs any other command. It aims for under 15 tool calls, because it reads code as well as the plan. It is stack-agnostic: it names `gates …` and lens ids only (`stack-agnostic-prompts`).

**One lens returns JSON, not findings.** `gatedloop.blast-radius` is the built-in tier classifier (D3). Run through it, the agent reads what `gates plan brief --lens gatedloop.blast-radius` prints: the digest and the effective dimensions. It may read the artifacts in full. It answers each dimension with a value and a confidence, gives an overall tier and a one-line reason, and returns only the `schema/plan-tier.schema.json` object. The shim combines the answers (D3), so the lens decides no tier by itself.

**Lenses** live in `rules/plan-lenses.md`, shaped like `rules/loop-rules.md`: one `### <lens-id>` section per lens, with `Applies to: plan`, a `Rule:` line and numbered checks. The ids are prefixed `gatedloop.`, so they cannot collide with an adopter's ids. The file resolves from the plugin (a `BUILTIN_LENSES_FILE` beside `BUILTIN_RULES_FILE`), and the same fail-loud check covers it.

- `gatedloop.implementability`, "the plan is right about the code":
  1. every path, rule id, command, gate name and configuration key the plan names exists at the base, or is created by an earlier task, and says what the plan assumes it says (the tessellate case of grepping for a generated line that the generator never writes); and every task that changes code names the files it changes;
  2. task order is executable: no task's work or oracle needs an artifact that only a later task creates;
  3. a task that deletes or renames a file is not followed by a task, or preceded by a `rewrites:` clause, that still needs it;
  4. every interface a task's tests would target is stated by the design or exists at the base.
- `gatedloop.zero-decision`, "no task leaves a decision to the implementer":
  1. no task leaves a design choice open ("either", "as appropriate", "for example" where the example is the decision, "TBD");
  2. every behaviour change a task makes has a spec scenario;
  3. every task's oracle tag fits its task: a behaviour change is not `none`, a task that can only pass on the tree is `characterization`, and a change to behaviour an existing test pins declares `rewrites:`;
  4. every design decision a task relies on is stated in `design.md`, not only implied by the task line.

**Extensible by construction.** A lens is an id plus its rules. `gates plan brief <change>` with no `--lens` lists the lenses that apply, and the tier selects among them (light: implementability; full: both). The agent reads whatever lens the brief names, so the later `plan-review-lenses` change adds lenses bound to surfaces in `.gates.yaml` by extending the selection in `bin/gates`, the way `gates rules` adds a hot surface's rules, and reworks nothing in the agent.

### D7. The preflight store is committed in the change's directory, `openspec/changes/<change>/preflight/`

Preflight output must survive a removed worktree and reach another machine: a planner may resume a plan from another laptop, and an approver reviews on the forge. Four homes were weighed.

- **`.gatedloop/out/preflight/<change>/`** (the earlier design). It is per worktree and ignored, so it dies with the worktree and never leaves the machine. Rejected.
- **The git common dir.** It survives a removed worktree, but it is local to one clone, and it would make the store the one place an agent writes inside `.git/`. Rejected.
- **A dedicated ref** (`refs/gatedloop/preflight/<change>`). It travels only with a custom refspec on every clone and every forge, a PR never shows it, and it needs plumbing (`git hash-object`, `git update-ref`) that the shim does not otherwise use for state. Rejected.
- **The change's own directory, committed on the plan branch.** Kept. A push of `plan/<change>` carries it, so another machine fetches the branch and resumes with the store intact. It is inside the worktree, so the author writes there without leaving its directory. The plan PR shows the held tests beside the plan, so the approver sees what the tests will pin. `/gatedloop:archive` moves it with the change, so the record of what was authored before approval stays with the change. Its paths are under `openspec/`, so a commit of the store is planning-grade (`_is_planning_path`) and needs no ci run, the same as the plan. `openspec validate --strict` and `openspec status` accept an extra directory inside a change; a test pins that on the tested OpenSpec version.

**Layout:** `authored/<N.M>/<path>.authored`, `CHARACTERIZATION` and `NO-TESTS` (the real holding area's layout, suffix included), `digests.json` (per task, the digest of the brief content it was authored from), `classifier.json` (D3, the built-in lens's verdict with the plan digests), and `reports/<loop>.<round>-<checker>.md` (each report passed to `gates plan record --report`). `gates plan check` reports any other path under `preflight/` as a finding.

**A committed test must never run.** The store lands on `main` when the plan PR merges, and its tests are red by design. The `.authored` suffix is what keeps every test runner, linter and type checker from collecting them, in any stack, without the shim naming a tool. `_read_holding_area` already refuses a held file without it. The commit-time guarantee is D8's second refusal.

**When it is committed.** The planner stages the store with each amendment and each round's ledger rows, in the plan commit (D13, D14). An interrupted round leaves the store as the last commit has it, and the next brief's digests say what is stale.

**What the approval covers.** The approval digest (`_approval_sha_worktree`) covers the proposal, the design, `specs/**/*.md` and the oracle tags of `tasks.md`, so it does not cover `preflight/`. That is right for this change, because the store informs the approver and binds nothing: a real handoff still reads only `.gatedloop/authored/<change>/`, and the test author runs again after approval. It is the gap `approved-tests` closes when it makes the held set the handed-off one, and that change must add `preflight/` to the approval digest.

**Reuse across rounds.** `gates tests brief <change> --preflight` computes, for each task, a digest of the brief content that task is authored from: its task line with its tag, its declared rewrites' copies, and the brief's change-wide sections (specs, design, rules and listed interfaces). It compares these digests with `digests.json`. A task is stale when its digest changed or is absent, or when it holds a path that a stale task also holds (§5 of the test author: the later task's copy holds the full file). The brief prints the stale tasks to re-author and the tasks kept from an earlier round, and the author rewrites only the stale ones. A clean `--dry-run` writes the current digests to `digests.json`. The honest effect: an amendment confined to task lines re-authors only those tasks. An amendment to the design, a spec or a rule re-authors every task, because the author reads the whole change for each one. The digests exclude the store itself, so committing the store changes no task's digest.

**Change #3 is not blocked.** `approved-tests` will make the loop's final held set the one that is handed off after approval. The store is on `main` once the plan merges, and `digests.json` says which held tests match the approved content, so #3 can copy a matching set into the change's holding area at handoff, on any machine.

### D8. A backstop at the lock (kept)

`gates tests check` refuses a staged path under `.gatedloop/authored/` whenever `_resolve_change_name` resolves no change: a `plan/*` branch, the merge target, or any other branch that names no active change. Today that path returns 0 with "nothing to check". Both commit hooks (`hooks/gate-commit.sh` and the git-layer `templates/git-hooks/pre-commit`) already run `gates tests check` after `check-commit`, so the refusal holds at both layers with no change to either script and no hook refresh for adopters.

Placing it in `discipline check-commit` was considered and rejected. `check-commit` grades the tree, and the lock is the authored-test check. `gates merge` also calls `check-commit` internally on the target, where a squash's net diff never holds the area, but a future edge case would fail in the wrong place. A ledger-grade commit skips the lock, but it stages only `.gatedloop/runs/**`, so it cannot carry a held file. The backstop catches the other route in: a real holding area populated off a change branch, by hand or by a confused agent.

**A second refusal covers the committed store (D7).** `gates tests check` also refuses, on any branch, a staged file under `openspec/changes/<change>/preflight/authored/` whose name lacks the `.authored` suffix and is not `CHARACTERIZATION` or `NO-TESTS`, naming each path and the name it should have. That is what stops a runnable red test reaching `main` through a plan merge. It rides the same hook call, so no hook script changes.

### D9. `--dry-run` runs every refusal except tag drift (kept)

`--dry-run` reads only the preflight store. It runs:
- `_read_holding_area`'s problems (with the directory as a parameter);
- the empty-area refusal and the `--task` refusal;
- every contradiction in `_oracle_handoff_problems`: tags, `characterization`, `none`, declared rewrites absent at `HEAD` or not held in full, and untagged tasks under `required`;
- the full-handoff "would drop a placed task" check.

It prints the undeclared-overwrite advisory lines. It skips only `_oracle_drift_problems`, and prints one line saying so: on a plan branch, the tasks are the plan being amended, and a real handoff still runs the check. The advisory computes existence with `is_file()` instead of hashing, so no git object is written. It writes no ledger row. Its exit status and messages are the real handoff's, with "Nothing was recorded." On success, it writes the current per-task digests to the store (D7), which is not the ledger. A real handoff keeps reading only `.gatedloop/authored/<change>/`.

### D10. What `gates plan check` can check, and what goes to the checkers (kept, honestly bounded)

`gates plan check` makes the checks the shim can make deterministically:
- this change's oracle-tag errors and warnings (`_task_oracle_problems`, filtered to the change);
- untagged tasks under `loop.task-oracle: required`;
- a `rewrites:` path absent at the base; when an earlier task's line names that path, the finding says the earlier task creates the file;
- a `Plan tier: light` line with no reason (D3);
- a path under the change's `preflight/` outside the store's layout (D7).

These reuse the parser and the messages that the handoff and `validate` already print, so the planner sees now the words it would otherwise see after approval. The issue's three asks, bounded:
- **(a) A `rewrites:` path that a task deletes.** Not mechanically checkable: the plan has no way to declare a deletion (test-rewrites D1), and detecting one from prose is a heuristic, not a fail-loud check. It is now implementability check 3, judged by a reader of the plan. The `removes:` candidate gets this report as evidence, unpromoted.
- **(b) A task whose oracle needs an artifact a later task creates.** Semantic in general: tessellate's #133 names no path the shim could pair. The mechanical part is the rewrite case above. The rest is implementability check 2, and the preflight author's `blocked: weak-spec` naming both tasks.
- **(c) A green-first task without `characterization`.** Statically, a tag is red-first unless it says otherwise. The dry run refuses an author's `CHARACTERIZATION` on a red-first tag. Zero-decision check 3 judges the tag, and preflight mode tells the author to return `weak-spec` when a red-first task's tests can only pass. The complete check (place the held tests in a scratch worktree and run each oracle gate at the base) is rejected for now. It costs a gate run per task per round, needs a scopable oracle gate, and can misjudge a test that an earlier task's implementation would turn red. It goes to `docs/candidates.md` with a promotion condition.

The honest limit stays: the test author reads public interfaces, never bodies, so a plan that misreads an implementation detail is caught by the author only where the interface shows it. The implementability lens closes part of that gap, because it may read the bodies of the files the plan names. It does not close all of it.

### D11. `--against <ref>` is in scope, because it is cheap (kept)

Drift needs nothing new. `_named_paths` already extracts backticked repository paths, and `git diff --name-status <base> <ref>` does the rest. The plan's base is the latest commit in `<ref>`'s history that touches `openspec/changes/<change>/`, when `<ref>` holds the change (the approved plan's merge), and `git merge-base HEAD <ref>` otherwise (a plan branch). With `--against`, existence checks run at `<ref>`, because the change branch is cut from it. A drift finding means "re-read this", not "this is wrong". The planner reads the moved files against the plan, sends the handoff when the plan still holds, and otherwise reports and sends nothing. Tessellate's "drifted while queued" category (#111 #119 #129 #131) is exactly a named file moving underneath an approved plan.

### D12. `loop.plan-preflight`: `run | skip`, scalar or mapping, default `skip`; `gates plan check` always runs

The model part of the loop spends usage, so it is opt-in, following the maintainer rule for new adopter-facing behaviour. Its shape:

```yaml
loop:
  plan-preflight: run          # shorthand for { mode: run }
# or
loop:
  plan-preflight:
    mode: run                  # run | skip
    rounds: 3                  # the full tier's round budget, a positive integer
    full-at:                   # the D3 floor thresholds (positive integers) and costly gates
      tasks: 20
      files: 12
      surfaces: 2
      oracles: []              # gate names whose tags make the floor full, e.g. [e2e]
    classifier: "<command>"    # optional; JSON on stdin, JSON on stdout (D3)
    classifier-timeout: 60     # seconds, a positive integer
    classifier-input-limit: 48000   # bytes of digest JSON, a positive integer (D3)
    dimensions:                # optional overrides of rules/plan-tier-dimensions.json
      persisted-data: 0.3      # a threshold, or `off`
```

Both parsers read both forms alike: `_mini_yaml` already reads nested mappings and scalars, and a test pins each form under PyYAML and `_mini_yaml`. `gates validate` refuses an unknown key in the mapping, a non-positive or boolean integer, any `mode` other than `run` or `skip`, and `mode: run` (or `run`) together with `loop.test-author: inline`. An inline project has chosen not to have a separate author, and a planner that authors tests against its own plan would lose the cold read that makes the loop worth its usage. The values are `run`/`skip`, not `on`/`off`, because PyYAML reads `on` as `True` while `_mini_yaml` reads `"on"`. The same manifest would then mean two things depending on the machine, which is the conditional-path defect `tests/` exists to catch.

Surfaces gain `blast-radius: high | normal`, default `normal`, validated by `gates validate` and the schema. The name says what it measures and not what it triggers, so the later `plan-review-lenses` change can read it too (for example, to run a surface's lenses at full depth), through the same `_plan_hot_surfaces` helper the tier uses.

**Cost, in usage terms.** On a Claude subscription, these runs draw on the plan's included usage. Only a run on an API key is billed per token. Docs that give a dollar figure at all label it "API-equivalent, if you pay per token".
- **skip:** nothing beyond `gates plan check`, which runs no model.
- **The classifier:** a declared external classifier is billed per input token to the adopter's own API key with that provider, outside the Claude session. A dollar figure is accurate there, and docs label it "billed to your classifier's API key" (SETUP.md's example gives its provider's published rate). The built-in `gatedloop.blast-radius` lens is one short plan-review run, only on a light floor, in usage terms like every other Claude run.
- **light:** one plan-review run per plan, single pass, plus the classifier.
- **full:** per round, one plan-review run per lens (two built-in), one test-author run and one authored-set review run, for up to `rounds` rounds. After the first round, the author re-authors only the stale tasks (D7).
- Plan review runs on Opus (D6), so each plan-review run, the built-in classifier lens included, draws more usage than a Sonnet run of the same length. The docs say so next to the tier table.

`gates plan check` runs in the propose path whatever the key says. It costs nothing, records nothing, and reports only what the handoff would refuse after approval anyway.

### D13. Running the loop is the planner's job

The planner's ban on dispatching was a ban on dispatching implementation. The loop needs exactly the dispatches the ban forbade, so this change makes them part of the role rather than an exception, and the role block says so. On its own `plan/<change>` branch, in its own worktree, the planner runs the loop at the computed tier. It dispatches plan review once per lens per round, the test author in preflight mode, and the convention review in authored-set mode. It records each verdict with `gates plan record`, and commits the rows and the preflight store (D7) with the plan.

What stays forbidden is unchanged: an implementer, a merge runner, a test author outside preflight mode, a real `gates tests handoff`, any review verdict or halt recorded for a task, `gates merge`, `/gatedloop:archive`, and working on a change branch or in the orchestrator's checkout. The `command-surface` requirement for the planner role is modified to carry this, with scenarios for the loop's dispatches, the still-forbidden ones, the question exit and drift.

### D14. Prompts

- `commands/propose.md` gains the loop as a step between reading back the change name and committing. It always runs `gates plan check <change>`. Under `run` it reads the tier from `gates plan tier <change> --json` and runs the rounds that tier names, in the order of D15. It puts `gates plan status <change> --markdown` in the PR body, stages the ledger and the preflight store with the plan, and opens the PR as a draft unless the loop ended green (marking it ready when a later loop ends green). If the forge CLI cannot open drafts, it opens the PR normally with the status at the top.
- `commands/planner.md`: the role block and the "Never" list as in D13, the loop as part of step 2, and step 4's `gates plan check <change> --against <target>` before `gates handoff`.
- `agents/test-author.md` gains a "Preflight mode" section. It reads `gates tests brief <change> --preflight`, and writes only to the area it prints, and only for the stale tasks it names. It ends with `gates tests handoff <change> --dry-run` and never runs a real handoff. It returns order problems (naming both tasks) and red-first tags whose tests can only pass as `blocked: weak-spec`, and records nothing. Every other rule (the boundary, the RED questions, the budget) is unchanged, so a preflight objection is the one the real run would raise.
- `agents/convention-review.md`'s authored-set mode reads `gates tests show <change> --preflight` (and `--preflight --diff`) when told it is a preflight, and the held files from the store. Its caller records the verdict with `gates plan record`, never with `gates review record`.
- `agents/plan-review.md` as in D6, including the JSON-only `gatedloop.blast-radius` lens.

All of these name only `gates …`, gate names and lens ids (`stack-agnostic-prompts`).

### D15. Order within a round: cheapest first, and a round stops at the first stage with findings

The stages are: static checks (inside `gates plan round`, free, and costing no round), then the lenses (cheap and independent, so they may be dispatched in parallel), then the test author and the dry run (the costliest run), then the authored-set review. A round with lens findings ends there. The author's run on a plan that is about to change would be the run most likely to be wasted, and its likeliest findings overlap the lenses'. That round's author, dry-run and review checkers are absent from its record, so `gates plan status` shows that the round stopped at the lenses. Within the authored stage, a review finding against a test itself (not the plan) goes back to the author for one revision of that task within the round, as in the real flow. A finding against the plan goes to the planner and ends the round.

## Risks / Trade-offs

- [The loop's checkers miss what the real author later finds] → the real author still runs after approval, so stochastic misses cost what they cost today, and nothing is worse.
- [An LLM verdict recorded by the planner is a claim] → it is record-only, shown to the approver with the content digest, and it never blocks. The shim records the deterministic checkers' rows from its own runs. Extending `review-provenance`'s `SubagentStop` proof to plan review is a follow-up, not a need.
- [A planner lowers its tier, or under-names paths to compute light] → lowering needs a reason in an approval-covered artifact and shows in the status. Under-naming is the known gap of D3, which implementability check 1 narrows.
- [An adapter leaks its key into the captured stderr log] → the shim never handles the key, the log is git-ignored, and SETUP.md tells adapter authors never to print it. The shim cannot stop an adapter that prints it anyway.
- [The plan digest leaves the machine] → only when the adopter declares a classifier, after the adoption question and SETUP.md have said so.
- [An external classifier is wrong, slow or down] → it can only raise the tier, so a wrong `light` changes nothing and a failure falls back visibly to the built-in lens. A wrong `full` costs usage, and the record shows which provider said it, so the adopter can rebind it.
- [The validator and the shipped schema drift apart] → the contract test of task 5.1 runs both over the same fixtures.
- [Repeated `gates plan resume` defeats the budget] → every resume and its reason is in the record and the PR body. The budget makes a stall visible; it does not forbid a human from continuing.
- [Usage per round under full] → opt-in, tiered, and reuse makes later rounds cheaper. A plan PR update that changes only `proposal.md` prose outside a `Plan tier` line runs no new round (the propose step re-runs the loop only when the plan digest or the tasks digest moved).
- [A drift finding on a busy file is noise] → the planner reads it and decides. Findings are advice and never block `gates handoff`.
- [The backstop refuses a commit on `main` that some workflow relies on] → no shipped flow commits held files off a change branch. The suite's fixtures are the check: a fixture that does so is either wrong or names a flow to keep, and either way the implementer reports it.
- [Plan-loop rows on the target confuse a reader of the ledger] → they are distinct kinds that no verdict reads (D5), and task 6.3 pins that.

## Migration Plan

Ships in 0.12.0. `loop.plan-preflight` is unset in every existing manifest, so the propose path changes only by running `gates plan check`. The `plan-preflight` adoption item asks once. The `tests check` backstop changes the verdict only for a staged held file on a branch that names no change, which no shipped flow produces. Rollback: revert the change. An older shim refuses `loop.plan-preflight` as an unknown `loop` key, and `blast-radius` as an unknown surface key, at `gates validate` (fail loud). A project that set either must unset it to downgrade. An older shim reading a ledger with plan-loop rows ignores rows of kinds it does not know, which task 6.3 checks rather than assumes.

## Follow-ups

- **`plan-review-lenses`** (change #2): per-surface lenses declared in `.gates.yaml` beside `rules` and `live-check`, selected in `bin/gates` from the surfaces hot for the plan's named paths. Onboarding (`gates-init`) proposes lenses per surface from the detected stack. It absorbs #30. This change prepares for it: a lens is an id plus rules, `gates plan brief` owns the selection, and `blast-radius` is read through the same hot-surface helper.
- **Chunked classification:** split digest items 4 to 6 across several calls that each carry items 1 to 3, and take the highest tier any chunk returns (sound under raise-only). It waits until a field plan's digest is trimmed often enough that a trimmed section matters.
- **Classifier provenance.** An external classifier's verdict is run by the shim, so it is evidence. The built-in lens's verdict is passed in by the planner, so it is a claim, like the other LLM checkers. Extending `review-provenance`'s `SubagentStop` proof to the plan-review agent would make it evidence too.
- **`approved-tests`** (change #3): the loop's final held set becomes the approved, handed-off tests, so the author does not run twice. D7's committed store and digests are its input, and it adds `preflight/` to the approval digest.
