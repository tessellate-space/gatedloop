# Onboarding asks first

## Why

Four defects found in the same afternoon, all touching onboarding, all the same shape:
**the plugin decides something it should be asking about, or stays silent where it
should speak.**

**1. The bootstrapper picks the stack for you.** `commands/gates-init.md` detects a
project's build system and binds a gate from it. To do that it names build tools —
`npm run`, `make`, `just`, `cargo test` — which `stack-agnostic-prompts` reads as
forbidden outright. The rule and the command have quietly contradicted each other since
both were written, and the contradiction was found while auditing `reposition-specloop`
(PR specloop PR 3), which changed neither.

The resolution is not to delete the tool names — onboarding genuinely cannot detect a
build system without naming one — nor to weaken the rule, which is the most important
rule in the repo. It is to move the *decision*: the four names are a curated list of
things to **look for and offer**, and the adopter chooses which to bind. Naming a tool
in order to ask about it is compatible with stack-agnosticism; naming one in order to
*pick* it is not. That distinction is what the rule is actually protecting, and it
should say so.

**2. The session brief has no branch for the half-onboarded project.** Measured
2026-08-18 against the installed plugin: `hooks/session-brief.sh` handles "no OpenSpec"
(offers exactly one step, `/specloop:gates-init`) and "fully onboarded" (the loop menu).
It has nothing for **OpenSpec present, `.gates.yaml` absent** — the single most likely
state for a brownfield adopter who installs Specloop into a project that already uses
OpenSpec. They get the full loop menu, and every command on it fails, because the
manifest those commands read does not exist. `gates-init` — the one command that would
fix it — is the one command the menu does not offer.

**3. Onboarding binds a gate without ever running it.** Carried over from
`reposition-specloop` 1.13, which specified the fix; this change is where it lands
alongside its siblings. Observed live: `gates-init` bound a red `ci` in a real project
and reported success, because its stated goal — a valid manifest — was met. A required
gate that is red at bind time means `tdd-apply` can never commit a single task. The
loop correctly refuses, and the adopter sees an unexplained no-op. **The defect is the
silence, not the red** — binding a gate the project cannot yet pass is legitimate and
often the whole reason someone is adopting a harness.

**4. The loop assumes how a change reaches `main`.** `tdd-apply` §7.5 ends in a local
squash-merge, unconditionally. Found in the 2026-08-18 field review
(`docs/review-2026-08-18.md`): a team whose `main` is protected — pull requests
required, approvals required — cannot use the loop's terminal step as written, and
nothing ever asked. The integration process is per-project variation of exactly the
kind `.gates.yaml` exists to hold, and `harden-unattended-loop` D10–D12 already design
the PR-shaped flow — what is missing is the *binding*: onboarding asking which process
this project uses and recording the answer where the loop and the enforcement layer
can read it, so installers pick from presented options instead of discovering the
assumption at merge time. This change owns the ask and the record; making the loop and
the hooks *consume* the declared process stays with `harden-unattended-loop`, which
reconciles §7.5 either way.

## What Changes

- **`gates-init` offers, and the adopter picks.** Detect candidates from a curated,
  documented list; present what was found; bind only what is chosen. Declining every
  candidate and writing the gate by hand stays a first-class path.
- **`stack-agnostic-prompts` gains an explicit carve-out** in `docs/conventions.md`:
  a shipped prompt may name a tool in order to *offer* it, never in order to *invoke*
  it. Invocation still goes through `gates run <gate>`, without exception.
- **The session brief grows its missing third branch** — OpenSpec present, no manifest —
  offering `gates-init` rather than a menu of commands that cannot work.
- **`gates-init` runs `ci` once after writing the manifest** and reports the exit code,
  without treating red as an onboarding failure.
- **`gates-init` asks how a change reaches `main`** — presenting preset options (local
  squash-merge; pull request; pull request with required approvals), detecting the
  likely answer from the remote where it can and offering it as the default, never
  auto-binding it — and records the choice in `.gates.yaml`, where `gates validate`
  checks it and later changes consume it.

## Capabilities

### Modified Capabilities

- `onboarding` — the bootstrapper asks before binding, reports the gate it bound, and
  the session brief covers the half-onboarded state.

## Non-goals

- Growing the curated tool list into a package-manager database. Four to six ubiquitous
  entries, with "none of these" always available; breadth is not the goal, asking is.
- Making a red gate block onboarding.
- Any change to the loop itself (`skills/`, `agents/`) — this change is onboarding only.
  In particular, **consuming** the declared integration process — `tdd-apply` §7.5
  switching on it, hooks enforcing it — belongs to `harden-unattended-loop`; this
  change only asks the question and records the answer.
