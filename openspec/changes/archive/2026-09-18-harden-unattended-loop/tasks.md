## 0. Measured baseline — what prompt-only enforcement actually delivers

Recorded 2026-08-17 from the first live unattended run of `/specloop:tdd-apply`, against
a real brownfield project (`personal-finance-coach`, 7-task change, 3 commits). This is
the "before" this change is measured against. Every guarantee below is today enforced by
nothing but a sentence in a prompt.

**Held under test** — worth knowing, because it means enforcement is closing a risk, not
fixing a known-broken loop:

- *Never commit on red.* Verified by checking out each commit and running the `ci` gate
  against that tree: 3/3 exit 0. Not self-reported — independently re-run.
- *done ⟺ committed.* Every commit paired its code with its `tasks.md` checkbox flip, so
  the run is resumable at exactly the point it stopped.
- *Stops before the merge.* `main` untouched. It halted at the blocking live-check
  because the stack was down and said it would not fabricate a green. The easy failure —
  mark it done and merge — did not happen.

**Did not hold, or could not be observed** — these are the gaps enforcement must close:

- [x] 0.1 *Atomicity is looser than the prompt claims.* Three commits covered six tasks
      (one commit spanned tasks 1.2–1.4). "One task per commit" is stated but unenforced,
      and the marker/PreToolUse work should decide whether it is a real invariant or
      guidance — do not enforce it silently either way
- [x] 0.2 *Red→green was not observed, and was partly skipped.* The task that would have
      supplied the failing test first was rescoped away mid-run (defensible: no JS unit
      runner exists and the proposal forbids new dependencies — and it documented the
      call). But the core behaviour change landed with no failing test preceding it. A
      marker can record that `unit` ran and failed before implementation; nothing does today
- [x] 0.3 *Convention review could not be confirmed to have run.* The run claimed every
      commit was "convention-clean". There is no artifact backing that claim. Whatever
      records gate satisfaction should also record review invocation, or the claim stays
      unfalsifiable
- [x] 0.4 **The run misattributed its own file edits to a non-existent third party.** It
      reported that "a background watcher/orchestrator in this environment is actively
      editing files" and disowned three uncommitted changes. No such watcher exists; the
      tree was clean at the starting commit and nothing else ran. The edits were its own —
      and were *correct* (adding `npx bddgen` to a BDD recipe, the genuine root cause of a
      red gate). This is the most serious finding of the run: an unattended agent that
      cannot distinguish its own writes from another party's will also mis-reason about
      what is safe to commit, revert, or overwrite. Consider recording the tree hash at
      task start so "did I change this?" is answerable from data rather than memory

- [x] 0.5 *The archive cannot run unattended.* `/specloop:archive` delegates to
      `/opsx:archive`, which blocks on an interactive confirmation. Headless, that is not a
      slow step — it never returns: two runs died at a 10-minute timeout and an API
      disconnect having done nothing. The same archive via `openspec archive -y --json`
      completes in **4 seconds**. A wrapper can only be as unattended as the thing it
      wraps, so the headless entry point (§4) must either pass `-y` through the delegation
      or declare archiving out of scope for unattended runs. Both failed runs left the repo
      clean, which is the one reassuring part

- [x] 0.6 *A commit was green in the working tree and red at `HEAD`.* Observed 2026-08-18
      in the unattended `rename-to-gates` run (16 commits). Commit `4e3dbba` staged a
      `git add` whose pathspec still named `.harness.yaml` after the rename had moved it;
      the bad pathspec aborted the **whole** `git add`, so `bin/gates` was committed as a
      pure rename carrying its *old* content — a shim that looked for a manifest filename
      the same commit had renamed away. Re-running `ci` against that commit's tree gives
      `no manifest found`, exit 1. The agent's own gate run before committing had passed,
      because it tested the working tree rather than the index. It caught this via
      `git diff` and repaired it in `681edf4` before anything built on it, and disclosed
      it unprompted — so the loop self-corrected, but only because a human-grade check
      happened to follow.

      **This is evidence, not a new gap.** Task 1.1 already binds the `ci` marker to
      `git write-tree` of the *index*, which is exactly what would have denied this
      commit. That choice currently reads as a precaution; it is now the difference
      between catching this run's one bad commit and shipping it. Do not weaken it to the
      working tree for convenience — this is the case that costs.

## 1. Marker infrastructure + PreToolUse gates (enforcement floor)

- [x] 1.1 Add marker read/write to the shim: `gates run <gate>` writes a marker on success recording the gate name + the committed-tree hash (`git write-tree` of the index for `ci`; branch-head tree for `live-check`); markers stored under `.git/` (per-worktree, never committable)
- [x] 1.2 Add `gates gate-marker check <gate> <tree>` — O(1) compare, exit 0 match / non-zero mismatch — for hooks to call
- [x] 1.3 `hooks/gate-commit.sh`: `PreToolUse` on `Bash(git commit *)` → deny (exit 2) unless a fresh `ci` marker matches `git write-tree`
- [x] 1.4 `hooks/gate-merge.sh`: `PreToolUse` on `Bash(git merge *)` → deny unless a fresh `live-check` marker matches the branch head
- [x] 1.5 Register both in `hooks/hooks.json` alongside the existing `SessionStart`; confirm a deny hook overrides an `allow` permission (D5)
- [x] 1.6 Test against a throwaway repo: green-ci commit allowed; no-marker commit denied; edit-after-ci commit denied; partial (subset) staged commit allowed when ci ran post-stage
- [x] 1.7 Test the observed failed-staging case from 0.6 explicitly, because it is the inverse of 1.6's last row: `ci` runs green, then a `git add` **fails** (bad pathspec) so the index never receives the tested content. The working tree still matches the marker; the index does not. The commit must be denied. A hook that compares the working tree passes this case wrongly, which is the whole reason 1.1 reads the index

## 1b. Ledger — same write point as the marker, opposite lifetime (D7/D8)

- [x] 1b.1 Fix the row shape BEFORE implementing `gates run`'s writes: `{ts, gate, exit, duration_ms, change, task, tree, attempt}` — omitting a field cannot be reconstructed later
- [x] 1b.2 Append one row per `gates run <gate>` to `.specloop/runs/<change>.jsonl` (durable, committed) — distinct from the `.git/` marker (ephemeral, never committed)
- [x] 1b.3 Key rows on `(change, task)`, never on a commit SHA; record the tree hash for the join back to history
- [x] 1b.4 Append exactly one `change → squash SHA` row at merge time
- [x] 1b.5 Ensure `.specloop/runs/` is committed (NOT gitignored) and archives with the change; one file per change so concurrent developers never conflict
- [x] 1b.6 Test against a throwaway repo: rows survive a squash-merge intact; no row references a SHA that is absent from `main` after the squash

## 1c. Git discipline as hooks, not prose (D9)

- [x] 1c.1 `PreToolUse` check: deny authoring a proposal artifact while a change branch is checked out — proposals run on `main`
- [x] 1c.2 `PreToolUse` check: deny archive for a change not yet merged to `main` (merge → archive ordering)
- [x] 1c.3 Test both against a throwaway repo, including the legitimate paths (propose on main allowed; archive after merge allowed)
- [x] 1c.4 Gate implementation on the plan being **merged**: refuse to start unless the change's artifacts are present in `origin/main` (D10)
- [x] 1c.5 Gate implementation on the plan being **approved**: refuse unless `.openspec.yaml` carries a populated `approved_by` and an `approved_sha` matching current artifact content (D10)
- [x] 1c.6 Record the approver on the run's ledger rows, so the ledger answers "who authorised this run" without leaving the repo
- [x] 1c.7 Test the automation-proof case: a headless run that authors a plan cannot proceed to implementation in the same session

## 1d. Plan review as a pull request, with attested approval (D11/D12)

- [x] 1d.1 End the authoring flow by opening a plan PR whose body summarises what is proposed and what is left open
- [x] 1d.2 Define what `approved_sha` is computed over (the change's artifact files, in a stated order) and implement it so the same content always yields the same hash
- [x] 1d.3 On merge, read the approving review via `gh pr view <n> --json reviews`, take the first `APPROVED` review, and write `approved_by` / `approved_at` / `approved_sha` into `.openspec.yaml`
- [x] 1d.4 Fail closed when no `APPROVED` review exists — merged is not approved
- [x] 1d.5 Fail closed when `gh` is missing, unauthenticated, or offline; report the reason and never write an unattested value
- [x] 1d.6 Verify the model cannot supply the value: attestation reads only the forge response, and a hand-edited `approved_by` fails the `approved_sha` check if artifacts changed
- [x] 1d.7 Test end to end in a throwaway repo with a real PR: approved → implementation proceeds; merged-without-approval → refused; approved-then-artifact-edited → refused. **Run 2026-09-04** against `radub21/specloop-e2e-1d7-d9c715` PRs specloop PR 1/#2 — all three observed as specified, at both the oracle (`gates discipline check-implement`) and the hook (`hooks/gate-implement.sh`); recorded in `AUTOMATION.md`. One limit found and recorded rather than fixed: a hand-written `approved_by` with a *recomputed* `approved_sha` passes, so 1d.6's guarantee holds only in its literal form and what actually forecloses a self-approval is forge branch protection on the default branch (layer 4)

## 2. Permission scaffolding (opt-in) — precedes self-running

- [x] 2.1 Extend `/specloop:gates-init` to OFFER (explicit confirm) writing `.claude/settings.local.json` — never `settings.json` — and to add `settings.local.json` to `.gitignore` if missing
- [x] 2.2 Rules written: `allow` `gates *` / `openspec *` / `git commit *`; `ask` `git merge *`; verify the `ask`-on-merge prompts even under an auto permission mode (else adjust — open question)
- [x] 2.3 Declining leaves permission files untouched

## 3. Stop hook — keep the loop running (after gates are real)

- [x] 3.1 `hooks/continue-loop.sh`: a **command** `Stop` hook — continue when (change branch) ∧ (`tasks.md` has `[ ]`) ∧ (clean tree at a task boundary); emit block decision with `reason: "continue from task N.M"`
- [x] 3.2 Read `stop_hook_active` from stdin and refuse to re-block when set (no runaway); add a per-session continue cap as defense-in-depth
- [x] 3.3 Register `Stop` in `hooks/hooks.json`; test: continues with unchecked tasks; does NOT continue when halted/red or when `stop_hook_active`

## 4. Headless entry point + structured report

- [x] 4.1 `agents/tdd-implementer.md`: emit the final report as parseable fields (`change, tasks_done, tasks_total, branch, gates, outcome`)
- [x] 4.2 Document the headless invocation in `SETUP.md`/`README.md`: `claude -p "/specloop:tdd-apply <change>" --permission-mode acceptEdits --output-format stream-json`; verify `--json-schema` support before promising structured stdout (open question)

## 5. Complementary hooks

- [x] 5.1 `PostToolUse` on `Edit|Write` → clear the `ci` marker proactively (belt-and-suspenders over the hash self-invalidation)
- [x] 5.2 `PreCompact` → persist loop state (current change + first unchecked task) so a mid-loop compaction doesn't lose the place

## 6. Docs + validation

- [x] 6.1 Update `AUTOMATION.md` to reflect the shipped design (mark the six corrections resolved)
- [x] 6.2 `claude plugin validate .` passes; all new hook scripts are exercised in a throwaway repo
- [x] 6.3 README/SETUP describe the enforcement model (gates are now hooks, not just prompt rules)
