# Automation gaps — making the loop safe to run unattended

gatedloop's goal is that a change goes idea → merged while you're doing something else. This document originally *described* the gap between that promise and prompt-only enforcement; `harden-unattended-loop` closed it. What follows is the historical problem statement, updated in place to say what now enforces each guarantee — the reasoning stays because the *why* still matters, not just the *what*.

## The problem: every guarantee used to be a sentence in a prompt

The workflow's hard rules used to live only in prompt text:

| Guarantee | Where it's stated | What enforces it now |
|---|---|---|
| Never commit on red `ci` | `skills/tdd-apply/SKILL.md` §Guardrails | `hooks/gate-commit.sh` (`PreToolUse` on `Bash(git commit *)`) |
| Convention review clean before commit | `skills/tdd-apply/SKILL.md` §5f | the *verdict* stays a prompt instruction (an LLM judgement has no oracle), but the *invocation* is now recorded: `gates review record <clean\|findings>` appends a ledger row pinned to the reviewed tree, so the claim is auditable after the fact — see the note under §0.3 below |
| `live-check` blocks the merge | `skills/tdd-apply/SKILL.md` §7.5 | `hooks/gate-merge.sh` (`PreToolUse` on `Bash(git merge *)`). Only a merge into the integration target is gated (`gates discipline merge-scope`); a sync of the target into a change branch passes when it creates no commit of its own (`--no-commit`, `--squash`, `--ff-only`, `--abort`, a fast-forward or an already-up-to-date merge) and is denied otherwise, naming the route (`git merge --no-commit <ref>`, `gates run ci`, `git commit`; loop-hardening D3). A command that switches branches before it merges (`git checkout my-change && git merge --ff-only origin/main`) is judged by the branch the switch names (`merge-scope --branch`, friction-fixes D5); a switch the hook cannot resolve to one branch (detached, a path checkout, another directory) stays gated, and the denial says to run the merge as its own command. Both marker checks pass `--ref <incoming>`, so the store of the worktree holding that branch is read after the merging worktree's own (cross-worktree-evidence D1–D2); a denial names every store it read |
| Full `ci` is always the last word — a scoped marker gates a commit, never the merge | `openspec/changes/scale-gate-cost/design.md` D2 | `hooks/gate-merge.sh` also requires `gates gate-marker check ci <tree> --require-scope full` on the branch head; scoped = per-commit locality (this tree, this task), full = pre-merge truth (the whole declared `ci`) |
| Agent stops before the merge | `agents/tdd-implementer.md` §4 | still a prompt instruction for the agent's own restraint, but `requireApproval: true` integration mode now makes it structural too — nothing except a human can supply the review a PR-based merge needs. Where the opt-in permission scaffolding is in place (§3), its `ask` rule on `Bash(gates merge *)`, the command that integrates, prompts a human; a lane's routine `git merge` sync of the target into its own branch does not (merge-lane-friction D4), and `gates doctor`'s `merge-checkpoint` row flags the earlier `Bash(git merge *)` rule |
| Resumable — done ⟺ committed | `agents/tdd-implementer.md` §2 | unchanged in mechanism (git itself), but now also backed by the durable per-change ledger (`.gatedloop/runs/<change>.jsonl`) and `hooks/persist-loop-state.sh` |
| Proposals run on `main` | (implicit, D9) | `hooks/gate-propose.sh` (`PreToolUse` on `Write`) |
| Merge precedes archive | (implicit, D9) | `hooks/gate-archive.sh` (`PreToolUse` on `Bash(openspec archive *)`) |
| Implementation starts only on a merged, approved plan | (new, D10) | `hooks/gate-implement.sh` (`PreToolUse` on `Bash(git checkout -b *)`/`git switch -c *`) |
| An epic is never implemented | epic-linkage D3 | `hooks/gate-implement.sh`: `gates discipline check-implement` refuses first, before the approval check, for a change any active change names in `x-gatedloop-epic`, naming those children, whatever the epic's schema |
| An epic archives only after every child | epic-linkage D4 | `hooks/gate-archive.sh`: `gates discipline check-archive` refuses while any child is not archived, listing each with its `gates epics` state; the merge check still applies to the epic |
| The loop keeps moving unattended | (new) | `hooks/continue-loop.sh` (`Stop`) |
| A halt stops the loop, and says why | `agents/tdd-implementer.md` "Record the halt before you report it" (escalation-outcomes D3/D6) | `hooks/continue-loop.sh` (`Stop`) via `gates discipline check-continue`, which refuses to continue past a `halt` row newer than the change's last `task-start`; the row is written by `gates halt record <cause>` with a cause from a closed set, so a halt that was only narrated is re-entered |
| A task stops retrying once its budget is used | `agents/tdd-implementer.md` §5, `skills/tdd-apply/SKILL.md` §5e (retry-budget D1/D2) | `gates run` itself: before a `unit` or `ci` run for a task it counts the task's failed attempts from the ledger, and once `loop.attempts` is reached it exits 1 without running the gate. A fresh restart (`gates attempt restart`) needs a clean tree and is allowed `loop.fresh-restarts` times per task |
| A human turn in the loop is visible | `skills/tdd-apply/SKILL.md` §5e/§6/§7 "pause and ask" (escalation-outcomes D4/D5) | `hooks/record-ask.sh` (`PreToolUse` on `AskUserQuestion`) appends an `intervention`/`ask` row on a change branch — it records, never denies; the reflog audit appends an `intervention`/`human-commit` row for a commit whose only green-`ci` evidence was written outside a session |
| A commit made after the last session stop is audited before the merge | escalation-outcomes D5 | `hooks/gate-merge.sh` runs `gates audit --ref <incoming>` immediately before `gates taint check`, so such a commit is tainted or classified before the merge is decided. With the ref, the audit is of the change that ref names, run in the worktree holding its branch; run bare it audited the current branch, which during a merge from the primary is the target |
| A tainted change is refused when the merge runs on the target | merge-step (specloop PR 100) | `hooks/gate-merge.sh` passes the incoming ref: `gates taint check --ref <ref>` reads the change that ref names and its ledger as the ref carries it. Without it the check resolved the change from the current branch, which during a merge is the target, so it never fired. `gates merge` step 1 calls the same function |
| Verified on main: the merged tree is proven before the target sees it (`local-squash-merge`) | `tdd-apply` §7.5's three-line squash recipe (merge-step) | `gates merge <change>` runs the merge in code: the merge hook's incoming-tree checks as functions, an unscoped `ci` on the staged squash, `discipline check-commit` before each of its commits (the git-layer pre-commit hook still fires on them), the optional `confirm` gate, and one push only after every step passed. Its subprocess `git` calls are not seen by the Bash `PreToolUse` hooks; it is the sanctioned path because it runs those checks itself |
| A human accepted the behaviour, not just clicked merge (opt-in: `approval.acceptance`) | acceptance-gate D4 | `hooks/gate-merge.sh`'s fourth check, after taint: `gates acceptance check <tree>` on the same tree the live-check and unscoped-`ci` markers matched — passes only when the latest `acceptance` ledger row for that tree is an `accept`, attested by `gates acceptance attest --local` or from the merged PR (`--merged`, which `gates record-merged` runs) under `self`, or from the PR's `APPROVED` review (`--pr`); passes stating "not required" when no policy is declared, so the hook is byte-identical to before for everyone else |
| A forge merge requires the gates that passed locally (`pull-request` mode) | merge-pull-request D1 | `gates marker publish <gate>` posts `gatedloop/<gate>` only from a green local marker for the commit's normalized tree, naming that tree; `gates marker check-remote` verifies one. Nothing local can block a forge merge: branch protection requiring `gatedloop/ci` and `gatedloop/tests` from the CI provider is what enforces it (layer 4) |
| A locked test edited past the commit hooks never merges | test-lock-remote-check D1–D4 | `gates tests check --ref <commit>` evaluates the authored-test lock against a commit's tree and the ledger it carries, every task. `gates merge` step 1 runs it on the branch head in both modes; `gates marker publish tests` posts the result as `gatedloop/tests` (computed, no marker), success naming the tree or failure naming the path, and the shipped workflow publishes it on every pull request for branch protection to require |
| A forge merge reaches the ledger | merge-pull-request D3 | `gates record-merged <sha>` resolves the change through the squash commit's PR head, records the merge row against that sha and archives, in one local commit that `discipline check-commit` allows at planning grade (ledger rows ride along); under `approval.acceptance: self` the same commit first gets the PR merge's `accept` row (none when that tree is already accepted, nothing committed when the writer refuses); a merged `plan/<change>` PR re-attests a stale `approved_sha`; a commit from no active change is skipped |

Interactively the old gap was fine: you were watching, and you caught drift. Unattended it was the whole risk — a model that skipped a gate produced a green-looking branch that was never gated, and nobody was present to notice. `harden-unattended-loop` closes that by converting every row above except the review-invocation one into a hook-enforced invariant — and that one into a recorded, auditable artifact, which is as far as a gate with no oracle behind it can honestly go (§0.3). See `SETUP.md`'s "Enforcement" section for the adopter-facing version of this table.

Claude Code exposes ~30 hook events. gatedloop used one (`SessionStart`); it now also uses `PreToolUse`, `Stop`, and `PreCompact`. (A `PostToolUse` hook that cleared the `ci` marker on every Write/Edit was removed by `hook-correctness` D3: the marker is keyed on the staged tree, which an edit never touches, so the clear added nothing and destroyed valid evidence.)

## The solution — shipped in `harden-unattended-loop`

Four changes, in dependency order. All are plugin-local; none require an external account or a research-preview feature. All four are shipped; see `openspec/changes/harden-unattended-loop/design.md` for the full decision record (D1-D12) and `openspec/changes/harden-unattended-loop/tasks.md` for what was verified where.

### 1. Turn the gates into `PreToolUse` denials (shipped)

Gate the tool call, not the model's intention.

- `PreToolUse` on `Bash(git commit *)` → deny unless `ci` passed green **on this exact tree**.
- `PreToolUse` on `Bash(git merge *)` → deny unless `live-check` passed green on the branch head.

Do **not** re-run the gate inside the hook — full CI under a hook timeout is unusable. Instead: `gates run <gate>` writes a marker recording the gate name and the tree hash on success; the hook compares the marker's hash against the current tree and exits 2 when they diverge. The check is O(1) and the guarantee is exact — a marker cannot survive an edit.

This converts "never commit on red" from an instruction into an invariant — but only
against the *honest* `git commit`. The `PreToolUse` matcher reads the Bash tool's command
*string*, and that is the wrong layer for the commit invariant: a commit created through
indirection (a Python subprocess, a written-then-run script, `sh -c`, a git library)
carries no `git commit` substring, so it slips straight past. That was an accepted
trade-off until it was **observed in the field (issue #2)**: a denied agent went looking
for a differently-phrased path rather than satisfying the gate. `enforce-at-the-effect`
answers it by moving enforcement to the layer where the *effect* is unavoidable — the
four-layer model below.

### The four-layer enforcement model (`enforce-at-the-effect`, issue #2)

No single layer is complete, and they fail in different directions. Each row states what
the layer catches and what defeats it.

| Layer | Mechanism | Catches | Defeated by |
|---|---|---|---|
| 1. `PreToolUse` string match (today) | `case "$cmd" in *"git commit"*` → `gate-marker check` | the honest direct `git commit` call | any indirection — `python -c`, a script, `sh -c`, a git library (**observed**, #2) |
| 2. Git `pre-commit` and `pre-push` hooks | `gates discipline check-commit` at the git layer (layer 1's own check), and `gates discipline check-push` for a push of the merge target, **inside a declared agent session only** | **every** commit-creating path (python, scripts, libraries, `sh -c`), on any host; a raw merge of the target pushed by hand | `--no-verify`; unsetting the `discipline.agent-env` variables; a stripped environment |
| 3. Post-hoc reflog audit | `Stop` hook joins each new commit's tree to the ledger's green-`ci` rows | any commit with no green record — everything that slipped layers 1–2 | nothing *hides* it; it is detection, not prevention — it taints and blocks the merge but cannot un-create the commit |
| 4. Forge branch protection | adopter-configured required checks/reviews on the default branch | `gh pr merge` and the forge-UI merge, which have no git-hook equivalent | a repo with no branch protection configured (documented adopter requirement) |

Layers 1–2 are prevention; layer 3 is detection; layer 4 is the only cover for the merge
paths that never touch a local git hook. What changed versus the string matcher alone is
decisive: evading layer 1 is *accidental* (any indirection does it, which is exactly what
#2 observed — a model reaching for indirection to get unstuck, not to evade); evading
layer 2 requires typing `--no-verify` or `env -u CLAUDECODE`, a flag whose only purpose is
to skip the gate; and layer 3 makes even that visible after the fact and blocks the merge
until the head is re-verified. The move is from "defeated by ordinary indirection" to "a
wall with one clearly-marked door that is then reported."

- **Layer 2 is opt-in** — `gates hook install` (offered by `/gatedloop:gates-init`,
  default-yes) wires a git `pre-commit` hook that runs the same `gates discipline
  check-commit` as layer 1 (ledger-grade and planning-grade allowances, else the O(1)
  `ci` marker compare). A planning diff that also carries ledger rows stays
  planning-grade (merge-pull-request D3): the ledger is invisible to every marker, so it
  neither earns nor costs the discount.
  The same install adds a git `pre-push` hook (`git-layer-enforcement` D3): a push that
  updates the merge target is denied unless `gates discipline check-push` finds the
  pushed commit proven — a `merge` ledger row records it (or records a commit it
  carries only ledger and planning paths beyond, which is what `gates merge`'s own
  push is), or the merge gate's incoming-tree checks hold for its tree: a `live-check`
  and a full `ci` marker, `verify` where declared, and for each change it carries in,
  no unresolved taint, the authored-test lock and acceptance where a policy is
  declared. A denial names each unmet check and `gates merge <change>` as the remedy.
  Other branches and deletions pass silently, and no gate runs inside either hook.
  Both hooks enforce **only inside a declared agent session**: `gates discipline
  agent-session` exits 0 when a variable `discipline.agent-env` lists is set (default
  `[CLAUDECODE]`, inherited by every subprocess including the #2 Python path); a human
  terminal, IDE, or CI runner sees a transparent no-op. This is not a `fail-loud-gates` violation: outside a session
  the check is not *due* — the gate exists to hold an autonomous loop to its invariant,
  and no loop is running a human's commit. The installer composes with a hook manager
  (husky, lefthook, the pre-commit framework, a `core.hooksPath` redirect, or a bare hook)
  where it safely can and refuses-and-instructs where it cannot — it never clobbers.
- **Layer 3 needs nothing configured** — the `Stop` hook audits every new commit and
  records a **taint** on the change's durable ledger (`.gatedloop/runs/<change>.jsonl`,
  own row kind `gate: "taint"`) for any commit whose tree has no green-`ci` row. The merge
  gate refuses a tainted change until a green `gates run ci` on the branch head appends a
  `taint-clear` row (append-only — the incident stays in history). The join is exact: a
  gated commit's tree equals the tree `gates run ci` recorded, so there is no heuristic.
- **Layer 4 is a documented adopter requirement**, not gatedloop code — for
  `integration.mode: pull-request`, the forge's own branch protection is the only thing
  covering `gh pr merge`; see `SETUP.md`'s "Branch protection is required for
  pull-request integration modes."

### What holds where: enforcement per layer and host (`git-layer-enforcement`)

The shim, the manifest and the ledger run on any host. Enforcement sits at three
layers, and only the first is tied to Claude Code:

- **Tool hook**: the `hooks/hooks.json` hooks. They fire only in a Claude Code session.
- **Git layer**: the `pre-commit` and `pre-push` hooks `gates hook install` writes.
  They fire on any host, inside a declared agent session: `discipline.agent-env` in
  `.gates.yaml` lists the variables that mark one (default `[CLAUDECODE]`), and
  `gates discipline agent-session` makes the decision for both hooks. An adopter on
  another host adds that host's variable; it is the one binding another host needs.
- **Forge**: branch protection requiring the `gatedloop/*` commit statuses
  (`gates marker publish`), on any forge that has statuses.

| Guarantee | Tool hook (Claude Code) | Git layer (any host, agent session) | Forge (branch protection, statuses) |
|---|---|---|---|
| A commit only on a green `ci` for its tree | `PreToolUse` on `git commit` | `pre-commit`: `discipline check-commit` | `gatedloop/ci` required |
| Authored tests stay locked, and run red first | `PreToolUse` on `git commit` | `pre-commit`: `tests check` | `gatedloop/tests` required |
| A merge into the target only on a proven head | merge gate (`gate-merge.sh`) | not gated: a raw `git merge` is caught at the push instead (`pre-merge-commit` misses fast-forwards) | required statuses on the PR head |
| A push of the target only of a proven commit | none | `pre-push`: `discipline check-push` | branch protection on the target |
| Implementation only after an approved plan | `PreToolUse` on `git checkout -b` | none | none |
| A change scaffolded only on an allowed branch | `PreToolUse` on `openspec new change` | none | none |
| No plan writes during implementation | `PreToolUse` on writes | none | none |
| Ungated commits detected after the fact (audit, taint) | the `Stop` audit records the taint | a recorded taint refuses the push (`check-push`) | none |
| Forge merges (`gh pr merge`, the web UI) | none | none | branch protection only |

**On a host other than Claude Code** the shim, the ledger, the commit gate, the push
gate and the forge statuses hold. The tool-hook denials do not: implement after
approval, the scaffold and propose discipline, archive after merge, and the `Stop`
audit that records a taint. A taint recorded elsewhere is still enforced at the push.

Two failure directions are deliberate. A host that does not pass its environment
variables to git's subprocesses makes both git-layer hooks a no-op (toward the
human, never toward blocking one). A hook that cannot resolve the shim — no plugin
root, no `gates` on PATH, and the path `gates hook install` recorded is gone — lets
the commit or push through with a stderr note, and `gates doctor` reports that copy
stale.

### 2. Keep the loop running with a `Stop` hook (shipped)

Prompt-type hooks don't exist for `Stop` (design D3, a correction on this document's original text) — `hooks/continue-loop.sh` is a **`command`**-type `Stop` hook instead. If a change branch is checked out, `tasks.md` has unchecked tasks, and the tree is clean at a task boundary, it emits `{"decision": "block", "reason": "continue from: <next task>"}` on stdout. Claude starts another turn instead of handing control back.

Bounded by the same thing that bounds the loop today: the gates. A halted or gate-blocked run (dirty tree) does not satisfy the condition and does not spin. A *clean* halt used to be indistinguishable from a task boundary; since escalation-outcomes (D3) a recorded halt — a `halt` row newer than the change's last `task-start` — also stops it, and `gates task start` on resume lifts it. Guarded against runaway two ways: the hook reads `stop_hook_active` from its own stdin and refuses to re-block when set, and a per-session continue cap (50) acts as defense-in-depth on top of that.

### 3. Scaffold permissions from `/gatedloop:gates-init` (shipped)

An unattended run stalls on the first permission prompt and sits there until you return. `gates-init` now offers — opt-in, explicit confirmation required — to write **`.claude/settings.local.json`**, never the shared `.claude/settings.json` (design D4, a correction on this document's original text: a plugin must not silently broaden a repo's permission surface for everyone; this file is personal and gitignored):

- `allow`: `Bash(gates *)`, `Bash(openspec *)`, `Bash(git commit *)` — the loop's own vocabulary.
- `ask`: `Bash(gates merge *)` — this encodes `tdd-implementer`'s "STOP BEFORE THE MERGE" as an actual boundary. An `ask` rule is evaluated before an `allow` rule and before the auto-mode classifier, so it prompts even under `Bash(gates *)` and the human checkpoint survives auto mode. It sits on the command that integrates (`gates merge` locally, the forge under pull-request mode), not on every `git merge`: the merge hook still gates a raw integration `git merge`, and an `ask` on every `git merge` stalled unattended lanes on their routine sync of the target (issue #44, merge-lane-friction D4). Scaffolding written before 0.6.0 asks on `Bash(git merge *)`; `gates doctor`'s `merge-checkpoint` row warns on it and `/gatedloop:upgrade` offers the one-line edit. (This specific claim about `ask`-rule precedence is documented behavior, not exercised in a live session by this change — see the task list's "Needs manual verification" notes.)

Declining leaves permission files untouched. The rule the agent promises to obey becomes a rule it cannot disobey — for the developer who opts in.

### 4. Add a headless entry point (shipped)

The actual "go do something else" surface:

```bash
claude -p "/gatedloop:tdd-apply <change>" \
  --permission-mode acceptEdits \
  --output-format json
```

`tdd-implementer`'s final report now ends in one line of literal JSON — `{change, tasks_done, tasks_total, branch, gates, outcome, cause, acceptance}` — so a headless caller doesn't parse prose. `cause` (escalation-outcomes D6) is `null` on `READY TO MERGE` and, on a halt, echoes the `halt` row the implementer recorded with `gates halt record` before reporting. `acceptance` (acceptance-gate D6) is `"required"` or `"not-required"`, read from `gates acceptance policy`, and the implementer prints `gates acceptance brief` immediately before the report; the earlier fields are unchanged. Both `--json-schema` and `--output-format json` are confirmed-present flags on the Claude Code CLI (`claude --help`); this document does not claim a live headless run was exercised as part of shipping this — see SETUP.md's "Running headless" section for the adopter-facing version.

## Deliberately deferred

**Channels.** `agents/tdd-implementer.md` §1 says the agent cannot ask the user, so it HALTs on ambiguity. A channel (Telegram/Discord/iMessage) changes that: the agent messages your phone and continues on your reply, instead of dying early. This is the largest single improvement to unattended completion rate — but it needs a bot token, a `--channels` launch flag, and it is a research preview. Separate decision from the four above.

**Routines (cloud).** Good fit for read-only work on a fresh clone — a `pull_request.opened` trigger running `convention-review` is a natural match. Bad fit for the main loop: routines get a fresh cloud clone with no local services, so `live-check` probes cannot run.

**`/loop` and scheduled tasks.** Session-scoped, expire after seven days, and require the session to stay open. The `Stop` hook (§2) covers the same ground with fewer constraints.

**Deep links.** No meaningful role in an unattended workflow.

## Order of work

1 → 3 → 2 → 4. The gates (1) must be real before the loop is allowed to run itself (2), and permissions (3) must be scaffolded before either matters in an unattended run.

## Beyond the four: git discipline, approval, and a ledger

The shipped change grew two things beyond the original four-part solution above, both
recorded in `openspec/changes/harden-unattended-loop/design.md` D7-D12:

- **A durable per-change ledger** (`.gatedloop/runs/<change>.jsonl`) alongside the
  ephemeral `.git/` marker — same write point (`gates run <gate>` finishing), opposite
  lifetime. It survives a squash-merge and is keyed on `(change, task)`, never a commit
  SHA.
- **OpenSpec's git discipline, enforced rather than described**: proposals run on
  `main`, merge precedes archive, and — the strong form — implementation cannot begin
  until a change's plan is present on `main` **and** carries an approval attested by a
  legitimate writer, never self-reported by the model (`gates discipline
  check-implement`). *Which* writer is legitimate is policy-dependent
  (`solo-approval-mode`, below) — the gate itself is not: it always checks the same
  two things, key presence and a matching content hash, regardless of which writer
  produced them. `/gatedloop:propose` ends the authoring flow by opening that PR
  instead of leaving artifacts on a branch.

## Update (`unblock-parallel-planning`): gates measure the repo the command runs in

A halted `harden-unattended-loop` run surfaced the assumption underneath every hook
above: each one resolves the repository via `cd "${CLAUDE_PROJECT_DIR:-$(pwd)}"` — the
**session root** — never the repository the guarded command will actually execute in.
That is correct in the single-checkout case and wrong the moment a second git worktree
is in play: markers live under the per-worktree `.git/worktrees/<name>/`, so a hook that
measures the session root checks a commit against the wrong index and an empty marker
store, denying a genuinely green commit. `unblock-parallel-planning` fixes this at its
root rather than documenting it as a limitation:

- **Every hook now resolves `cwd` first.** `gate-commit.sh`, `gate-merge.sh`,
  `gate-archive.sh`, `gate-implement.sh`, `gate-propose.sh`, and
  the new `gate-scaffold.sh` all parse the top-level `cwd` field Claude Code already
  sends with every hook invocation and `cd` there before doing anything git-related,
  falling back to `CLAUDE_PROJECT_DIR` only when `cwd` is absent, and to `pwd` only when
  neither is set. This makes the natural escape hatch for issue #5 — an implementer
  holding the primary checkout while planning proceeds in a second worktree — actually
  work, instead of being the one configuration the enforcement layer broke.
- **A planning-only commit is gated proportionally**, not against `ci`: `gates
  discipline check-commit <tree>` classifies the staged diff and, when every path is a
  planning file, substitutes manifest + OpenSpec artifact validation for the `ci`
  marker. See `SETUP.md`'s "A planning-only commit is gated at planning grade" for the
  adopter-facing version.
- **D9 (proposals run on `main`) now also admits a `plan/*` branch** based on the merge
  target, and `openspec new change` is gated by the same discipline one step earlier
  than the artifact write, so a refusal never strands a half-created change directory
  (issue #7).

**Reconciliation point with `enforce-at-the-effect`, closed by
`lock-and-ledger-hygiene` (D4).** That change's git-layer `pre-commit` hook (layer 2 of
the four-layer model above) called `gates gate-marker check ci` directly, so a
ledger-only or planning-only commit made by any path the `PreToolUse` hook did not see
was denied and paid a full `ci` run. It now runs `gates discipline check-commit`, the
same entry point as layer 1, so the two layers share one implementation. A hook copy
installed before 0.5.0 keeps the old body until it is refreshed: `gates hook install`
replaces gatedloop's own stale direct copy with the shipped template, saving the old
body as `pre-commit.gatedloop-prev` (`adoption-followups` D3), and `/gatedloop:upgrade`
offers that refresh as the recurring `git-hook-refresh` item.

## Update (`solo-approval-mode`): the D10 gate stays fixed, its writers become policy-dependent

Three field-trial reports (#3, #4, #6) converged on one gap: every approval writer
above assumes a forge PR and a second human, which a remoteless solo repo does not
have — GitHub itself refuses to let an author approve their own PR, so `gates approval
attest --pr` correctly refuses every time in that setup, forcing exactly the hand-edit
D12's sha pin exists to catch. The fix declares the policy instead of leaving it as an
orchestrating session's undeclared convention:

- **`.gates.yaml` gains an optional `approval:` block** — `plan: review` (today's
  behavior, the default when absent) or `plan: self` (standing self-approval).
  `gates validate` rejects any other value.
- **`gates approval attest <change> --local`** is a second legitimate writer, valid
  only under a declared `self` policy: it reuses the exact same content-hash
  computation `--pr` uses, records the configured git identity, and refuses outright
  under `review` (or an absent block), naming `--pr` instead of falling back to it
  silently.
- **The D10 gate itself did not change.** `gates discipline check-implement` and
  `gates approval check` never read the `approval:` block — they still check exactly
  the same two things regardless of which writer produced the keys: presence, and a
  content hash that still matches. The policy is consulted by the writers only,
  which is why declaring `self` cannot silently weaken what the gate enforces.
- **This repo hit the exact gap live**, immediately before this change existed:
  three plan PRs (specloop PR 23 `unblock-parallel-planning`, specloop PR 24 `expand-brace-globs`, specloop PR 25
  `solo-approval-mode` itself) were merged without an `APPROVED` review for the
  reason above, and the human explicitly authorized one-time hand-written
  `approved_by`/`approved_at` values (the sha itself still computed by `gates
  approval sha`, never invented) as a bootstrap — see commits "attest:
  unblock-parallel-planning approved" and "attest: solo-approval-mode +
  expand-brace-globs approved". `--local` under a declared `self` policy is what
  makes that hand-edit the last one.
- **The session brief now routes an approved, unimplemented change to the
  implementer** (design D4): `hooks/_session_brief.py` shells out to `gates approval
  check <name>` for every apply-ready change and offers spawning `tdd-implementer` as
  the default action only for the ones that pass, naming the missing step instead for
  the ones that don't — "default" is never "auto-started" in either file that states
  it (`hooks/session-brief.sh`, `commands/start.md`).

See `openspec/changes/solo-approval-mode/design.md` for the full decision record
(D1-D4) and SETUP.md's "The declared approval policy" for the adopter-facing version,
including the D3 honesty note this update extends rather than contradicts: content is
attested mechanically and unconditionally; identity is only ever as strong as
whichever writer recorded it.

### Approval attestation, verified against real pull requests (task 1d.7)

Run 2026-09-04 in a throwaway private repo (`radub21/specloop-e2e-1d7-d9c715`, PRs 1
and 2 — left in place, the test account's token has no `delete_repo` scope). GitHub
refuses a self-approval, so the `APPROVED` review came from `github-actions[bot]` via a
`pull_request` workflow using `GITHUB_TOKEN`, which needs both
`default_workflow_permissions: write` and `can_approve_pull_request_reviews: true` on
the repo — worth knowing for anyone reproducing this. Both the oracle
(`gates discipline check-implement`) and the hook that reads it
(`hooks/gate-implement.sh`, fed a real `PreToolUse` payload) were exercised at each
step:

| Situation | `check-implement` | hook | Reported reason |
|---|---|---|---|
| approved plan, not yet merged | exit 1 | — | not present on `origin/main` |
| merged, not yet attested | exit 1 | — | merged, but no `approved_by` |
| **(a) approved + merged + attested** | **exit 0** | **allow** | merged to `origin/main`, approved by `github-actions` |
| **(b) merged with no approving review** | **exit 1** | **deny (2)** | `gates approval attest` refused first — `"PR #2 has no APPROVED review"` — and wrote nothing |
| **(c) approved, then the artifact edited** | **exit 1** | **deny (2)** | `approved_sha` no longer matches the plan content on `origin/main` |

Two results from that run are worth stating plainly:

- **`attest` is the only writer, and it fails closed.** In (b) the refusal came *before*
  any value existed to check: `.openspec.yaml` was left untouched, so the later
  `check-implement` refusal was a second line of defence, not the first.
- **The sha pin proves content, not the approver.** A hand-written `approved_by` with a
  *recomputed* `approved_sha` passes — verified, exit 0, approver
  `a-human-i-invented`. Task 1d.6's claim holds only in its literal form: a hand-edit
  fails *once the artifacts change*. What actually stops a self-approval is that
  `.openspec.yaml` only counts when it is on the default branch, which is why forge
  branch protection is a **requirement** for `pull-request` integration modes (SETUP.md,
  layer 4) rather than an optional extra. Recorded, not fixed: no local check can tell a
  forged approver from a real one, because the forge is the only party that knows.

## The 2026-08-17 baseline run, resolved or left open

`tasks.md` §0 recorded six gaps from the first live unattended run, before any of the
above existed. Their disposition:

- **Atomicity** (one task per commit) — a deliberate non-decision: the marker/hook
  layer does **not** enforce "one task per commit" as an invariant. It stays prompt
  guidance (`skills/tdd-apply/SKILL.md` §5h/§Guardrails), not silently promoted to a
  rule nobody asked for.
- **Red→green observability** — closed structurally. The ledger records every `gates
  run <gate>` invocation, pass or fail; `skills/tdd-apply/SKILL.md` §5c/§5e now pass
  `--task`/`--attempt` through the red and green `unit` runs, so a red run before
  implementation is recorded rather than only asserted.
- **Convention review invocation** — closed as far as it can honestly be closed.
  Convention review is a subagent call, not a `gates run <gate>` invocation, so the
  ledger never saw it. It does now: `gates review record <clean|findings> --task <N.M>`
  appends a `review` row to the same `.gatedloop/runs/<change>.jsonl` ledger, carrying
  the verdict as the row's exit code and the exact tree that was reviewed, and a clean
  verdict also writes a `review` marker so `gates gate-marker check review <tree>`
  answers "is this review still about this tree?" with the same self-invalidating hash
  compare `ci` uses.
  What that buys is **falsifiability, not an oracle**, and the distinction is the whole
  point. The verdict is still an LLM's judgement; what changed is that a task with no
  review row, or a clean row naming a tree that was never committed, is now visible
  instead of invisible — the original finding was that the claim could be neither
  confirmed *nor refuted*.
  Deliberately **not** done: no third `PreToolUse` denial. Design D1 gates the commit on
  `ci` and the merge on `live-check` because both have an executable oracle behind them;
  denying a commit for want of a self-recorded verdict would enforce only that a command
  was typed, while imposing the ceremony on every hand commit in every adopting repo.
  Recorded and auditable, not blocking — stated here rather than decided silently, per
  finding 0.1's rule.
- **Misattributed edits** — closed. `gates task start <N.M>` records the tree a task
  began from as a `task-start` row on the same ledger, and `gates task changed` reads
  it back as the set of paths that differ *now* — so "did I change this file?" is
  answered from data rather than recollection. Two details are what make the answer
  trustworthy rather than merely available: **untracked files are included** (the
  disowned edits were uncommitted, and `git diff <tree>` alone never names an
  untracked file, so an answer built only on it would have agreed with the run's wrong
  conclusion), and **a missing baseline is refused loudly** instead of rendering as
  "nothing changed", which would recreate the finding exactly. `skills/tdd-apply/SKILL.md`
  §5a starts every task with the baseline; `agents/tdd-implementer.md` §3 requires
  consulting it before discarding anything. Like the review row this is an artifact,
  not a denial — nothing blocks on it, because the failure it addresses is an agent
  reasoning from memory, and the remedy for that is data it can consult.
- **Unattended archive** — declared out of scope for unattended runs, not fixed.
  `/gatedloop:archive` delegates to `/opsx:archive` (design D2/`no-forked-upstream-assets`:
  it holds no copy of the upstream prompt, so it cannot itself pass a `-y` flag through
  a confirmation upstream owns), and `/opsx:archive`'s interactive confirmation is
  upstream OpenSpec's surface. `openspec archive -y --json` (the direct CLI, 4 seconds)
  is the unattended-safe path when archiving is genuinely needed as part of an
  automated run; SETUP.md's "Running headless" section states this plainly rather than
  promising a headless archive gatedloop's own commands don't deliver.
- **Green-in-tree, red-at-HEAD** (task 0.6) — closed. This is exactly what D2's
  index-tree marker definition (not the working tree) prevents; `hooks/gate-commit.sh`
  denies the commit in this scenario, verified against the specific failed-`git add`
  reproduction (`tasks.md` §1.7).

## Update (`worktree-native-loop`): `check-archive`/`check-implement` accept a sound local merge target

A serialized merge lane (one worktree per implementer, one merge lane in the primary
checkout — `docs/worktree-lanes.md`) used to pay an interim push after every single
merge: `check-archive` and `check-implement` both tested change presence only against
the resolved *origin* ref, so archiving (or starting the next change's implementation)
right after a local merge required pushing first just to satisfy a check that has
nothing to do with durability. Design D5 splits the two gates by what each actually
guarantees:

- **`check-archive`'s guarantee is ORDERING** — merge precedes archive, nothing else.
  A local counterpart branch of the merge target (`main` when the target resolves to
  `origin/main`) that carries the change proves that ordering exactly as well as
  origin does, so it's now accepted — with a loud advisory (`merged locally but not
  yet pushed to origin; push before ending the session`) rather than silently. The
  origin ref is still tried first; the local counterpart is the fallback, never the
  first-choice evidence.
- **`check-implement`'s guarantee is a REVIEWED, ATTESTED plan** — and that's
  policy-dependent (`solo-approval-mode`, above). Under `plan: review`, the
  attestation is anchored to the forge PR's approving review, which a purely local
  ref cannot evidence — origin stays unconditionally required, and a local-only
  merge is refused exactly as if it weren't merged at all. Under `plan: self`, local
  attestation is already the legitimate writer (the whole point of that policy), so
  the same local-counterpart fallback applies, with the same advisory.
- **Neither gate's approval/ordering logic changed** — `_approval_check` still checks
  exactly the same two things (presence, then a content hash that still matches), just
  against whichever ref (origin or local counterpart) resolved; declaring `self` still
  cannot silently weaken what either gate enforces.
- Resolution order matters: the origin ref is always tried first (the stronger
  evidence — it's what a reviewer or a teammate can actually see), and the local
  counterpart is computed only from a resolved `origin/<name>` target with a same-named
  local branch that actually exists — there is no "local counterpart" of a ref that
  is already local, and nothing is invented when one doesn't exist.

Push-after-merge remains recommended hygiene either way: the local acceptance is a
serialization convenience, not a durability claim — an unpushed merged change still
dies with the laptop. See `openspec/changes/worktree-native-loop/design.md` D5 for the
full decision record and `docs/worktree-lanes.md` for the adopter-facing map of what's
per-worktree vs repo-wide and where local acceptance applies.

## Update (`split-test-author`): the implementer cannot edit its oracle, and red is checked

`test-quality-rule` gave review the words for a low-value test; it could not remove the
cause, which is one agent writing the tests from the code it is about to write. The fix
splits authorship — a `test-author` agent writes every task's failing tests before
implementation begins — and, like every other guarantee here, the split only holds if a
sentence in a prompt is not what holds it. Two guarantees move from prompt to
enforcement:

- **The implementer never edits an authored test.** The handoff (`gates tests handoff`)
  records every authored test's blob in the ledger. `gates tests check` refuses a commit
  whose staged index holds a placed test that differs from the blob placed for it, or a
  held test (`.gatedloop/authored/<change>/…`) that differs from the latest handoff. The
  only way to change an authored test is back through its author: `gates tests defect
  --kind setup|assertion|green`, then a re-handoff for that task. The kind is required and
  each has its own cap per task, enforced by refusing the next defect: three `setup` (the
  test cannot run as written; past the cap, halt `weak-spec`), two `assertion` (it asserts
  the wrong behaviour; past the cap, a human, `oracle-conflict`), one `green` (the placed
  tests passed before any implementation, an observation rather than a claim they are
  wrong; the author re-declares the task or rewrites the tests, and past the cap a human
  decides, `oracle-conflict`). A defect row from before kinds existed counts as
  `assertion`. A defect at a completed task reopens it: the re-handed-off tests are placed
  and locked as usual, and the red run its first placement recorded stays the record. A
  halt voids a placement only at a task not yet completed, completion being ordered by
  the commits that tick the task and carry the row (`unblock-authored-lock` D2–D5).
- **Red before green is a checked fact.** For every placed task with tests, the same
  check requires a run of the task's **oracle gate** recorded after the placement that
  failed with an exit other than 75 (a precondition failure is not a red run), and it
  refuses implementation staged for the task in flight before its tests are placed. The
  oracle gate is the one the plan's tag declares (`[oracle: integration]` needs a red
  `gates run integration --task <N.M>`), read from `tasks.md` in the tree being checked
  (the staged index, or the commit under `--ref`), and `unit` for an untagged task
  (`task-oracle` D2, D4). A task its author declared `characterization` (a locked
  `CHARACTERIZATION` file beside its held tests), or that the plan tags
  `characterization`, is held to the reverse: its first verdict on that gate after
  placement must be green, and a red one is refused as a defect. The same check refuses a task
  whose tag in the checked tree differs from its tag in the merge target's `tasks.md`, so
  the branch cannot choose its own oracle; the tag changes only by amending the plan on
  the target and re-attesting it, since the approval sha covers the tags (`task-oracle` D9).

Both run where the `ci` marker check runs: `hooks/gate-commit.sh` (layer 1) and the git
`pre-commit` hook (layer 2) call `gates tests check` right after it, so every
commit-creating path the marker check covers is covered here too. The one exception is a
ledger-grade commit (`unblock-authored-lock` D1): when `check-commit`'s verdict is
`ledger`, read from the one-token file it writes under `--verdict-file`, both hooks skip
the lock, because a staged diff of only `.gatedloop/runs/**` cannot change a test. That
is what lets a halt row, a defect row and `gates merge`'s own step-1 and step-5 commits
through on a branch whose lock would fail at the index. A ledger row staged with any
other path is not ledger-grade, so the lock still runs on it. It runs at commit, not
on Write/Edit, because a tool hook cannot tell the author from the implementer, and the
author legitimately rewrites held tests on a defect; the commit is where the two roles'
outputs join. With no handoff for the change — or on the merge target — the check passes,
so a project or change that predates the split is unaffected. See
`openspec/changes/split-test-author/design.md` D3–D5.

**The lock now holds at commit, merge and forge** (`test-lock-remote-check`). The commit
hooks see only the commits made through them; a `--no-verify`, a human edit or a host
with no hook carried an edited placed test to the merge. `gates tests check --ref
<commit>` runs the same conditions against a commit's tree and the ledger it carries,
for every task; `gates merge` step 1 requires it on the branch head in both integration
modes, and `gates marker publish tests` posts it as the `gatedloop/tests` status that
branch protection requires beside `gatedloop/ci`. A change with no handoff passes, so a
planning or docs pull request gets the status too.

## Update (`retry-budget`): the stopping rule is enforced in code

"If a gate stays red after 2 focused fix attempts, HALT" was a sentence in
`agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md` §5e. `--attempt` was
recorded on every ledger row, and nothing counted it. Now the count comes from the
ledger alone:

- **The cap.** A failed attempt is a red row of the task's oracle gate (`unit` unless
  the plan's tag declares another) or of `ci`, after its RED run (the first red
  oracle-gate row) and after its latest `restart`. Exit 75 never counts. Once the count
  reaches `loop.attempts` (default 2), `gates run unit|ci` for the task refuses with
  exit 1, runs nothing and writes no row. The caller's `--attempt` is a label, so
  passing a smaller one buys nothing.
- **One fresh restart, never self-granted.** `gates attempt restart` refuses on a
  dirty tree and past `loop.fresh-restarts` (default 1). The `stalled` halt row
  carries `restart_available`, computed by the shim, so a dispatcher decides from a
  fact rather than from the implementer's report.
- **Memory between attempts.** `gates attempt note` records four bounded one-line
  fields per failed attempt, and a resumed or restarted agent reads `gates attempt
  notes`. Their quality stays the agent's, like a commit message's.

The refusal is the enforcement: it sits in `gates run`, the only way the loop runs a
gate, so no hook is needed. What stays a prompt instruction is that the implementer
halts on the refusal rather than switching to some other way of running the tests.
The commit hooks still need a green `ci` on the staged tree, and `ci` is refused, so
that route is closed too. See `openspec/changes/archive/2026-10-20-retry-budget/design.md` D1–D4.

## Update (`token-ledger`): what a task cost, and a budget enforced in code

The ledger recorded `duration_ms` and nothing else about spend. A team asking whether
the loop paid for itself read a billing page instead. The host writes per-message
usage next to the session, and the plugin's hooks already receive that transcript's
path, so the gap was a reader:

- **What the hooks now write.** `hooks/gate-commit.sh`, once it has allowed a commit,
  runs `gates usage record --stage` with the hook input's `transcript_path`. The task's
  `usage` row is staged into the commit it costs. `hooks/continue-loop.sh` runs the
  same record at every `Stop`, re-invocations included, before the continue decision,
  so a halted or abandoned task is costed too. The git-layer `pre-commit` hook has no
  hook input; inside an agent session it records a `no-transcript` row with null
  counts. Nothing the record does can deny a commit or fail a stop.
- **Counts only.** A row stores, per model, input, output, cache-read and cache-write
  token counts, the number of assistant messages and the window. No transcript text
  is ever copied into the ledger.
- **A flush is not work in progress.** A tree whose only change is appended `usage`
  rows still counts as a clean task boundary, both for the `Stop` hook's continue
  decision and for `gates attempt restart`. Any other change still stops the loop.
- **The budget is enforced in code.** `loop.token-budget` is checked in `gates run`
  beside the attempt cap. Once the change's recorded usage reaches it, a task-bearing
  `unit` or `ci` run refuses with exit 1, names `gates halt record budget`, and runs
  nothing. As with the attempt cap, no hook is needed: `gates run` is the only way
  the loop runs a gate, and the commit hooks still need a green `ci`. What stays a
  prompt instruction is halting on the refusal rather than retrying. The count lags
  by the task in flight, which is recorded at its commit or the session stop.

See the `token-ledger` change's design, D1–D8.


## Update (`loop-hardening`): the plan approval at the merge, and denials that name their cause

An adopter's orchestrator report, checked on 0.10, found five places where a
guarantee was stated but not enforced, or a denial named the wrong cause:

- **The plan approval is checked at the merge and at acceptance.** The approval
  was checked when implementation started, and never again. `gates merge` step 1
  now runs it first, in both modes: the approval recorded on the target must still
  match the plan there, and the plan on the branch head must hash to that recorded
  sha. Every acceptance writer (`--local`, `--pr`, `--merged`) runs the same check
  before writing. Under `approval.acceptance: self`, `gates record-merged` still
  records the merge row, because the forge merge happened, but no acceptance, and
  exits non-zero naming the re-approval. An untagged `tasks.md` stays outside the
  sha, so a tick never needs re-approval (D1, D2; #101).
- **A sync into a change branch may not commit by itself.** Git runs no pre-commit
  hook for a merge commit, so a plain `git merge origin/main` in a lane created a
  commit no gate saw; the audit tainted it, and the taint surfaced only at merge
  step 1. The merge hook now denies a committing sync and names the route:
  `git merge --no-commit <ref>`, then `gates run ci`, then `git commit`, an ordinary
  commit both commit hooks gate. The taint refusal lists each tainted commit's
  short sha and subject and marks a merge commit (D3–D5; #108).
- **An unparseable manifest fails loud in one line.** A `.gates.yaml` with
  conflict markers crashed every subcommand with a traceback, or, without PyYAML,
  parsed silently. Both paths now exit 1 with the file, the position and the
  reason. `hooks/gate-commit.sh` passes the shim's output through instead of
  calling every `check-worktree` failure a shared branch (D6, D7; #109).
- **The hooks judge the repository the command runs in, or deny.** `hook git-cwd`
  expands `~`, `~/…`, `$HOME/…` and `${HOME}/…`, and a `cd` inside a leading `(`
  governs only that subshell. A `cd` it still cannot evaluate (another variable,
  `~user`, a command substitution) used to fall through to the session's checkout;
  `git-cwd` now exits 3, and every hook that guards a command denies with "use an
  absolute path or `git -C <dir>`". This supersedes worktree-native-loop D1's
  fall-through for the `cd` rung only (D8; #110).
- **A handoff never loses tests, and never blames the author for main.**
  Placement accepts a test file's content at `git merge-base HEAD <target>`, so a
  pre-existing test main changed after the handoff is placed over rather than
  called a defect. A full `gates tests handoff` refuses when it would drop a task
  that is already placed (D9, D10; #111).
- **The READY report's gate fields come from the ledger.** `gates ledger
  record-ready` prints `gatedloop: gates {"ci": …, "review": …, "live_check": …}`,
  with `review` one of `clean`, `findings`, `partial` or `none`, and
  `tdd-implementer` copies it unchanged (D11; #112).

See the `loop-hardening` change's design, D1–D12.
