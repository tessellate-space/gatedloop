## Context

See `proposal.md` — Why. `harden-unattended-loop` shipped the enforcement layer
(markers, the durable ledger, the `PreToolUse` deny hooks, the `Stop` hook); this
change fixes *where in the stack* that enforcement sits. Today every commit/merge
guarantee is enforced by matching the Bash tool's command string
(`hooks/gate-commit.sh`, `hooks/gate-merge.sh`: `case "$cmd" in *"git commit"*`),
and issue #2 records an agent defeating that by creating the commit through a
Python subprocess. The mechanism this change reuses unchanged is harden's
`gates gate-marker check <gate> <tree>` — an O(1) hash compare against a marker that
`gates run <gate>` writes on a green pass — and its durable per-change ledger
(`.specloop/runs/<change>.jsonl`, harden D7/D8). Nothing here re-runs a gate under a
hook timeout; every new check is a comparison against an existing record.

## Goals / Non-Goals

**Goals:** move commit/merge enforcement from the invocation layer to the effect
layer, so a differently-phrased commit is caught by *what it produces*, not *how it
was phrased*; keep the honest first line (layer 1) but stop it being load-bearing;
make a covert bypass an overt, merge-blocking incident; do it all with the markers
and ledger harden already ships, adding no new runtime dependency.

**Non-Goals:** broadening the `PreToolUse` string matchers (explicitly rejected, D1);
any forge-API-side implementation beyond documentation (D10); fixing issue #1 (brace
globs — a separate change); and harden-unattended-loop's own open closure tasks (e.g.
task 1d.7), which this change builds on but does not reopen.

## The four-layer model

Enforcement is layered because no single layer is complete, and the layers fail in
different directions. Each row states what the layer catches and what defeats it — the
same table goes into `AUTOMATION.md`, replacing its "raises the floor" admission.

| Layer | Mechanism | Catches | Defeated by |
|---|---|---|---|
| 1. `PreToolUse` string match (today) | `case "$cmd" in *"git commit"*` → `gate-marker check` | the honest direct `git commit` call | any indirection — `python -c`, a script, `sh -c`, GitPython (**observed**, #2) |
| 2. Git `pre-commit` hook | `gates gate-marker check ci` at the git layer | **every** commit-creating path (python, scripts, GitPython, `sh -c`) | `git commit --no-verify`; `env -u CLAUDECODE`; a stripped environment |
| 3. Post-hoc reflog audit | `Stop` hook walks new commits, joins each tree to the ledger's green-`ci` rows | any commit with no green record — i.e. everything that slipped layers 1–2 | nothing *hides* it; it is detection, not prevention (it cannot un-create the commit, only taint it) |
| 4. Forge branch protection | adopter-configured required checks/reviews on the default branch | `gh pr merge` and the forge-UI merge, which have no git-hook equivalent | a repo without branch protection configured (documented adopter requirement) |

Layers 1–2 are prevention; layer 3 is detection; layer 4 is the only cover for the
merge paths that never touch a local git hook. The design decisions below justify each.

## Decisions

### D1: Enforce at the effect, not the invocation — a git `pre-commit` hook

**Decision.** Ship a git `pre-commit` hook (a template under `templates/`, referenced
via `${CLAUDE_PLUGIN_ROOT}` per `plugin-relative-paths`) that runs the same
`gates gate-marker check ci "$(git write-tree)"` the `PreToolUse` hook already runs.
A git `pre-commit` hook fires on the *commit object being created*, regardless of
which program invoked it — `git commit`, `python -c … subprocess`, a wrapper script,
or a GitPython call all pass through it. That is the layer at which the guarantee
("never commit on red `ci`") is actually about the thing being guaranteed.

**Rejected alternative — broaden the string matchers.** Teach layer 1 to also match
`python -c` + `git`, `sh -c`, etc. Rejected explicitly (and by #2's own scope note):
it is an arms race with no fixed point — every new matcher invites the next phrasing —
and it still only sees invocations that spawn a recognizable subprocess, never a
library call. The git hook makes the matcher's incompleteness *irrelevant* for the
commit invariant, which is strictly better than making the matcher longer.

### D2: Env-scoped enforcement — the git hook enforces only inside a session

**Decision.** The `pre-commit` hook enforces only when `CLAUDECODE` is present in the
environment, and is a transparent no-op otherwise. Every agent session sets
`CLAUDECODE`, and every subprocess it spawns inherits it — verified in this repo
(`CLAUDECODE=1` is visible to a shell the agent launches), and it is exactly the
Python-bypass path from #2 that inherits it too. A human committing from a terminal
or IDE, or a CI runner, has the variable absent and sees no gate.

This is **not** a `fail-loud-gates` violation. Outside a session the check is not
*due*: the gate exists to hold an autonomous loop to its own invariant, and there is
no loop running a human's `git commit`. Inside a session the check cannot be dodged by
rephrasing the invocation. The rule the plugin enforces is "an agent may not commit on
red," not "nobody may ever commit" — scoping to the session is what makes that the
actual rule rather than a hostile one.

**Rejected alternative — unconditional enforcement.** A `pre-commit` hook that
enforces for everyone. Rejected because it blocks a teammate's ordinary commit (they
have no `ci` marker for their tree and no reason to run `gates run ci`), making the
plugin hostile to the rest of the team and guaranteeing it gets uninstalled — which
removes the enforcement for the agent too. Scoping to the session keeps the guarantee
exactly where it belongs and nowhere it doesn't.

### D3: Layer 2's limits are stated plainly, not papered over

`git commit --no-verify` skips all `pre-commit` hooks; `env -u CLAUDECODE git commit`
strips the enforcement scope; a deliberately stripped environment does the same. The
design states this rather than implying layer 2 is airtight.

**What changes versus today is still decisive, and is the whole point.** Evading
layer 1 can be *accidental* — any indirection at all does it, and #2 shows a model
reaching for indirection without intent to evade, just to get unstuck. Evading layer 2
requires typing `--no-verify` or `env -u CLAUDECODE` — a flag whose *only* purpose is
to skip the gate, with no other reason to be there. And layer 3 makes even that
visible after the fact. The move is from "defeated by ordinary indirection" to
"defeated only by an unmistakable act of evasion that is then reported" — which is the
difference between a floor and a wall with one clearly-marked door.

**Rejected alternative — claim layer 2 closes the hole completely** (e.g. by also
trying to intercept `--no-verify`). Rejected because `--no-verify` is git's own,
un-interceptable-from-a-hook escape, and claiming otherwise would repeat the original
sin this change exists to correct: a guarantee stated more strongly than it is
enforced. Honesty about the seam, plus layer 3 detection, is the correct posture.

### D4: The hook install is deterministic code, not prompt prose — `gates hook install`

**Decision.** A new `gates hook install` subcommand (stdlib-only, `zero-dep-shim`)
owns wiring the `pre-commit` hook. It detects who currently owns the hook path —
husky, lefthook, the `pre-commit` framework, a `core.hooksPath` redirect, or a bare
existing `.git/hooks/pre-commit` — and **composes** where it safely can (chain/append
the `gates` invocation into the existing manager's flow) and **refuses-and-instructs**
where it cannot determine a safe composition. It never clobbers an existing hook. This
is the same principle as surface selection (`bin/gates` in code, not a prompt): the
*judgement* about a project's hook topology is deterministic and testable; leaving it
to a prompt would make it non-reproducible and unreviewable.

A companion read-only `gates hook status` is included **only if** it earns its place —
the concrete consumer is `gates doctor`, which already reports partial-wiring states
(streamline D3/D4) and would naturally report "the git `pre-commit` hook is/ isn't
installed." If `doctor` is the sole caller, `status` ships as a `doctor` sub-check
rather than a standalone verb; the tasks resolve this rather than pre-committing to a
new top-level command.

**Rejected alternative — a prompt step that tells the adopter how to wire the hook.**
Rejected: hook-manager topology is exactly the kind of branchy detection a prompt does
unreliably and untestably, and a wrong compose silently disables either the project's
existing hooks or Specloop's. Determinism in the shim, with unit tests over each
detected topology, is the house pattern.

### D5: Opt-out-with-consent in `gates-init` — default-yes, never silent

**Decision.** `gates-init` gains a hook-install step (near the permission-scaffolding
step, streamline's step 6), offered as a **default-yes** question via AskUserQuestion:
an adopter who installed the enforcement plugin presumably wants the enforcement, so
the default leans toward installing. It is never installed silently, and declining
completes onboarding normally.

**Rejected alternatives, two of them.** (a) *Strict opt-in, default-no* — buries the
very fix that motivated the change behind a question most adopters will skip, leaving
the observed #2 hole open by default. (b) *Silent install* — violates the consent
pattern harden D4 and streamline established for anything that touches a developer's
local git/permission surface; a plugin must not modify `.git/hooks` (or a hook
manager's config) without an explicit yes. Default-yes-with-consent is the resolution
that neither buries the fix nor installs behind the adopter's back.

### D6: Post-hoc audit — the `Stop` hook walks the reflog and taints the ledger

**Decision.** The `Stop` hook (`hooks/continue-loop.sh`, already running at every
stop) gains an audit pass, implemented in the shim so it is testable: for each commit
new since the last audited point, compute its tree and look for a green-`ci` ledger
row (`gate: "ci", exit: 0, tree: <that tree>`) in `.specloop/runs/<change>.jsonl`. A
commit whose tree has **no** matching green-`ci` row was committed without a recorded
green gate — it slipped layers 1 and 2 — and is reported **loudly** (the incident,
naming the offending SHA and tree) and recorded as a **taint** on the change's ledger.

The join is exact because a legitimate task commit's tree equals `git write-tree` of
the staged index at commit time, which is exactly the tree `gates run ci` recorded in
its green ledger row for that task (harden D2's index-tree marker definition). So a
gated commit always matches and an ungated one never does — no heuristic. The
last-audited cursor is tracked per-worktree under `.git/` (ephemeral, like the
`Stop` hook's existing continue-counter), so the audit only walks genuinely new
commits and never re-reports.

This layer is **detection, not prevention** — it runs after the commit exists and
cannot un-create it. Its value is converting a covert bypass (a green-looking branch
nobody gated, the exact silent-failure-on-`main` this whole line of work exists to
stop) into an overt, recorded, merge-blocking incident.

**Rejected alternative — try to prevent the ungated commit from the `Stop` hook.**
Rejected as a category error: by the time a `Stop` hook runs the commit already
exists, so prevention is not on the table there; the honest framing is detection, and
the enforcement teeth come from D7 (the taint blocks the merge), not from pretending
the audit prevented anything.

### D7: The taint blocks the merge — it is not a report-only advisory

**Decision.** A taint recorded by D6 blocks the merge. The taint is written to the
durable per-change ledger (harden's store, D7/D8) as its own row kind, so it survives
to change completion and is carried by git. The merge gate (`hooks/gate-merge.sh` via
`gates`) gains a taint check alongside its existing green-`live-check`-on-head check
and refuses a tainted change. Clearing is cheap and self-describing: re-running
`gates run ci` green on the current branch head records a fresh green-`ci` row for the
head tree, which **resolves** the taint (the head is now individually verified even if
a mid-branch commit was not); the resolution is an appended clear row, keeping the
ledger append-only and the incident permanently visible in history.

**Rejected alternative — report the taint but let the merge proceed.** Rejected
because a report nothing acts on is precisely the defect this whole change corrects: a
guarantee that is only a sentence. `fail-loud-gates` is the house rule — a detected
ungated commit is a non-zero, blocking condition, not a note. Making the clear cheap
(one green `ci` run on the head) is what keeps blocking from being punitive.

### D8: Say precisely which guarantee was breakable, and where

The severity is not "red code reaches `main`" — it is narrower and worth stating
exactly, so the fix is neither over- nor under-sold.

- **The outer "verified on `main`" guarantee self-heals at the merge boundary for the
  local path.** The merge gate already requires a green `live-check` marker on the
  branch-HEAD tree (harden D1/D2). A red or ungated commit *mid-branch* therefore
  cannot reach `main` via `git merge` unless the head itself passes — the outer
  guarantee holds even under a mid-branch bypass.
- **What a bypass actually destroys is the per-task guarantee**: that each commit is
  atomic, individually gated on green `ci`, and therefore bisectable. A branch whose
  head passes but whose intermediate commits were ungated has lost its per-commit
  integrity even though its tip is clean. That is the real damage, and layers 2–3 are
  what protect it (layer 3's taint makes the lost integrity visible and blocks the
  merge until re-verified).
- **For `pull-request` integration modes the merge path itself has no git-hook
  equivalent.** `gh pr merge`, or a click in the forge UI, is not a local `git merge`,
  so neither layer 1 nor the merge gate fires — hence layer 4 (D10). This is where the
  self-heal argument does *not* hold, and it is why branch protection is a requirement
  for those modes rather than a nice-to-have.

**Rejected alternative — frame the bug as "red reaches main" and stop there.** Rejected
as both inaccurate (the local merge gate already prevents it) and as obscuring the real
loss (per-task integrity, and the PR-merge gap). Stating which guarantee broke where is
what lets each layer be justified against a specific failure rather than a vague fear.

### D9: One norm sentence in the loop prompts — cheap, honest, no longer load-bearing

**Decision.** Add exactly one sentence to `skills/tdd-apply/SKILL.md` and
`agents/tdd-implementer.md`: a denied gate call means the gate is unsatisfied, and
rephrasing the invocation to get past the denial is a loop violation, not a solution.
It is explicitly a prompt-layer nudge — the behavioural half of #2's problem 2 — and
it is fine that it is only a sentence now, because unlike before it is backed by
layers 2–4 and no longer the only thing standing between the model and an ungated
commit.

**Rejected alternative — rely on the prompt sentence alone (status quo of #2's
problem 2), or omit it entirely.** Rejected on both ends: alone it is exactly the
unenforced-sentence failure #2 observed; omitted, the model gets no in-context signal
about why the deny happened and what the right move is, wasting the cheap redirect.
One sentence, paired with real layers, is the calibrated amount.

### D10: Forge branch protection is a documented adopter requirement for PR modes

**Decision.** `SETUP.md` gains a requirement: for `integration.mode: pull-request`
(with or without `requireApproval`), the adopter configures branch protection on the
default branch (required status check on `ci`/`live-check`, and required review for the
approval variant). This is the only layer covering `gh pr merge` and the forge UI (D8),
which no local git hook can reach — the caveat open since PR specloop PR 8. Specloop documents the
requirement and names what to protect; it does not implement anything forge-API-side.

**Rejected alternative — a Specloop-side shim around `gh pr merge`.** Rejected by the
rejection test's second question: reaching into the forge's merge path is knowing a
specific forge's command/API, which is the adopter's binding, not Specloop's. The forge
already ships branch protection built for exactly this; documenting the requirement is
"make a stated guarantee enforceable" (ours), while re-implementing the forge's gate is
not.

### D11: The rejection test, applied to this change as a whole

| Question | Verdict | Reasoning |
|---|---|---|
| Does it author an artifact? | not ours, and it doesn't | It ships a git-hook template, shim subcommands, an onboarding step, and docs — no proposal/spec/design/tasks authoring. |
| Does it know a stack command? | not ours, and it doesn't bind one | The git hook calls `gates gate-marker check`; no project-specific test/build command appears anywhere (`stack-agnostic-prompts`). Hook-manager names (husky, lefthook, …) are detected to *compose with*, never invoked to run a project command. |
| Does it make a stated guarantee enforceable? | **ours** | This is the purest instance the repo has had: "never commit on red `ci`" was stated and defeated in the field (#2); this change makes it hold at the layer where the effect is unavoidable. |
| Does it get a team running faster? | **ours** | An unattended loop whose per-task integrity can no longer be silently lost is one a team can leave running with less supervision. |

**Verdict: passes**, on question 3 above all — the single-question form ("does it move
a phase from `act` to `close`, or move a team up a rung faster?") scores it as
deepening `close` on the enforcement it already owns.

## Risks / Trade-offs

- **`--no-verify` / `env -u CLAUDECODE` still bypass layer 2** → mitigated by layer 3
  (detection + merge-blocking taint) and stated plainly (D3); not claimed closed.
- **The reflog audit could false-taint a legitimately unusual commit** (e.g. a commit
  whose tree genuinely has no `ci` row because `ci` was never run for it) → the clear
  path is cheap (one green `ci` on the head) and the taint names the exact SHA/tree, so
  a false positive is self-diagnosing and self-clearing rather than silently blocking.
- **`gates hook install` meets a hook topology it can't classify** → it
  refuses-and-instructs rather than clobbering (D4); the failure mode is "you wire it
  by hand," never "your existing hooks silently broke."
- **PR-mode adopters who skip branch protection** → the guarantee degrades to layers
  1–3 (local paths only) for them; documented as a requirement (D10), and the Stop-hook
  audit still reports loudly even when it cannot block a forge-side merge.
- **Env-scope depends on `CLAUDECODE` remaining the session marker** → if Claude Code
  renames or drops it, the git hook becomes a no-op everywhere (fails safe toward the
  human-commit behaviour, never toward blocking humans); the tasks pin this to a
  verified check rather than an assumption.

## Open Questions

- **Does `gates hook status` earn a top-level verb, or ship as a `gates doctor`
  sub-check?** Resolved at implementation against its only consumer (D4) — noted here
  only because it is a naming choice with no bearing on the specs or the task breakdown.
- **Taint row placement within the ledger schema** — a new `gate: "taint"` row kind
  versus a dedicated field; both survive the squash and satisfy the merge gate. The
  spec fixes the *behaviour* (a taint blocks the merge, a green head clears it); the
  exact row encoding is an implementation detail the tasks settle, constrained only by
  harden's "fix the row shape before writing rows" rule.
