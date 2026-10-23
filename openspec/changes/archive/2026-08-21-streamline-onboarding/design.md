## Context

`commands/gates-init.md` today runs six steps, all downstream of "OpenSpec is
already initialized": preflight (confirm git repo, confirm OpenSpec, confirm the
authoring commands, warn once on locally-modified generated files), detect the task
runner, discover candidate gates & surfaces, confirm bindings with the adopter,
ask how a change reaches `main`, validate + run `ci` once + report. `onboarding-asks-first`
built the "ask, don't pick" discipline into every one of those steps. What it did not
do — and what `docs/review-2026-08-18.md` F6 names as the residue — is extend the
command backward to cover the prerequisites that today have to be satisfied by hand
before `gates-init` is even reachable: installing the OpenSpec CLI and running
`openspec init --tools claude`.

`harden-unattended-loop` D4 already designed a permission-scaffolding step for
`/specloop:gates-init` (offer `.claude/settings.local.json`, opt-in, never the
shared `settings.json`). Both changes touch the same file. `harden-unattended-loop`
is in flight now; this change lands after it, per the review's recommended sequence
(`fix-change-scope-selection` → `onboarding-asks-first` → `harden-unattended-loop` →
`streamline-onboarding` → `workflow-packs`).

## Goals / Non-Goals

**Goals:** collapse the six manual prerequisites into one guided command triggered
at the first session inside a project; make conventions capture a core step instead
of a silent gap; state the FR5 boundary explicitly; close the FR4 overwrite gap with
a real confirmation gate; probe the OpenSpec contract (F5) instead of assuming it;
diagnose the invisible-install failure; preserve and clarify the no-scaffold-stop
behaviour.

**Non-Goals:** permission-scaffolding design (owned by `harden-unattended-loop` D4);
authoring any artifact; naming a stack command in order to invoke it; a
package-manager detector database; schema acquisition or pack inspection
(`workflow-packs`); a code-level guard against `openspec init`'s overwrite behaviour.

## Decisions

### D1: This change lands after `harden-unattended-loop`, and absorbs D4 rather than being rebased onto

Both changes edit `commands/gates-init.md`. `harden-unattended-loop` D4 adds one
step (permission scaffolding, opt-in) to the command as it exists today; this
change restructures the whole command around a new step order. Doing D4 first and
then restructuring around it means one rewrite; restructuring first and then
grafting D4 on afterward means harden would have to rebase its design onto a
command this change already changed underneath it — the same rewrite, done twice,
by two different changes.

**Decision:** `harden-unattended-loop` lands first, unmodified. This change absorbs
its permission-scaffolding step into the new step order at implementation time (see
D2's step 6) rather than harden rebasing onto a command this change has already
rewritten. `harden-unattended-loop`'s own design and tasks are untouched by this
change — D4 stays that change's decision; this change only changes where in the
restructured command its already-designed step runs.

**Rejected alternative:** land `streamline-onboarding` first, have harden graft its
step onto the new structure. Rejected because `harden-unattended-loop` is already in
flight (proposal committed, tasks not yet started) and the review's own recommended
sequence already places it before this change; reopening that ordering would stall
work already underway for no benefit — the file collision is the same size either
way, and harden getting there first means this change's authors design against a
finished D4 rather than a moving one.

### D2: The bootstrapper's step order

**Decision:** `commands/gates-init.md` is restructured into:

0. **Doctor preflight** (D3) — a `gates doctor` check for whether Specloop itself is
   reachable in this session, run automatically, before anything else.
1. **OpenSpec CLI presence** — detect whether the OpenSpec CLI is installed; if not,
   offer to install it (naming the tool to offer it, not to invoke a project
   command — compatible with `stack-agnostic-prompts`' carve-out, which already
   covers "name to offer, not to bind").
2. **`openspec init --tools claude`**, gated by the FR4 confirmation check (D7) —
   today's "existing OpenSpec initialized" and "authoring half installed" preflight
   checks fold into this step, since both are really asking "does this project have
   a working OpenSpec + Claude Code integration," which this step now establishes
   rather than assumes.
3. **Detect-and-confirm gate binding** — today's steps 2–4, unchanged in behaviour
   (`onboarding-asks-first` already did this work); the no-scaffold-stop case (D8)
   is made explicit here.
4. **Conventions capture** (D5) — promoted from "mention it, don't run it
   unprompted" to a core step that harvests, presents, confirms, and syncs.
5. **Integration process ask** — today's step 5, unchanged.
6. **Permission scaffolding** — `harden-unattended-loop` D4's step, absorbed here
   per D1.
7. **Validate, probe the contract version (D4-F5), run `ci` once, report** — today's
   step 6, extended with the version-mismatch warning.

**Rejected alternative:** keep OpenSpec-CLI-install and `openspec init` as a
separate command from gate binding (e.g., a `/specloop:openspec-init` run before
`/specloop:gates-init`). Rejected because it reintroduces exactly the "six manual
steps" problem this change exists to close — an adopter would still have to know to
run two commands in order, and the `SessionStart` hook can only point at one thing.

### D3: The invisible-install diagnostic is a doctor preflight inside the bootstrapper, plus a manual fallback — not a standalone command

`docs/candidates.md`'s `gates doctor` entry recommends folding this into whichever
change opens the bootstrapper, rather than standing alone. Upstream already ships
`openspec doctor`, which reports OpenSpec **root relationship health** (specs/changes
consistency) — a different failure class from the one F6 item 7 names: Claude Code
supports multiple config profiles via `CLAUDE_CONFIG_DIR`, and a plugin installed
under one profile is entirely invisible under another — no commands, no skills, no
session brief, no error.

**The mechanism has a hole that has to be named, not hidden:** if the plugin is
truly invisible under the active profile, no command bundled in that plugin —
including a `gates doctor` command — is reachable to diagnose it. A preflight step
inside `gates-init` can only run once `gates-init` itself is reachable, which is
precisely the condition that fails in the worst case of this failure class.

**Decision, in two parts, closing both symptom classes:**

1. A `gates doctor` shim subcommand, run automatically as `gates-init`'s step 0,
   covers the *partially*-visible states — commands registered but hooks stale
   (needs a new session), OpenSpec CLI missing, `gatesVersion` mismatch, the F5
   contract-version mismatch (see the next decision). This is the common case: the
   plugin loaded, something downstream of it did not.
2. For the *fully*-invisible state, no in-session surface can diagnose its own
   absence — the fix is documentation, not code. `SETUP.md` gets a troubleshooting
   note naming `CLAUDE_CONFIG_DIR` as the first thing to check when no Specloop
   command, skill, or session-brief output appears at all, with the check a human
   runs from a plain shell (`echo $CLAUDE_CONFIG_DIR`, then confirm the plugin is
   registered under that profile) — independent of whether any Specloop surface is
   reachable.

**Rejected alternative:** a standalone `/specloop:doctor` command. Rejected for the
same reason as (2) above — a slash command bundled in the plugin cannot diagnose the
plugin's own total invisibility, so a standalone command would only ever be reachable
in the cases `gates-init`'s step 0 already covers, adding a second surface for no
additional coverage. `docs/candidates.md`'s own promotion criterion ("fold this in as
one of its checks rather than opening a separate change for it") is satisfied by
folding into `gates-init`, not by a new command.

### D4: The F5 contract-version probe lives in the doctor check

**Decision:** the shim records the OpenSpec CLI version it was last verified
against as a constant it can check. `gates doctor` (D3) compares it to the installed
`openspec --version` and warns loudly — not a hard failure — on mismatch, since a
version drift in a pre-1.0, fast-moving CLI is not guaranteed to break the contract,
only to make it worth a second look. The warning names what changed if discoverable
(e.g., `openspec schemas --json`'s shape) and points at re-running `gates doctor`
after an `openspec update`.

**Rejected alternative:** fail `gates validate` hard on a version mismatch.
Rejected because `fail-loud-gates` is about validation and marker/gate checks that
have a definite right answer (a dangling rule-id, a missing required gate); an
unpinned upstream CLI's version drift does not have one — it may still work
perfectly. A hard failure here would block onboarding on a signal that is
informative, not conclusive, which is a worse failure mode than the silent-assumption
status quo it replaces.

### D5: Conventions capture — sources, mechanism, and the ask-first discipline

**Decision:** the harvest step reads, in order: existing contributing/agent
instruction files (`CONTRIBUTING.md`, `CLAUDE.md`/`AGENTS.md`-shaped files), linter
or formatter configuration, and — per FR3 — an existing OpenSpec project's
`openspec/config.yaml` `context:` block. From each source it drafts candidate
rule-doc entries (an `### <id>` heading, an `Applies to:` line defaulting to `code`,
a `Rule:` one-liner, and the surrounding prose taken or summarised from the source).
It presents the drafted candidates to the adopter — matching the "ask, don't guess
silently" discipline `onboarding-asks-first` already established for gate and
integration-process bindings — and only writes confirmed entries into the project's
rules-doc. It then wires `.gates.yaml surfaces[].rules` for the surfaces that map to
harvested ids and runs `gates conventions sync`.

`Applies to:` defaults to `code` rather than guessing an artifact id, because `code`
is always a safe default (every rule is at minimum a convention-review input) and
promoting a rule to also govern authoring is a real content decision — which
artifact ids, and whether the rule is actually about authoring rather than code —
that the adopter, not the bootstrapper, should make.

**Rejected alternative:** auto-write harvested rules without confirmation, on the
grounds that they are extracted from material the project already committed to.
Rejected because extraction is lossy (a CONTRIBUTING.md paragraph is prose, not an
imperative one-liner) and the same "adopter confirms, bootstrapper never silently
binds" discipline the review's F6 established for gates and the integration process
applies here with the same force — a wrongly-summarised rule is worse than no rule,
because `gates validate` will happily validate it and convention review will cite it
as though it were authoritative.

### D6: The FR5 boundary is stated as "one source, two projections"

**Decision:** wherever this change's artifacts, the rewritten `gates-init` prompt,
or `docs/conventions.md`-style guidance describe how the conventions source feeds
its two consumers, they use the phrase **"one source, two projections"** and state
plainly: the rules-doc entire and unfiltered is what `convention-review` reads (via
`.gates.yaml`'s `conventions.rules-doc` → `gates rules`, a path that never touches
`openspec/config.yaml`); only the subset whose `Applies to:` line names a real
artifact id is what `gates conventions sync` projects into `openspec/config.yaml`'s
`rules:` block. A `code`-scoped rule is correctly absent from the second projection
— not a defect, not something sync failed to deliver — because no OpenSpec schema
(the bundled `spec-driven` or any of the five community schemas) has an
artifact-authoring destination for a rule with no artifact id: an `apply` block
cannot carry rules.

This is a closed input from `settle-fr5` (PR specloop PR 7), not a decision this change is
making — it is recorded here because F6's original scope decisions promised "one
source, two consumers" language that this change is not permitted to repeat
unmodified now that the verdict is in.

**Rejected alternative:** silently drop the "two consumers" framing without
replacing it, leaving adopters to discover the boundary the way the field run did.
Rejected because the whole shape of this change is closing gaps the field run found
by surprise; leaving this one implicit would recreate the exact failure mode (FR5
"still open" until checked against the schema) that this change exists to close out.

### D7: `openspec init` gets a confirmation gate, not a warning that proceeds regardless

Today's `commands/gates-init.md` preflight already warns once when generated
OpenSpec files look locally modified (present since `rename-to-gates`, predating the
field run) — and FR4 shows exactly this warn-then-continue behaviour in production:
the warning fired, and `openspec init --tools claude` still ran and overwrote three
locally-edited files, recoverable only because the tree was otherwise clean.

**Decision:** the new step 2 (D2) checks for local edits to generated files
*before* invoking `openspec init --tools claude`, and where edits are detected, it
stops and asks — explicit confirmation required to proceed, not a warning the
adopter can silently pass through — presenting `openspec schema fork <source>
<name>` as the durable alternative to editing a generated file. Declining leaves the
existing files untouched; the bootstrapper reports which downstream steps can't
proceed as a result (an authoring-command check that depends on `openspec init`
having run) rather than silently continuing in a half-consistent state.

This is the gate `docs/candidates.md`'s "protect locally-edited generated OpenSpec
assets" entry calls for as the "honest first move" — guidance plus a confirmation
gate, not a Specloop-side shim around `openspec init`'s own behaviour (which the
rejection test's second question — "does it know a stack/tool command" — would
reject as not-ours; gating *our own invocation* of it is ours, patching *its*
behaviour is not).

**Rejected alternative:** a code-level guard that intercepts or diffs `openspec
init`'s writes. Rejected per `docs/candidates.md`'s own disposition — the mechanism
belongs to upstream, and a Specloop-side guard around another tool's command is the
second rejection-test question's "not ours." Revisit only if the confirmation gate
proves insufficient in the field, per that entry's promotion criterion.

### D8: No-scaffold-stop is preserved and made an explicit, distinct case from "unlisted stack"

`onboarding-asks-first` already made "the adopter declines every candidate" and "the
stack isn't on the curated list" first-class outcomes that still reach a valid
manifest by asking the adopter to hand-write the `ci` gate body. F6's scope
decisions and F7 describe a stricter case this doesn't cover: a project with
**nothing to bind to at all** — no runner, no build target, no code — where asking
"what command builds and tests this?" has no honest answer because nothing exists
yet to build or test.

**Decision:** the detect-and-confirm step (D2's step 3) distinguishes the two cases
explicitly. "Unlisted stack, real project" still falls through to "ask outright,
adopter supplies the command by hand" (unchanged from `onboarding-asks-first`).
"No scaffold at all" — detected as the absence of any source files, build markers,
or targets to point at — stops onboarding honestly: it names what's missing (no code
to test, no target to run) and does not ask the adopter to invent a fictitious gate
command, because a project can have `ci` genuinely unbindable and that is not an
onboarding failure. The adopter can return once a scaffold exists.

**Rejected alternative:** treat "no scaffold" identically to "unlisted stack" and
always fall back to asking the adopter to hand-write something. Rejected because it
would pressure an adopter of a genuinely empty greenfield project into typing a gate
body for a target that doesn't exist, which either produces a gate that immediately
and permanently fails `ci` for reasons unrelated to code quality, or an adopter
typing a placeholder — exactly the "invented oracle" F6's scope decision rules out.

### D9: The rejection test, applied to this change as a whole

| Question | Verdict | Reasoning |
|---|---|---|
| Does it author an artifact? | not ours, and it doesn't | The bootstrapper wires `.gates.yaml`, a project's rules-doc, and `openspec/config.yaml`'s generated block — none of these are OpenSpec artifacts (proposal/specs/design/tasks); `openspec init` itself, which does scaffold OpenSpec's own files, is invoked through the upstream command, never reproduced. |
| Does it know a stack command? | not ours, and it doesn't bind one | Every tool name (`npm`, `just`, `make`, `cargo`, the OpenSpec CLI itself) is named to detect-and-offer, per the existing `stack-agnostic-prompts` carve-out; nothing here invokes a project command directly — invocation stays behind `gates run <gate>`. |
| Does it make a stated guarantee enforceable? | **ours** | Turns "conventions govern generated work" from an optional afterthought into a step that actually runs (F6/FR2); turns "your local edits are safe" from a warning into a confirmation gate (FR4); turns "the OpenSpec contract is stable" from an assumption into a checked one (F5). |
| Does it get a team running faster? | **ours** | This is the change's whole point per its Why: six manual, easy-to-get-wrong prerequisite steps collapse into one guided command run at the moment a project first has Specloop and OpenSpec in front of it. |

**Verdict: passes.** It clears on both of the "ours" questions (three and four), and
correctly clears the first two by declining to cross them — every new step gathers
information or asks a question; none of them authors an artifact or binds a
project-specific command without the adopter's explicit confirmation.

## Risks / Trade-offs

- **A longer bootstrapper is a longer first-run conversation.** Mitigated by keeping
  every new step optional-to-decline (skip OpenSpec CLI install if already present;
  skip harvesting if no source material is found; skip permission scaffolding if
  declined) so a project with everything already in place moves through quickly.
- **The doctor check (D3) cannot cover the worst case of its own failure class.**
  Named directly rather than papered over — see D3's two-part decision and the
  `SETUP.md` fallback for the fully-invisible state.
- **Harvested conventions can be wrong.** Mitigated by D5's confirm-before-write
  discipline; a wrongly harvested rule is never written without the adopter seeing
  it first.
- **This change is sequenced behind `harden-unattended-loop`, which is still
  in-flight.** If harden's own scope shifts materially before it lands, D1's
  absorption plan may need to be revisited — but the risk is contained to D1/D2's
  step ordering, not this change's other decisions.

## Open Questions

None. Every decision above states a rejected alternative and closes; the one
genuine hole (D3's diagnostic cannot reach a plugin that is totally invisible) is
not left open — it is resolved by explicitly scoping what the in-session mechanism
covers and pairing it with a documentation fallback for what it structurally cannot.
