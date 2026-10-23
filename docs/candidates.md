# Candidates

Ideas that passed the rejection test but are deliberately not scheduled. Recorded so
they are not re-derived from scratch, and so the reason for waiting is on the record
alongside the reason for wanting them.

An entry here is **not** a commitment. Promoting one means opening a change and
re-applying the rejection test with whatever has changed since.

---

## `gates audit` — score a project's loop coverage

**What.** Report, per SDLC phase, how far the project's own tooling reaches on the
0–4 rung scale (`none` / `advise` / `observe` / `act` / `close`), and for every phase
sitting at `act`, name the specific verdict that would close it.

**Why it is a good fit.** It is the *climb* job in `reposition-gatedloop` D3 made
measurable. gatedloop already holds everything the report needs: `.gates.yaml` says
which gates exist and which surfaces they cover, the ledger records whether they
actually run, and the rung scale is already the vocabulary the docs use. The output
is the diagnosis an existing hand-written coverage audit produced against the same
scale — *"held at rung 3 by missing oracles, not missing tools"* — which is exactly
the sentence an adopter needs in order to know what to build next.

**Against the rejection test.** Authors no artifact. Names no stack command. Does not
itself move a phase from `act` to `close` — but it tells a team which phase to move
and what the missing oracle is, which is the fourth question answered squarely.

**Why not now.** Three reasons, in order of weight:

1. **It measures things that do not exist yet.** Half the interesting signal is
   run history, and the durable ledger arrives with `harden-unattended-loop`.
   (`escalation-outcomes` now supplies that half: `gates stats --outcomes` reports
   what stopped each run — halts by cause, interventions by kind — from the ledger.
   It measures throughput, not coverage, so this entry is not promoted by it.)
2. **Scoring needs more than one workflow to be worth anything.** With a single
   loop shape an audit has one axis, the same objection that defers benchmarking in
   `workflow-packs`. Packs are a prerequisite, not a competitor.
3. **A scoring rubric is opinion until it is calibrated.** Publishing rung
   assignments a team disagrees with damages the frame the docs are about to adopt.
   Better to run it by hand against real projects a few more times first.

**Promote when.** The ledger is landing real run records, at least two workflows are
in use, and the rung assignments have been applied by hand to two or three projects
without argument about the scoring.

---

## `gates doctor` — diagnose an invisible install

**What.** A diagnostic command that checks whether gatedloop is actually reachable
in the current session — plugin installed under the active config profile,
commands/skills registered, session-brief hook wired — and says which of those is
missing when the answer is no.

**Why it is a good fit.** Claude Code supports multiple config profiles via
`CLAUDE_CONFIG_DIR`, and a plugin installed under one profile is completely
invisible under another: no commands, no skills, no session brief, no error.
Diagnosing that took a full round trip during the 2026-08-19 field run (see
`docs/review-2026-08-18.md` §"Field run — 2026-08-19"). It is F5's "probe, don't
assume" applied to gatedloop's own reachability, not just the OpenSpec contract.

**Against the rejection test.** Authors no artifact. Names no stack command (it
probes Claude Code's own install state, not a project's). Makes an implicit,
currently-unstated guarantee ("if it's installed, you'll know") checkable — the
third question, squarely.

**Why not now.** It is a diagnostic surface with no home yet. `reposition-gatedloop`
D3 already assigns "climb" jobs — onboarding, `gates-init`, workflow packs — a
place to live; a standalone doctor command would duplicate that home rather than
use it. It belongs bundled with the bootstrapper/doctor change once `streamline-onboarding`
(or its successor) opens one, not standing alone before that change exists.

**Promote when.** `streamline-onboarding` (or whatever change owns the
bootstrapper) is proposed — fold this in as one of its checks rather than opening
a separate change for it.

---

## Protect locally-edited generated OpenSpec assets from `openspec init`

**What.** Some way to stop an adopter from silently losing hand-edits to generated
OpenSpec files the next time `openspec init --tools claude` runs.

**Why it is a good fit.** Confirmed in the field: re-running `openspec init
--tools claude` against a real project overwrote three locally-edited generated
files (203 insertions, 91 deletions) with no prompt beyond a warning, recoverable
only because the tree was clean first (see `docs/review-2026-08-18.md` §"Field
run — 2026-08-19", FR4). Silent data loss on a routine re-run is exactly the kind
of stated-but-unenforced guarantee ("your edits are safe") the rejection test's
third question is for.

**Against the rejection test.** It falls on the **"ours"** side by that third
question — but the mechanism available today is guidance, not enforcement: the
overwrite is upstream OpenSpec's `init` doing exactly what it's documented to do,
so a code-level guard would mean gatedloop shimming another tool's command, which
is the second question's "not ours." The honest move today is the guidance form
of the guarantee — tell adopters to fork a schema instead of editing a generated
file (`openspec schema fork <source> <name>`) — which `streamline-onboarding`
should say plainly per FR4.

**Why not now.** The mechanism is upstream's, so the honest first move is
guidance (fork, don't edit), not code. A gatedloop-side safeguard only becomes
defensible if guidance proves insufficient in practice.

**Promote when.** Guidance alone (in `streamline-onboarding`) turns out not to be
enough — adopters keep losing edits despite being told to fork — at which point
revisit whether a pre-`init` guard is defensible as enforcement rather than a
stack-command binding.

---

## Per-task model tiering, with escalation

**What.** Let a task list name a cheaper model for the tasks that don't need
`tdd-implementer`'s full Sonnet judgment (a mechanical rename across N files, a
docs-only task with no oracle), with escalation back to the default tier when a
task turns out to need more than the cheap tier can give it — the second half of
#4, deferred out of `solo-approval-mode` by its own proposal.

**Why it is a good fit.** `solo-approval-mode` already makes "spawn the
implementer" the discoverable default action for an approved, unimplemented
change (design D4) — it gets a team to the point of running the loop
unattended faster. Per-task tiering is the next rung on the same ladder: once
spawning the implementer is routine, the next question is whether every task in
that change needs the same tier of model, and #4's escalation half is what
keeps a cheap-tier task from silently producing worse output when it turns out
to be harder than it looked.

**Against the rejection test.** Does it author an artifact? No — `tasks.md` is
already authored by the schema; this only reads it. Does it know a stack
command? No — model selection is a loop concern, not a project binding. Does it
make a stated guarantee enforceable? Partially — "cheap tasks get a cheap
model" is not a guarantee `tdd-implementer` states today, so there is nothing
yet to enforce; this candidate would be creating the guarantee, not closing a
gap in an existing one. Does it get a team running faster? Yes, plausibly —
cost and latency per change, not correctness.

**Why not now.** Two reasons:

1. **Escalation needs a working failure signal first.** "The cheap tier turns
   out to need more" has no cheap, reliable detector today — a wrong guess
   either produces a worse commit (caught by `ci`/convention-review, but late)
   or stalls (ambiguous halt, indistinguishable from a hard task on any tier).
   Building tiering before escalation would ship the easy half and leave the
   half that actually protects quality for later, backwards from how every
   other gate in this repo has been built (oracle first).
2. **No calibration data yet.** Which tasks are "mechanical enough" for a
   cheaper tier is an empirical question this repo hasn't measured against a
   real task list. Guessing a heuristic now risks encoding a wrong one that a
   later change has to unwind.

**Promote when.** `tdd-implementer` (or a sibling) has run unattended on enough
real changes that a task-shape heuristic (file count touched, presence of an
oracle, docs-only vs. code) can be proposed with evidence instead of a guess,
and an escalation signal — even a crude one, like a second failed gate attempt
— exists to fall back on.

---

## Task batching — fewer, larger commits per change

**What.** Let a task list group several adjacent tasks into one gate-and-commit
cycle, running `ci`/convention review once for the batch instead of once per task —
field issue #13's third cost-reduction suggestion, alongside the inline-review fix
and the scoped-gate fix `scale-gate-cost` already ships.

**Why it is a good fit, on paper.** It would cut wall time further: #13 measured
2–4 minutes of gate time per task, 2+ runs per task, 8–17 tasks per change — batching
N tasks into one gate-and-commit would divide that by roughly N.

**Against the rejection test.** Does it author an artifact? No — task granularity is
already authored by the OpenSpec schema (axis B), not gatedloop. Does it know a stack
command? No. Does it make a stated guarantee enforceable? No — if anything it
*weakens* one: `agents/tdd-implementer.md` §2's guarantee is **done ⟺ committed**, a
task's `[x]` flip lands in the same commit as its code, and batching several tasks'
flips into one commit blurs which specific task a given diff hunk belongs to,
degrading resumability's precision (a halt mid-batch can no longer point at "the
first `[ ]`" as cleanly as one task, one commit does today). Does it get a team
running faster? Plausibly, but the same win already shrank once the other two
`scale-gate-cost` changes landed: scoped `ci`/`unit` already cuts the per-task gate
run to what the task actually touched, and delegated review already keeps rules
prose and diff text out of the loop's own context. Batching's *remaining* marginal
benefit — fewer subagent spawns, fewer marker/ledger round-trips — is real but
smaller than it was when #13 was filed, against a real cost to the resumability
invariant this repo has built four other things (markers, the durable ledger, task
baselines, the `Stop` hook) specifically to make trustworthy.

**Why not now.** Two reasons, in order of weight:

1. **It blurs done ⟺ committed.** `scale-gate-cost` and everything before it treats
   "one task, one commit" as load-bearing — the `Stop` hook's continuation check, the
   reflog audit's taint join, and a halted run's own resumption all key off "the
   first unchecked task, at a clean tree boundary" being unambiguous. A batch changes
   what "boundary" means mid-flight, and that redefinition deserves its own design
   pass, not a rider on a cost-cutting change already shipping two other mechanisms.
2. **Task granularity is axis B's, not this repo's, to change unilaterally.** How
   many tasks a change has, and how finely they're split, is decided when the schema
   authors `tasks.md` (OpenSpec's job). A batching *mechanism* in the loop is fine to
   build, but it should be driven by something the schema states (e.g. a task grouped
   under one heading, or an explicit `batch:` marker) rather than a heuristic the loop
   invents on its own — and no schema states that today.

**Promote when.** A schema (upstream or one of the two gatedloop authors,
`bugfix`/`architecture`) states task grouping explicitly, AND the shrinking-benefit
argument above no longer holds — e.g. field data after `scale-gate-cost` ships shows
per-task gate/review cost is still the dominant driver even with scoping and
delegation in place, not batching's absence.

---

## Standing guardrail gate slots — `perf`, `a11y`, `security`, `design-system`

**What.** Four more optional, stack-blind gate names in the contract, each attachable
to surfaces and blocking when declared; onboarding asks about each category and
records a decline as `declined` rather than leaving it silently absent; the acceptance
brief lists their verdicts; `gates stats` counts the regressions they caught. Field
issue #30.

**Why it is a good fit.** The mechanism already exists — surfaces select rules and
live-checks from the changed files, deterministically, on every commit — and it is
category-agnostic. What is missing is only that these four categories are never
*offered*: they appear in no template, no onboarding question and no SETUP section, so
an adopter gets them only by thinking of them unprompted. Naming the slots turns "you
could bind a performance budget" into a question the plugin asks.

**Against the rejection test.** Authors no artifact. Names no stack command — the
slot is a name, the adopter binds it. Does it make a stated guarantee enforceable?
Partly: a declared slot is blocking, which is more than a convention rule an LLM reads.
Does it get a team running faster? Yes, in the way onboarding does — by asking the
question. It passes.

**Why not now.** Two reasons:

1. **No field pressure yet.** No trial repo has asked for a named slot; every adopter
   who wanted a budget folded it into `ci` or a surface's `live-check`, which already
   works. A slot's value is the *conversation* at onboarding, and that conversation is
   worth having once the loop's own metric (`gates stats --outcomes`,
   `escalation-outcomes`) can show what a missing guardrail cost.
2. **The onboarding half is the real work, and onboarding is mid-flight.** Adding four
   names to the contract is a schema edit. Asking about them well — detecting likely
   existing commands, recording a decline, not turning `gates-init` into a
   questionnaire — is design work on a surface `workflow-packs` is also reshaping.
   Land that first so the questions are asked once, in one flow.

**Promote when.** `workflow-packs` has landed and a trial repo has either asked for a
named guardrail or shipped a regression that a declared perf/a11y/security gate would
have caught — at which point the slot has a motivating incident, not just a category.

## Split this repository's over-long requirements

**What.** OpenSpec 1.14.1 limits a requirement to 500 characters under `--strict`.
16 of this repository's 19 specs fail that check, 55 requirements in all. Split each
into requirements short enough to pass.

**Why it is a good fit.** Strict validation is the cheapest check that a spec stays
readable, and a repository that ships a loop should pass its own strictest check.

**Why not now.** It is repo-internal: adopters never validate gatedloop's specs, and
the loop runs non-strict validation. It is also large spec-authoring work that should
be its own reviewed change, not a side effect of a compatibility patch
(`openspec-1-14-compat`, design D7).

**Promote when.** A release is otherwise quiet, or CI starts running `--strict`.

## Read archived changes through `openspec list --archived --json`

**What.** Use `openspec list --archived --json` for archive lookups
(`scripts/release status`, `epic-linkage`), instead of reading
`openspec/changes/archive/` directly.

**Why it is a good fit.** It follows OpenSpec's own resolution of where a change
lives (stores, planning homes) rather than assuming a path.

**Why not now.** The direct read works on every OpenSpec version, and the flag would
raise the minimum version gatedloop needs. Waiting keeps that minimum where it is.

**Promote when.** gatedloop raises its minimum OpenSpec version for another reason, or
an adopter's archive lives somewhere the direct read cannot see.

## Requirement names from `openspec show --json`, and `openspec version --check --json` in doctor

**What.** Two small uses of OpenSpec 1.14 output:
- the acceptance brief takes requirement names from `openspec show --json` rather
  than parsing spec headings;
- `gates doctor` reports "an OpenSpec update is available" from
  `openspec version --check --json`.

**Why it is a good fit.** Both read a fact from the tool that owns it instead of
re-deriving it.

**Why not now.** Both are useful, but neither is needed now: the heading parse works,
and doctor already warns when the installed version differs from the tested one.

**Promote when.** The brief's heading parse breaks on a real spec, or adopters ask
doctor to say when an update is out.

## A tamper-evident ledger

**What.** Chain each ledger row to the previous one with a hash, and let `gates marker
publish` carry the chain head, so a row edited or removed after the fact is detectable
at the merge and at the forge. Seen in the 2026-10-22 survey as signed, offline-verifiable
tool-call receipts in a governance plugin.

**Why it is a good fit.** The merge gate, the outcomes view and the attested approvals
all trust `.gatedloop/runs/*.jsonl`, a tracked plain-text file any agent can edit.
Publishing the chain head as a status would let the forge refuse a rewritten history
the same way it refuses an unpublished tree.

**Against the rejection test.** Authors nothing, names no stack command, makes a
stated guarantee (the ledger is the record) enforceable.

**Why not now.** The agent that can edit the ledger can also recompute the chain;
the guarantee only holds once the chain head leaves the machine, which is pull-request
mode only. Wait for a second host or a second adopter in pull-request mode to ask.

**Promote when.** An outcomes report is disputed, or a tainted change is found with
its taint row missing.

## `gates task revert <N.M>`

**What.** Revert one task's atomic commit (code, checkbox and ledger row together) and
record a `revert` row, so a rejected increment can be unwound at task granularity.
Seen in the survey as a per-task revert in a context-driven workflow tool.

**Why it is a good fit.** Done ⟺ committed makes a task's commit a clean unit to
revert; nothing else in the loop can undo a task without a human `git revert` that
leaves the checkbox and the ledger inconsistent.

**Against the rejection test.** Authors nothing, names no stack command, moves a human
turn (undoing a task) into the loop's own vocabulary.

**Why not now.** No halt cause or acceptance verdict asks for it yet; a rejected
acceptance today restarts the change. Promote when a `reject` with a named task
becomes a recorded pattern in `gates stats --outcomes`.
