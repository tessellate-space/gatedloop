## Why

Specloop's promise is that a change goes idea → merged while you're doing something else. Today the loop *describes* that but doesn't *enforce* it: every hard guarantee — "never commit on red `ci`", "convention review clean before commit", "`live-check` blocks the merge", "stop before the merge", "done ⟺ committed" — lives only as a sentence in a prompt (`skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`). Interactively that's fine because a human is watching. **Unattended, a model that skips a gate produces a green-looking branch that was never gated, and nobody is present to notice — a silent failure that lands on `main`.**

Claude Code exposes ~30 hook events; Specloop uses one (`SessionStart`). The gap isn't a missing feature — it's a missing *enforcement layer*. This change adds it, so the guarantees become invariants the model cannot violate rather than instructions it is asked to follow.

## What Changes

- **Gate `git commit` / `git merge` with `PreToolUse` deny hooks, backed by markers.** `gates run <gate>` writes a marker recording the gate name and the exact tree it passed on; a `PreToolUse` hook on `Bash(git commit *)` denies unless a fresh `ci` marker matches the tree being committed, and `Bash(git merge *)` denies unless a `live-check` marker matches the branch head. The hook does an O(1) hash compare — it never re-runs CI under a hook timeout. This converts "never commit on red" from a request into an invariant.
- **Ship a `Stop` hook that keeps the loop running.** A **`command`-type** `Stop` hook (not `prompt` — prompt hooks aren't available for `Stop`) that, when a change branch is checked out with unchecked `tasks.md` tasks and a clean tree at a task boundary, blocks the stop and continues from the next task. Guarded by `stop_hook_active` so it can never spin.
- **Scaffold least-privilege permissions from `/specloop:gates-init`, opt-in.** Optionally write `.claude/settings.local.json` (personal, gitignored — never the shared `settings.json`) with `allow` for the loop's own vocabulary (`gates *`, `openspec *`, `git commit *`) and `ask` for `git merge *`. The `ask`-on-merge encodes `tdd-implementer`'s "STOP BEFORE THE MERGE" as an enforced human checkpoint that survives auto mode.
- **Add a headless entry point + a structured final report.** Document/enable `claude -p "/specloop:tdd-apply <change>" --permission-mode acceptEdits --output-format stream-json`, and make `tdd-implementer`'s final report machine-parseable (`{change, tasks_done, tasks_total, branch, gates, outcome}`) so runs can be queued, chained, and reported without a human reading terminal output.
- **Two complementary hooks:** `PostToolUse` on `Edit|Write` clears a stale `ci` marker proactively; `PreCompact` persists loop state (current change + first unchecked task) so a long unattended run that compacts mid-loop doesn't lose its place.
- **Write a durable ledger alongside the ephemeral marker.** The marker and the ledger are the *same moment* (`gates run <gate>` finishing) with *opposite lifetimes*: the marker is a lock under `.git/` that should die with the clone, the ledger is a record under `.specloop/runs/<change>.jsonl` that must not. Rows are keyed on `(change, task)` — never a commit SHA, which a squash-merge orphans — with one `change → squash SHA` row appended at merge. One file per change means git itself carries the metrics, with no infrastructure. Only the row's *shape* is urgent; every consumer of it is a sink that can be added later.
- **Enforce the OpenSpec git discipline instead of describing it.** Proposals run on `main` (from a branch, OpenSpec loses sight of other in-flight changes and the authoritative specs) and merge precedes archive. Specloop satisfies both today only *by accident of ordering* — precisely the kind of implicit rule an unattended loop breaks silently — so both become `PreToolUse` checks on the machinery this change already introduces.
- **Make the pull request the negotiation surface for a plan.** A plan is not finished when its artifacts are written; it is finished when a human has argued with it and agreed. So the authoring flow ends by opening a PR rather than by leaving artifacts on a branch for someone to notice, and that PR is where the proposal is reviewed, amended, and approved before any code exists.
- **Attest the approval instead of letting the model assert it.** On merge, `approved_by` / `approved_at` / `approved_sha` are written into the change's `.openspec.yaml` from the pull request's *actual* approving review (`gh pr view --json reviews`), never typed from the model's belief about who approved. A run that writes its own approval line is exactly the failure the approval gate exists to prevent, so the field is derived from the forge rather than authored.

## Evaluation impact

- Evaluation impact: none — plugin workflow/enforcement tooling; no scored pipeline, prompt, or model-facing code path.

## Capabilities

### New Capabilities
- `loop-enforcement`: turns the loop's prompt-stated guarantees into hook-enforced invariants — marker-backed `PreToolUse` gates on commit/merge, enforced OpenSpec git discipline (propose on main, merge before archive), a plan-review flow whose approval is attested from the pull request rather than self-reported, a self-guarded `Stop` hook that continues the loop, opt-in least-privilege permission scaffolding with an enforced pre-merge checkpoint, a durable per-change ledger of gate outcomes, and a headless entry point with a structured report.

### Modified Capabilities
<!-- None — this adds enforcement around the existing (prompt-level) workflow; it does not change the loop's described steps. -->

## Impact

- **Plugin files added/modified**: `hooks/hooks.json` (add `PreToolUse`, `Stop`, `PostToolUse`, `PreCompact` entries alongside the existing `SessionStart`); new `hooks/*.sh`/`*.py` gate/continue/marker scripts; the shim gains marker read/write (`gates gate-marker …`), approval attestation, and a machine-readable report mode; the onboarding command gains the opt-in permissions step; `agents/tdd-implementer.md` emits the structured report; `SETUP.md`/`README.md` document the headless path.
- **Depends on `rename-to-gates`.** This change adds substantial new surface to the shim and four hook scripts that call it; landing it before the rename means renaming twice, with the second pass over hook scripts where a missed reference fails inside a `PreToolUse` handler.
- **Depends on `reposition-specloop`** for the definition of the `.openspec.yaml` approval keys; this change populates and enforces them.
- **Requires a forge CLI for attestation.** Reading the approving reviewer needs `gh` (or an equivalent) and network access. The degraded path must be explicit: when attestation is unavailable, the approval gate fails closed rather than accepting an unattested value.
- **Runtime behavior in every adopting project**: commit/merge become gated by real hooks; new sessions may auto-continue an in-progress change.
- **No new account or research-preview feature** — all hooks are plugin-local and use standard Claude Code hook events. The one new external dependency is a forge CLI for approval attestation, and it is confined to that one check, which fails closed without it.
- **Dogfood note**: this change is authored in the Specloop repo itself (its first self-hosted change). *Running* the loop on it requires the plugin to be installed (so `gates` is on PATH); authoring the artifacts does not.

## Non-goals

- **Channels** (Telegram/Discord/iMessage so the agent asks instead of HALTing) — highest-value for unattended completion, but needs a bot token and is a research preview. Separate decision.
- **Cloud routines** — a fresh cloud clone has no local services, so `live-check` probes can't run; unfit for the main loop (fine for read-only `convention-review` on a PR).
- **`/loop` and scheduled tasks** — session-scoped, expire after 7 days, require the session to stay open; the `Stop` hook covers the same ground with fewer constraints.
- **A hard sandbox around git.** `PreToolUse` command-string matching raises the floor against *accidental* gate-skipping; it is not an airtight jail against a determined bypass, and this change does not claim to be one.
- **Specloop self-hosting setup** (its own `.gates.yaml` + gate bodies) — a separate bootstrap; this change ships the hooks for adopters.
