## Context

The loop's guarantees are prompt text; nothing enforces them (see `AUTOMATION.md`). This change adds an enforcement layer using standard Claude Code hooks. It builds on the shipped plugin (skills/agents/shim/SessionStart brief) from the scaffold change.

Source material is `AUTOMATION.md` at the repo root; this design folds in six corrections found while reviewing it.

Two inputs recorded after this design was written (2026-08-18, `docs/review-2026-08-18.md`):

1. **Prerequisite — `fix-change-scope-selection`.** The field review confirmed by experiment that `gates run live-check` passes vacuously on a clean tree: the changed-set baseline is the working tree, which is empty at change completion, so the hot set is empty and the blocking gate exits 0 without running anything. D1/D2's merge marker would record that vacuous green as a real one. The selection fix (change-level gates baseline = the change's diff against the merge target) must land before the marker is implemented, and the marker must never be satisfiable by a skipped-because-empty run.
2. **The integration process is declared, not assumed.** `onboarding-asks-first` §5 records the project's integration process (local squash-merge / PR / PR + required approvals) in `.gates.yaml`. D10–D12 and the reconciliation of `tdd-apply` §7.5 (which currently hard-codes a local squash-merge) should consume that declaration rather than assuming a single merge model.

## Goals / Non-Goals

**Goals:** make the blocking guarantees (commit-on-green-ci, merge-on-green-live-check, stop-before-merge) hold even with no human watching; keep the loop moving unattended; keep everything plugin-local (no external account / preview feature).

**Non-Goals:** channels, cloud routines, `/loop`, a hard git sandbox, and Specloop's own self-hosting setup (see proposal Non-goals).

## Decisions

### D1: Gate the tool call, not the intention — `PreToolUse` deny + markers
`gates run <gate>` writes a marker on success; a `PreToolUse` hook on `Bash(git commit *)` / `Bash(git merge *)` compares the marker to the current tree and exits 2 (deny) on mismatch. The hook does **not** re-run the gate (full CI under a hook timeout is unusable) — it's an O(1) hash compare. A marker cannot survive an edit, so "never commit on red" becomes an invariant.

### D2: Define "the tree" precisely (correction — the marker's exactness depends on it)
`ci` runs on the working tree, but a commit records the **staged index**, and tdd-apply deliberately stages a *subset* (`git add <specific files>`, never `git add .`). So a naive working-tree hash would false-deny a legitimate partial commit. Decision: the marker records the tree object that will actually be committed — `git write-tree` of the index — and `gates run ci` is defined to run **after staging** and to record that index tree. The commit hook recomputes `git write-tree` and denies unless it matches a fresh marker. Merge uses the branch-head commit's tree. This makes the guarantee exact rather than approximate.

### D3: The `Stop` hook is a `command` hook, guarded against runaway (correction)
Prompt-type hooks exist only for `PreToolUse`/`PostToolUse`/`PermissionRequest`, so the continue-the-loop hook is a **`command`** `Stop` hook: a script that checks (branch is a change branch) ∧ (`tasks.md` has `[ ]`) ∧ (tree clean at a task boundary) and, if all hold, emits a block decision with `reason: "continue from task N.M"`. It **must** read `stop_hook_active` from the hook input and refuse to re-block when set, so it can never infinite-loop. A halted/gate-blocked run fails the condition and does not spin.

### D4: Permissions are opt-in and personal, not silently shared (correction)
`/specloop:gates-init` offers to write permission rules to **`.claude/settings.local.json`** (gitignored, per-developer) — never the committed `.claude/settings.json` — and only with explicit confirmation. A plugin must not silently broaden a repo's permission surface for everyone. Rules: `allow` the loop's vocabulary (`gates *`, `openspec *`, `git commit *`); `ask` on `git merge *` so the pre-merge human checkpoint is enforced even under auto mode.

### D5: Composition — deny hooks win over allow rules
`allow: Bash(git commit *)` (D4) lets commits through the permission prompt; the D1 `PreToolUse` deny still blocks an *ungated* commit. The two compose: permission rules remove friction for the intended path; the marker hook enforces the invariant. (Confirm precedence during implementation — a `PreToolUse` deny must override an allow.)

### D6: Structured report + headless entry point
`tdd-implementer` emits a machine-readable final report (`{change, tasks_done, tasks_total, branch, gates, outcome}`) so headless runs are queryable. Document `claude -p "/specloop:tdd-apply <change>" --permission-mode acceptEdits --output-format stream-json`. In true headless mode the D4 `ask`-on-merge cannot be answered — which is the *desired* outcome: the run cleanly stops before the merge and reports, exactly matching "STOP BEFORE THE MERGE".

### D7: The marker and the ledger are the same moment, not the same store (correction)
An earlier reading of this design treated the D1 marker as "a run record with the outcome deleted — the same write with four more fields." Same *moment* — both happen when `gates run <gate>` finishes — but they want **opposite lifetimes**, and conflating them produces a metrics store that dies with the clone:

| Store | Lives in | Lifetime | Purpose |
|---|---|---|---|
| Marker | `.git/` | ephemeral, per-worktree, never committed | a **lock**: deny the commit unless `ci` passed on this exact tree |
| Ledger | `.specloop/runs/<change>.jsonl` | durable, committed, archived with the change | a **record**: what ran, how long, how many red cycles |

`bin/gates` is the only place where every gate outcome in the system is observable — agents see no gate history, hooks see one gate at a time. Since this change already opens `gates run` to write a marker, the ledger row is written in the same place; it simply lands somewhere that survives.

**Only the row's shape is urgent.** Aggregation, export, and any dashboard are sinks that can be added later without touching a call site — but a row shape that omits a field cannot be reconstructed after the fact.

### D8: Key the ledger on the change, never on the commit
Specloop squash-merges. This repository's own PR specloop PR 1 demonstrated the consequence: it merged as `6d15996`, and the three branch commits are no longer ancestors of `main` — only their content is. An append-only ledger file survives that intact (the squashed commit carries the file's final state and every row in it); what dangles is any SHA a row names.

So rows are keyed on **(change, task)** — durable, human-meaningful identifiers that survive the squash — plus the tree hash, which for the final task equals the squashed commit's tree when `main` has not moved, giving a verifiable join back into history. A single row is appended at merge mapping `change → squash SHA`. **The change is the durable unit; commits are an implementation detail of how it got built.**

One file *per change* also means two developers on different changes never conflict, and the ledger is carried by git itself — team-wide aggregation inside a repo with no infrastructure.

### D9: Enforce the OpenSpec git discipline rather than describing it
Upstream's rule is that every OpenSpec state change must cross `main` before the next lifecycle phase depends on it: proposals run **on main** (from a branch, OpenSpec loses visibility of other in-flight changes and of the authoritative specs), and **merge precedes archive, every time**.

Specloop satisfies both today *by accident of ordering* — the branch is cut after proposing, and archive is invoked after the merge — but neither is enforced. An implicit ordering rule is exactly what an unattended loop violates silently, which is the same failure class this change exists to close. Both become `PreToolUse` checks using the machinery D1 already introduces.

### D10: Implementation may not begin until the plan is merged and approved
"Proposals run on main" is the weak form of the real rule. The strong form is a **two-gate flow**: artifacts are authored on a branch cut from current `main` (so OpenSpec still sees the authoritative specs and every other in-flight change), reviewed as a pull request, and merged. Only then may implementation branch — from a `main` that now contains the approved plan.

```
   plan branch ──► PR ──► review ──► merge to main
                                        │
                                        ▼   ← implementation may start ONLY here
                              impl branch ──► gates ──► PR ──► merge ──► archive
```

Two conditions are therefore checked before the first implementation task runs, and both are mechanical:

1. **Present on `main`** — the change's artifacts exist in `origin/main`, proving the plan was merged rather than merely written.
2. **Approved** — the change's `.openspec.yaml` carries `approved_by`, `approved_at` and an `approved_sha` matching the current artifact content (the keys are defined in `reposition-specloop` D7).

Condition 2 exists because condition 1 is not sufficient on its own: a merge proves the plan reached `main`, not that a human agreed with it — and an unattended loop can produce and merge its own plan. Recording the approver *in the repository* also means provenance survives independently of the forge; PR history is a different system with a different retention policy, and the repository should be self-describing.

This tightens D9 rather than replacing it: D9 keeps proposals off implementation branches, D10 gates implementation on the plan being merged and signed.

### D11: The pull request is where a plan is negotiated
D10 gates on approval but says nothing about where approval *happens*, which leaves the most important step in the flow unowned. A plan is not finished when its artifacts are written — it is finished when a human has argued with it and agreed. The pull request is the surface built for that argument: inline comments on specific lines, a review state, and a durable record of what was contested.

So the authoring flow **ends by opening a PR**, rather than leaving artifacts on a branch for someone to notice. Two consequences:

- The plan PR is a first-class artifact of the workflow, not incidental process. It gets a body summarising what is proposed and what is deliberately left open, because a reviewer who has to reconstruct the argument from four markdown files will approve without reading.
- D10's approval check becomes reachable. Without a step that creates a PR, nothing produces the approval it gates on, and the gate would deadlock every unattended run on a condition the loop had no way to satisfy.

### D12: Approval is attested from the forge, never authored by the model
The natural implementation of D10 — have the model write `approved_by` when it observes an approval — reintroduces exactly the hole D10 exists to close. A model that can write the field can write it wrongly, and under automation there is nobody to notice. Self-reported approval is not approval.

The gap is worth naming precisely, because the convention already exists and this change is only closing it. The OpenSpec adoption model cited in `reposition-specloop` D3 teaches exactly this flow — *"draft the spec, discuss it in comments, record approval"* — and calls the last step **a team convention**, arrived at independently of this design. A convention is a thing a person remembers to do; under automation the thing that remembers is the model whose work is being approved. Same field, same file, and the entire difference is whether anything checks.

**Decision: the fields are derived, not authored.** On merge, the value is read from the pull request's actual approving review:

```
gh pr view <n> --json reviews \
  → first review with state APPROVED  → author.login, submittedAt
```

`approved_sha` is computed over the change's artifact content at that moment, so a later edit is detectable rather than silently covered by a stale approval. The model's job is to run the command and record the output; it never supplies the value.

Two failure modes have to be decided rather than discovered:

| Situation | Behaviour |
|---|---|
| No `APPROVED` review on the PR | approval gate fails closed — merged is not approved |
| `gh` unavailable, unauthenticated, or offline | approval gate fails closed, reporting *why*; never falls back to an unattested value |

Failing closed is the right default because the alternative fails silently in precisely the unattended case this change exists to protect. A team that wants to work without a forge can bind the check to something else — the gate is a mechanism, and per `reposition-specloop` D6 the judgement is the adopter's — but the shipped default does not accept an approval nobody can verify.

The obvious objection is that a self-approving author defeats this: on a solo repository, the person who wrote the plan can approve their own PR. True, and not worth engineering around. The gate's purpose is to make approval a *deliberate, recorded act by a human* rather than a side effect of automation; a human clicking approve on their own plan has performed that act. What it stops is an unattended run manufacturing its own authorisation, which is the realistic failure.

## Risks / Trade-offs

- **`PreToolUse` matches command strings, not intent** → a differently-phrased commit (`cd x && git commit`, a script, `git -c … commit`) can slip past. Mitigation: match generously and treat this as raising the floor against accidents, not a jail. Documented as a Non-goal.
- **Marker staleness** → an edit after a green `ci` must invalidate the marker. Mitigation: markers are tree-hash based (self-invalidating) *and* a `PostToolUse` on `Edit|Write` clears the marker proactively.
- **Stop-hook runaway** → mitigated by D3's `stop_hook_active` guard; additionally cap continues per session as defense-in-depth.
- **Compaction mid-loop loses place** → `PreCompact` hook persists current change + first unchecked task.

## Open Questions

- **Verify two CLI/hook claims before depending on them:** (a) `--json-schema` paired with `--output-format json` for the structured report; (b) that an `ask` permission rule is evaluated before the auto-mode classifier and always prompts. If either is false, adjust D6/D4.
- ~~**Marker storage location**~~ — **RESOLVED (D7)**: `.git/` for the marker, because a lock *should* die with the clone and can never be committed by accident; `.specloop/runs/<change>.jsonl` for the ledger, because a metric must not.
- **Ledger row fields** — the one part that is expensive to change later. Current candidate: `{ts, gate, exit, duration_ms, change, task, tree, attempt}`. `attempt` is what makes red-cycles-per-task and first-pass-green rate computable; without it the ledger records outcomes but not effort.
- **Does the ledger belong in this change at all?** It is not enforcement. The argument for folding it in is that D7's write point is being opened here and nowhere else; the argument against is scope. If it splits out, the row shape must still be fixed *before* `gates run` is implemented.
- **Marker freshness window** — is tree-hash equality sufficient, or also bound the marker by time/commit to avoid a stale-but-matching tree edge case?
