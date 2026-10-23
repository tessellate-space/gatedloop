---
name: "Gates Init"
description: Bootstrap gatedloop into this project in one guided command — doctor preflight, OpenSpec CLI + init, gate binding, conventions capture, permission scaffolding, git-layer commit enforcement, the remaining adoption settings, validate + ci.
category: Workflow
tags: [workflow, setup, onboarding]
---

Onboard the current project onto gatedloop in **one guided command**, covering the whole prerequisite chain rather than assuming most of it is already in place: it runs a doctor preflight, ensures the OpenSpec CLI and `openspec init --tools claude`, binds gates, captures conventions, offers permission scaffolding, then validates. The deliverable is the project's **seam** — the single `.gates.yaml` manifest plus the rules-doc it references. This is a guided fill-in-the-blanks, not a rewrite of the project, and every new step is decline-able so a project already set up moves through quickly.

**Goal**: after this command, `gates validate` passes and the project is ready for `/opsx:propose` (OpenSpec authors the artifacts) → `/gatedloop:tdd-apply` (gatedloop runs the loop).

---

## Steps

### 0. Doctor preflight
Before anything else, run the onboarding preflight — it names the reachable ways a
session can be half-wired before onboarding trips over one:
```bash
gates doctor
```
It is **advisory** (design D3/D4): it reports the OpenSpec CLI's presence and version
(against the contract version the shim was tested with — F5), whether any existing
`.gates.yaml`'s `gatesVersion` is current, and whether the plugin looks registered
for this session — and it **never blocks**. A version-drift warning is a heads-up,
not a failure; read the output and continue.

If `gates doctor` itself does not run — no `gates` command, no gatedloop session
brief, nothing at all — the plugin may be invisible under the active Claude Code
config profile, which no in-session command can diagnose (a command bundled in the
invisible plugin cannot report its own absence). That case is covered by SETUP.md's
`CLAUDE_CONFIG_DIR` troubleshooting note, run from a plain shell.

### 1. OpenSpec CLI presence
This is the first prerequisite the bootstrapper now covers itself rather than
assuming an adopter satisfied it by hand.

- Confirm this is a git repo. gatedloop's loop is built on per-change branches and
  gated commits — there is nothing to onboard without git. If it isn't one, say so
  and stop.
- If a `.gates.yaml` already exists, run `gates validate`; if valid, report and ask
  whether to keep or regenerate. Never clobber a valid manifest without confirmation.
- **Detect whether the OpenSpec CLI is installed.** gatedloop does not author
  artifacts — OpenSpec does — so its CLI is a hard prerequisite, not a convenience.
  Check for it without assuming it is there:
  ```bash
  openspec --version
  ```
  - **Present** → note the reported version (step 2 initializes with it, and step 0's
    doctor check compares it against the contract version the shim was tested against)
    and continue.
  - **Absent** (`command not found`, non-zero exit) → **offer to install it.** Naming
    the tool here is to *offer* it, never to invoke a project command — the same
    `stack-agnostic-prompts` carve-out that lets step 3 name task runners. The OpenSpec
    CLI ships on npm as `@fission-ai/openspec`; via the **AskUserQuestion tool**, offer
    to install it (`npm install -g @fission-ai/openspec`, or the adopter's own package
    manager if they prefer) and **wait for explicit confirmation** before running
    anything.
    - *Accepted*: run the install, re-check `openspec --version`, and continue.
    - *Declined*: report that gatedloop requires the OpenSpec CLI and that onboarding
      cannot proceed without it. **Stop without writing anything** — no `.gates.yaml`,
      no rules-doc, no partial configuration. A half-configured project is worse than
      an unconfigured one, because `gates validate` would then fail for a reason
      unrelated to the real problem.

### 2. Initialize OpenSpec — `openspec init --tools claude`
This step establishes a working OpenSpec + Claude Code integration rather than
assuming one. It absorbs the old preflight bullets that *checked* whether OpenSpec
was initialized and whether the authoring commands were present: both are really the
one question — "does this project have a working OpenSpec + Claude Code integration?"
— which this step now answers by running the initializer, not by stopping and telling
the adopter to run it by hand.

**First, guard against overwriting local edits — a stop-and-confirm gate, not a
warning that proceeds regardless (design D7).** `openspec init --tools claude` (like
`openspec update`) regenerates the files under `.claude/commands/opsx/` in place — no
backup, no prompt — so a re-run can silently overwrite edits an adopter made to them.
Before invoking it, check whether those generated files look locally modified:
```bash
git log --oneline -- .claude/commands/opsx/
```
More commits than the one that introduced them means someone edited them. If
`.claude/` is untracked, treat the check as inconclusive rather than reporting a pass.
- **Local edits detected** → **stop and require explicit confirmation before running
  `openspec init --tools claude`.** A warning the adopter can silently pass through
  does not satisfy this — require a real yes via the **AskUserQuestion tool**. In the
  same message, name the durable alternative: editing a generated file is not
  supported, and `openspec schema fork <source> <name>` produces the adopter's *own*
  file (which survives an upstream update by construction) instead of a regenerated
  one.
  - *Declined* → leave the existing generated files exactly as they are, and report
    which downstream steps cannot proceed as a result (the authoring-command
    completion check below depends on `openspec init` having run) rather than
    continuing in a half-consistent state.
  - *Confirmed* → proceed.
- **No local edits detected** → proceed without asking.

**Then run the initializer** (unless it was declined above):
```bash
openspec init --tools claude    # creates openspec/ AND .claude/commands/opsx/*
```
Running it is safe on a project that already has OpenSpec — it reconciles rather than
clobbers untouched files — which is why first onboarding runs it (subject only to the
gate above) instead of first testing whether OpenSpec was already initialized and
stopping if not.

**Completion condition — confirm the authoring half is really there.** OpenSpec
authors the artifacts gatedloop's loop consumes; confirm the specific commands the
prompts name actually resolve, not merely that a directory exists (adopters
legitimately prune commands they have replaced):
```bash
for c in explore propose apply sync archive; do
  [ -f ".claude/commands/opsx/$c.md" ] || echo "missing: /opsx:$c"
done
```
- **All five present** → the integration is complete; continue to gate binding.
- **Any missing** → name exactly which, and report that the loop's prompts would
  point at commands that do not resolve. If `openspec init` was declined above, this
  is the expected consequence of that decline; otherwise re-run it and re-check. Do
  not write a `.gates.yaml` while the authoring half is incomplete.

### 2b. Select workflow schemas
`openspec/config.yaml`'s `schema:` defaults to `spec-driven` from step 2 — fine for
most projects, but not the only shape available. Invoke the **`workflow-select`
skill** here rather than repeating its procedure: it presents the bundled default,
the community catalog, and gatedloop's own `bugfix`/`architecture` packs, installs
whatever is chosen, and discloses the upstream-drift limitation at install time.
Declining is a complete, first-class outcome — most projects keep `spec-driven` and
move on immediately.

This same capability is reachable on its own at any later point (a team does not
need to re-run onboarding to add a workflow once the need for it shows up) — this
step is onboarding *calling* it, not the only place it lives.

### 3. Detect the task runner
This is a **curated detector list** — a convenience for the common cases, not a
supported-stack list. Naming these tools here is compatible with
`stack-agnostic-prompts`'s carve-out because they are named to be **offered**,
never to be invoked: nothing below runs a command, and no name here is written
into `.gates.yaml` except through the adopter's explicit confirmation in step 5.
A project that matches none of these rows is expected, not unsupported — Non-goals
in this change's proposal are explicit that breadth was never the point.

| Marker file | Tool | Suggested gate body |
|---|---|---|
| `justfile` | `just` | `just <recipe>` |
| `package.json` (with a `scripts` block) | `npm` | `npm run <script>` |
| `Makefile` | `make` | `make <target>` |
| `Cargo.toml` | `cargo` | `cargo <cmd>` |
| `pyproject.toml` / `noxfile.py` / `tox.ini` | the matching Python runner | `<runner> <target>` |

Scan for every marker present — do not stop at the first hit and do not rank
them; ranking implies a preference the adopter hasn't stated. Report exactly
what you found: zero markers, one, or several. **Detecting is not deciding** —
which candidate (if any) gets bound is step 5's question, not this one, and
that holds even when exactly one marker is found.

**Zero markers has two very different meanings — distinguish them now (design
D8).** Before treating "no curated match" as "ask the adopter to hand-write `ci`",
check whether there is anything to bind a gate *to* at all:

- **Unlisted stack, real project** — no marker from the table above, but there *is*
  source code and some existing build or run target (a language toolchain, a
  `Dockerfile`, scripts, a compile step — something a `ci` command could exercise).
  This is the expected common case, not a failure: it falls through to step 5's
  "ask outright, adopter writes the `ci` body by hand", and onboarding completes with
  a valid manifest exactly as before.
- **No scaffold at all** — no source files, no build markers, no run targets of any
  kind: an empty or near-empty directory where "what command builds and tests this?"
  has no honest answer because nothing exists yet to build or test. **Stop here.**
  Name precisely what is missing (no code to test, no target to run) and do **not**
  ask the adopter to invent a `ci` command, and do **not** write a `.gates.yaml`
  binding a fabricated one. A fictitious gate either fails `ci` permanently for
  reasons unrelated to code quality, or becomes a placeholder — the invented oracle
  this workflow refuses. `ci` being genuinely unbindable yet is not an onboarding
  failure; the adopter returns once a scaffold exists.

### 4. Discover candidate gates & surfaces
- Grep the runner's targets/scripts for likely gates: a test target (`unit`), an aggregate check (`ci`), an integration target, a spec/acceptance target (`verify`), a runtime smoke/e2e (`live-check`), an eval.
- Map top-level source areas to surfaces from the directory layout (e.g. `backend/**`, `frontend/**`, `**/agents/**`, or a single `**` catch-all for a monolith).
- **Identify the conventions doc.** It is **never** `openspec/config.yaml` —
  that file's own `rules:` key is a *generated* artifact-instruction block
  (see below), not a place to author rule-id prose; pointing
  `conventions.rules-doc` at it is the exact defect `reposition-gatedloop`
  fixed. Look for an existing standalone rules-doc (a file with `### <id>`
  headings) first. If none exists, offer to create `docs/conventions.md`
  from `${CLAUDE_PLUGIN_ROOT}/templates/rules-doc.template.md` — this is
  the default path, not a guess to re-ask each time, so it composes with
  the next bullet without a name collision.
  Identifying the doc is all this step does with it; **step 6** (conventions
  capture) is where its content is harvested, confirmed, written, and synced.

### 5. Confirm the bindings WITH the user — don't guess silently
Drop a starter file (`gates init`) then fill it *interactively*. For anything you can't confidently detect, **ask — do not leave a `# TODO` for a gate the loop will need**:

- **Gates.** Present **every** candidate found in step 3 — including when there is
  exactly one — via the **AskUserQuestion tool**, alongside a "none of these — I'll
  write it myself" option. Never bind a candidate automatically, not even the sole
  one detected: a marker is an offer, not a decision, and only the adopter's
  confirmation turns it into a binding. Always resolve `ci` (required) to a real
  command before finishing — if nothing was detected, or every candidate is
  declined, ask outright: "What single command builds + tests this project (the
  pre-commit gate)?" and let the adopter write it by hand. That path — declining
  every candidate and supplying the gate body directly — is a first-class outcome,
  not a fallback; onboarding reaches a valid manifest either way. Only include
  `unit`/`integration`/`verify`/`eval` when the user confirms a real target —
  **omit** (don't fake) the rest. When you bind `verify`, `integration` or a
  `live-check`, tell the adopter the bound command must fail on an undefined or
  skipped test and must not pass on retry; only their runner's configuration can
  honour that. Step 11 asks them to confirm it (the `runner-strictness` adoption
  item), so don't ask twice here.
- **Surfaces.** Show the proposed glob→area map and confirm it with the user (one catch-all `**` is a fine answer for a monolith). For each surface, confirm its `live-check` command (or that it has none) and which `rules` apply.
- **`confirm`, once any `live-check` is bound.** Offer the optional `confirm` gate via
  the **AskUserQuestion tool**: the command that brings the *merged* tree up on the
  project's own environment and smokes it, which `gates merge` runs as its step 5 before
  anything is pushed. Offer the adopter's existing bring-up/smoke command if step 3 found
  one, alongside "not now" and "I'll write it myself"; never bind one unconfirmed. Say
  that the environment it runs on, and whatever brings it up and down, stays theirs —
  put those steps in the command body or its `requires` precondition. If a freshly
  started environment flakes on its first scenario, offer an idempotent warm-up (one
  that exits 0 once the stack is warm) as that `requires`: it runs before the verdict,
  so it is not a retry of a failure. Declined, omit it:
  step 5 is then skipped with a note, which is not a failure. `/gatedloop:upgrade` runs
  this same offer for the `confirm-gate` item.
- **Rules.** If the conventions doc has addressable ids, list them and let the user pick per surface. If it's fresh from the template (no real ids written yet), do **not** reference a placeholder id — an undefined id fails `gates validate` loudly, which is the exact defect this generation flow exists to avoid. Use inline prose instead (the documented escape hatch for "no addressable rules-doc yet"), and note that switching to rule-ids is a later edit once the conventions doc has real content.

Write the confirmed values into `.gates.yaml` — real commands, not placeholders. The only acceptable `# TODO` is an *optional* gate the user explicitly deferred.

### 6. Conventions capture — harvest, confirm, wire, sync
Conventions are a **core** onboarding step, not an optional extra an adopter
discovers is missing later. A freshly generated rules-doc has no addressable
`### <id>` rules, so convention review has nothing checkable to enforce until
someone fills it in by hand, unprompted (the exact gap the field run found). This
step closes it up front — from material the project already has, with the adopter
confirming every entry. It runs on **every** onboarding pass, not only when asked.

- **Harvest candidate rules from existing material.** Read, where present:
  - contributing guides (`CONTRIBUTING.md`, `docs/contributing*`);
  - agent instruction files (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules`, and similar);
  - linter / formatter configuration (`.eslintrc*`, `ruff.toml`, `.editorconfig`, a
    `[tool.*]` block in `pyproject.toml`, …) — read as *evidence of a rule*, never to
    invoke the tool;
  - an existing OpenSpec project's `openspec/config.yaml` `context:` block — per FR3,
    real checkable conventions (a components-library-first UI rule, an auth-client
    rule, a query-key naming convention, …) frequently already live there unharvested.
- **Draft candidate rule-doc entries** from what you find. Each is a `### <id>`
  heading, an `Applies to:` line **defaulting to `code`**, a `Rule:` one-line
  imperative, and prose taken or summarised from the source. Default `Applies to:
  code` rather than guessing an artifact id: `code` is always safe (every rule is at
  minimum a convention-review input), and promoting a rule to also govern authoring
  is a real content decision — which artifact ids, and whether the rule is about
  authoring at all — that the adopter makes, not the bootstrapper.
- **Present each candidate to the adopter before writing anything** (AskUserQuestion)
  — the same "ask, don't guess silently" discipline that governs gate and
  integration-process bindings. Extraction is lossy (a prose paragraph is not an
  imperative one-liner), and a wrongly-summarised rule is worse than no rule, because
  `gates validate` will validate it and convention review will cite it as
  authoritative.
- **Then a test-conventions pass.** The test author works from these rules, and so
  does the reviewer: `gates tests brief` hands the author every rule tagged
  `Applies to: tests`, and `gates rules` lists them for every diff. A project with
  none gets tests that are technically clean but foreign to it. From the same
  material (plus the layout of the existing test tree — paths and names only),
  draft `Applies to: tests` candidates covering:
  - where tests live, and how they are named;
  - the shared fixtures and factories, by path, that new tests should build on;
  - what may be faked and what must be real;
  - which layer owns which behaviour (unit, integration, acceptance);
  - how the bound runner treats an undefined or skipped test, and retries.

  Confirm each with the adopter exactly as above; write only what they confirm.
  `tests` is a review-only target like `code` — `gates conventions sync` never emits
  it, and it needs no surface wiring, because `gates rules` includes it whatever
  surfaces are hot.

  **Record the answer here** (it is the `test-conventions` adoption item):
  `gates adoption record test-conventions adopted` once at least one `Applies to:
  tests` rule is written, or `gates adoption record test-conventions declined` when
  the adopter declines every candidate or there was nothing to draft and they don't
  want to write one now. `/gatedloop:upgrade` runs this same pass when the item is
  adopted later; the pass is the only copy.
- **No harvestable material?** Say so plainly and complete the step **without writing
  placeholder content** — an honest empty rules-doc (or none) beats invented rules.
  Convention review then falls back to inline prose per surface (step 5), and the
  adopter can add addressable rules later.
- **Write only confirmed entries** into the rules-doc step 4 identified or created,
  then wire the confirmed ids into `.gates.yaml`'s `surfaces[].rules` for the
  surfaces the adopter selects.
- **Then run `gates conventions sync`** and re-run `gates validate` to confirm no
  drift. This is **one source, two projections** — *not* one source feeding two
  consumers the same content:
  - the rules-doc **entire and unfiltered** is what `convention-review` reads, via
    `.gates.yaml`'s `conventions.rules-doc` → `gates rules` (a path that never
    touches `openspec/config.yaml`);
  - only the **subset** of rules whose `Applies to:` line names a real artifact id
    from the active schema is projected by `gates conventions sync` into
    `openspec/config.yaml`'s `rules:` block.

  A rule scoped `Applies to: code` is **correctly absent** from that second
  projection — not a defect, not something sync failed to deliver: no OpenSpec schema
  (bundled `spec-driven` or any community schema) has an artifact-authoring
  destination for a rule with no artifact id (an `apply` block cannot carry rules). A
  sync that finds only `code`-scoped rules is a legitimate no-op, not a gap to fix
  later.

### 7. Ask how a change reaches main
`tdd-apply`'s completion step assumes a local squash-merge; not every project's
`main` allows that — some require a pull request, some require an approved one.
Ask before assuming, the same rule as the gates above.

- **Detect a default, don't bind one.** Where the evidence exists — an `origin`
  remote is configured, `gh` reports required reviews on the default branch, or
  the branch's own history looks PR-shaped (merge commits, `Merge pull request
  #…`) — note which preset that evidence points at. Detection only decides which
  option is offered *first*; on its own it writes nothing.
- **Ask with the AskUserQuestion tool**, presenting these preset options (the
  detected default, if any, promoted to the top — never auto-selected):
  - local squash-merge — today's behavior; the loop merges directly at
    change completion
  - pull request — the loop opens a PR; no approval required to merge
  - pull request with required approval — the loop opens a PR and waits for
    an approving review before merging
- **Record the confirmed choice**, never the detected guess unless the adopter
  confirms it, in `.gates.yaml` as an `integration:` block:
  ```yaml
  integration:
    mode: pull-request      # local-squash-merge | pull-request
    requireApproval: true   # only meaningful when mode is pull-request
  ```
  Omitting `integration:` entirely is also valid and means today's behavior
  (local squash-merge); `gates validate` accepts a manifest with or without it.
- This step only asks and records the choice, and `tdd-apply`'s completion step
  and the loop-enforcement hooks now consume it (`harden-unattended-loop`).

### 8. Ask who approves plans
Every change's plan must be merged and approved before implementation starts
(`gates discipline check-implement`, design D10). Today that approval comes from a
PR's `APPROVED` review — the right default, but a hard requirement in a solo,
remoteless repo where no second party can leave one. Ask, beside the integration
question above, rather than leaving a solo adopter to hand-edit the keys the D12
sha-pin exists specifically to catch (`solo-approval-mode`, #3/#21).

- **Ask with the AskUserQuestion tool**, presenting these preset options (neither
  auto-selected — a remote's absence or presence is a hint, not a default to bind
  silently):
  - a second party reviews and approves each plan (`review`, today's default) —
    `gates approval attest <change> --pr <n>` reads the PR's actual `APPROVED`
    review; the model never supplies the value
  - I approve my own plans (`self`) — `gates approval attest <change> --local`
    computes the same content-pinned hash and records your configured git
    identity; an edit after attestation still invalidates it exactly as under
    `review`
- **Record the confirmed choice** in `.gates.yaml` as an `approval:` block, only
  when the adopter answers:
  ```yaml
  approval:
    plan: self   # or: review
  ```
  Declining the question writes nothing — the block stays absent, and the
  effective policy is `review`, exactly as if it had been declared explicitly.
- **Name the approval step in the closing summary** for whichever policy is
  recorded: under `self`, the solo procedure is `gates approval attest <change>
  --local`; under `review` (or no answer), it's opening a PR and getting an
  `APPROVED` review before `gates approval attest <change> --pr <n>`.
- This step only asks and records the choice; the writers (`gates approval attest
  --local`/`--pr`) and the D10 gate itself (unchanged — it never reads this block,
  only the keys the writers produced) are `solo-approval-mode`'s scope, not this
  command's.

### 9. Offer permission scaffolding (opt-in, personal)
An unattended run stalls at the first permission prompt and sits there until someone
returns (`AUTOMATION.md` §3). Ask — **do not write anything without an explicit yes**:

- **Ask with the AskUserQuestion tool**: "Scaffold permissions for the loop's own
  vocabulary, so an unattended run doesn't stall on a prompt? (`gates merge`, the
  command that integrates, will still always ask.)" — yes / no.
- **On yes**, write to **`.claude/settings.local.json`** — never the shared
  `.claude/settings.json`; this is personal, gitignored, per-developer (design D4). A
  plugin must not silently broaden a repo's permission surface for everyone. Merge with
  any existing content in that file rather than overwriting it:
  ```json
  {
    "permissions": {
      "allow": ["Bash(gates *)", "Bash(openspec *)", "Bash(git commit *)"],
      "ask": ["Bash(gates merge *)"]
    }
  }
  ```
  The `ask` rule on `gates merge *` is deliberate, not an oversight: it encodes
  `tdd-implementer`'s "STOP BEFORE THE MERGE" as an enforced human checkpoint that
  survives even an auto/accept permission mode — an `ask` rule is evaluated before an
  `allow` rule and before the auto-mode classifier, so it prompts even under the broad
  `Bash(gates *)` allow. It sits on `gates merge`, not on every `git merge`, because
  that is where integration happens: `gates merge` integrates locally, the forge does
  it under pull-request mode, and the merge hook still gates a raw integration `git
  merge` into the target. An `ask` on every `git merge` would also prompt on a lane's
  routine sync of the target into its own change branch; an unattended lane has no one
  to answer it, so it stalls there. Then add `settings.local.json` to
  `.gitignore` **if it isn't already covered** (check for a `.claude/` or
  `settings.local.json` pattern before appending, so this doesn't duplicate an existing
  rule).
- **On no**, write nothing — leave any existing permission files exactly as they are.

### 10. Offer git-layer commit enforcement (opt-in, default-yes)
The `PreToolUse` commit gate matches the Bash tool's command *string*, so a commit
created through indirection — a Python subprocess, a written-then-run script, a git
library — slips past it (observed in the field: issue #2). A git `pre-commit` hook
fires on the commit *object* itself and catches every path, running the same
`gates discipline check-commit` as the `PreToolUse` gate (an O(1) compare, never a `ci` run). Offer to install it, defaulting toward yes (an
adopter who installed the enforcement plugin presumably wants the enforcement), but
never install it silently — the same consent pattern as the permission step above.

- **Ask with the AskUserQuestion tool**, **default-yes**: "Install the git-layer commit
  hook, so an agent can't route around the commit gate through a subprocess or script?
  It enforces only inside a Claude Code session — your own terminal, your IDE, and CI
  are unaffected." — yes (default) / no.
- **On yes**, run:
  ```bash
  gates hook install
  ```
  It detects who owns the hook path (husky, lefthook, the pre-commit framework, a
  `core.hooksPath` redirect, or a bare `.git/hooks/pre-commit`) and **composes** the
  check in where it safely can, **refusing-and-instructing** where it cannot — it never
  clobbers an existing hook. The one file it replaces is its own: a direct copy of an
  earlier (or locally edited) gatedloop template is **refreshed** to the shipped one,
  with the old body saved as `pre-commit.gatedloop-prev` beside it, and the output names
  both paths. This is also the step `/gatedloop:upgrade` runs for the `git-hook-refresh`
  item. Report its result verbatim: a clean install or compose
  exits 0; a refusal exits non-zero and prints the exact block to add by hand — relay
  that block rather than treating onboarding as failed. A refusal is "wire it yourself,"
  not "onboarding broke."
- **On no**, install nothing — leave `.git/hooks` and any hook manager's config exactly
  as they are — and continue. Onboarding still completes normally; the tool-invocation
  hook and the post-hoc reflog audit (`AUTOMATION.md`) remain in force regardless.

Naming husky/lefthook/pre-commit here is **detection, not invocation** — the same
`stack-agnostic-prompts` carve-out as step 3's task-runner list: they are named so the
installer can compose *with* them, never run as a project command.

### 11. Decide the remaining adoption settings
gatedloop ships a catalogue of settings each project should choose deliberately
(acceptance before merge, who writes the tests, runner strictness, a local schema's
flow, …). Steps above that correspond to an item already recorded their answer, and
any setting already written to `.gates.yaml` counts as decided. Now run the
**`/gatedloop:upgrade` walk** over whatever is still undecided, rather than repeating
its procedure here. It asks one question per item, recommended answer first, plus
"Decide later", and records each answer with `gates adoption record` as it is given.
If `gates adoption status` lists nothing, it says so and asks nothing.

A freshly onboarded project therefore leaves with every current item decided or
deferred, and the session brief carries no adoption line. Name
`.gatedloop/adoption.json` in the closing summary as a file to commit with the
manifest: it is how the whole team shares these decisions.

### 12. Validate, run `ci` once, and report
```bash
gates validate
```
- If it fails (missing required gate, dangling rule-id, missing rules-doc), show the errors and resolve each **with the user** (loop back to step 5 for the offending field) — never hand back an invalid manifest.
- On success, **run the `ci` gate once** (`gates run ci`) and report its exit
  code — do not stop at "the manifest is valid." Validity means the gate is
  *bound*; it says nothing about whether the project can currently *pass*
  it. Observed live: a real project's freshly bound `ci` was already red (a
  BDD recipe missing its codegen step), `gates validate` passed, and the
  onboarding report said nothing about it — so the first sign of trouble
  was `/gatedloop:tdd-apply` refusing to commit a single task, with no
  connection back to cause.
  - **`ci` passes** → report the exit code and move to the next-steps note
    below.
  - **`ci` fails** → this is **not** an onboarding failure — binding a gate
    the project cannot yet pass is legitimate and common, often exactly why
    someone is adopting gatedloop. Report it plainly instead of staying
    silent: show the failing command's output, state that `/gatedloop:tdd-apply`
    will refuse to commit until `ci` is green, and that this is expected
    and does not block finishing onboarding.
- Print the final manifest and a short next-steps note:
  > `.gates.yaml` is valid. Run `/opsx:propose <change>` to author a change, then `/gatedloop:tdd-apply` to run the loop.

## Guardrails
- Never invent a gate command that doesn't correspond to a real target — leave it as a `# TODO` for the user rather than a command that will fail at gate time.
- `ci` is the only required gate; everything else is optional and should be omitted (not faked) when absent.
- Do not modify application code, the task runner, or existing rules — only create `.gates.yaml` and, if the user agrees, a starter rules-doc.
- Never bind a detected task-runner candidate without the adopter's explicit confirmation, even when step 3 found exactly one. Detecting is offering; only the adopter's answer decides.
- Never bind a detected integration-process default without the adopter's explicit confirmation. The same rule that governs gate candidates governs this one.
- Never write permission rules without an explicit yes, and never write them to `.claude/settings.json` — only `.claude/settings.local.json`, which is personal and gitignored (design D4).
- Never install the git-layer commit hook without an explicit yes (default-yes, but still asked). `gates hook install` is the only thing that touches `.git/hooks` or a hook manager's config, it never clobbers, and a decline leaves onboarding able to complete normally.
