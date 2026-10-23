## Why

`docs/review-2026-08-18.md` **F6** names the honest prerequisite list for onboarding
a project onto Specloop: a git repo, Claude Code + the plugin, Node + the OpenSpec
CLI, `openspec init --tools claude`, Python 3.9+, and a task runner with a real `ci`
command — six manual steps where one guided command is possible. `onboarding-asks-first`
already fixed *how* `/specloop:gates-init` decides (it offers candidates, the adopter
picks; F6's ask-before-bind residue) but not *how much of the chain it covers* — it
still starts after most of the prerequisites are already in place. F6's scope
decisions record two more commitments that change hasn't spent yet: conventions
capture is a **core** onboarding step, not an optional extra, and a project with
nothing to bind to should **stop honestly** rather than invent an oracle. The
Disposition table in that review names this change — `streamline-onboarding` — as
the vehicle for exactly this residue, sequenced after `onboarding-asks-first` and
pairing with `harden-unattended-loop` D4.

The 2026-08-19 field run against a real brownfield project supplies the evidence
this change turns into behaviour:

- **FR1** confirmed `onboarding-asks-first` working end to end — offer-don't-pick,
  the integration-process ask, real reasoning behind each binding. Nothing here
  revisits that ground.
- **FR2** showed the practical cost of leaving conventions capture optional: a
  freshly generated rules-doc has no `### <id>` headings, so every surface's
  `rules:` falls back to inline prose and convention review has nothing checkable
  to enforce until an adopter fills the doc in by hand, later, unprompted.
- **FR3** found real, checkable conventions already sitting in that project's
  `openspec/config.yaml` `context:` block — a components-library-first UI rule, an
  explicit auth-client rule with its reasoning recorded, a mobile-first rule, a
  data-fetching rule, a query-key naming convention — that nothing had harvested
  into a rules-doc. This is concrete evidence the harvest step has real input to
  work with, not a hypothetical one.
- **FR4** found that re-running `openspec init --tools claude` overwrote three
  locally-edited generated files (203 insertions, 91 deletions) with nothing beyond
  a warning already present in `commands/gates-init.md` — no diff, no confirmation
  gate — recoverable only because the tree happened to be clean beforehand.
- **FR5**, left open by the field run, is now settled on branch `settle-fr5` (PR specloop PR 7):
  `gates conventions sync` dropping `Applies to: code` rules is **correct by
  design**, not a defect. Code-scoped rules reach convention review through
  `.gates.yaml` `surfaces[].rules` → `gates rules`, a path that never touches
  `openspec/config.yaml`. No OpenSpec schema — the bundled one or any of the five
  community schemas — has an artifact-authoring destination for a `code`-scoped
  rule; an `apply` block cannot carry rules. This change may not promise "one
  source, two consumers" as if both consumers receive the same content — the
  accurate framing, which this change states explicitly rather than leaving
  adopters to discover it, is **one source, two projections**: the rules-doc
  entire and unfiltered feeds convention review, and only the artifact-scoped
  subset feeds OpenSpec authoring via sync.

**F5** — the OpenSpec contract is unpinned — is folded in here per the review's
Disposition table ("fold into the follow-on bootstrapper/doctor change"): `gates
validate` already shells out to `openspec schemas --json` against an unversioned,
pre-1.0 CLI, and nothing records which version was tested.

Onboarding at the moment of plugin *install* is the wrong moment and likely
impossible — install is per-user and once, every prerequisite above is per-project.
The right trigger is the first session inside a given project, which the
`SessionStart` hook already owns (`onboarding-asks-first` §3 already added the
"OpenSpec present, no manifest" branch that offers `/specloop:gates-init`). This
change does not touch the hook; it makes the command the hook already points at
cover the whole chain.

## What Changes

- **`/specloop:gates-init` becomes the bootstrapper.** It grows a preflight doctor
  check, an OpenSpec-CLI-presence check with an install offer, and an `openspec init
  --tools claude` step — ahead of the detect-and-confirm gate binding
  (`onboarding-asks-first`) it already performs. Six steps collapse into one guided
  command, run at the moment that has a project in front of it.
- **Conventions capture becomes a core step**, not something an adopter discovers is
  missing later (FR2). The bootstrapper harvests existing material — contributing
  guides, agent instruction files, linter configuration, and (FR3) an OpenSpec
  project's own `config.yaml` `context:` block — into candidate rule-doc entries,
  confirms them with the adopter, wires both consumers, and runs `gates conventions
  sync`.
- **The FR5 boundary is stated, not implied.** Wherever this change's artifacts or
  the bootstrapper's own output describe the conventions source, they say "one
  source, two projections" and name which content reaches which consumer.
- **`openspec init` gets a real confirmation gate, not just a warning** (FR4). Where
  local edits to generated OpenSpec assets are detected, the bootstrapper stops and
  asks before running `openspec init --tools claude` — today's warn-once-then-proceed
  behaviour is exactly what FR4 found insufficient — and names the durable
  alternative (`openspec schema fork <source> <name>`) plainly.
- **The OpenSpec contract is probed, not assumed** (F5). The tested OpenSpec CLI
  version is recorded where the shim can check it against the installed one, and a
  mismatch is a loud warning, not a silent assumption.
- **No scaffold → stop honestly** is preserved and made explicit as its own
  behaviour, distinct from "the stack isn't on the curated list": a project with
  nothing to bind to (no runner, no targets, nothing built yet) is told what's
  missing and onboarding stops, rather than the bootstrapper inventing an oracle or
  asking the adopter to fabricate one.
- **A preflight diagnostic for the invisible-install failure.** A `gates doctor`
  check, run automatically as the bootstrapper's first step, distinguishes the
  states between "nothing is wired" and "fully onboarded" — see design D3 for why
  this alone cannot cover every failure mode of this class, and what covers the
  rest.
- **Absorbs `harden-unattended-loop` D4's permission-scaffolding step** into the
  restructured command (see design D1) rather than harden rebasing onto a command
  this change has already rewritten.

## Capabilities

### Modified Capabilities

- `onboarding` — `/specloop:gates-init` covers the full prerequisite chain, treats
  conventions capture as core, states the FR5 boundary, gates `openspec init` on a
  local-edit confirmation, probes the OpenSpec contract version, diagnoses the
  invisible-install failure, and preserves the no-scaffold-stop behaviour as an
  explicit requirement.

## Non-goals

- **Permission scaffolding as new design.** `harden-unattended-loop` D4 owns the
  decision (opt-in, `.claude/settings.local.json`, never the shared
  `settings.json`); this change only relocates *where in the command* that already-
  designed step runs.
- **Authoring artifacts of any kind.** Selecting or acquiring an OpenSpec schema, or
  producing proposal/design/tasks content, is OpenSpec's half and `workflow-packs`'
  half respectively — never this change's.
- **Naming a stack command in order to bind it.** The bootstrapper only ever offers
  a curated tool name for the adopter to confirm or decline (`stack-agnostic-prompts`'
  carve-out); it never invokes one directly.
- **Growing the detector list into a package-manager database.** Already a
  non-goal of `onboarding-asks-first`; this change does not reopen it.
- **Schema acquisition and pack inspection.** `workflow-packs` owns "make schema
  acquisition a guided step available at any time" and "inspect a schema before
  trusting it" — this change's `openspec init` step assumes the bundled
  `spec-driven` default and does not select or evaluate a schema.
- **A code-level guard against `openspec init`'s overwrite behaviour.**
  `docs/candidates.md` records this as a live candidate: the mechanism is
  upstream's, so the honest first move is a confirmation gate plus guidance (fork,
  don't edit), not a Specloop-side shim around another tool's command. Revisit only
  if guidance proves insufficient in practice.
- **`gates audit`** (score a project's loop coverage) — a separate `docs/candidates.md`
  entry, blocked on the durable ledger `harden-unattended-loop` introduces.
