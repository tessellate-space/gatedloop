## Purpose

The time-scoped surface for opening Specloop to invited testers: a field guide covering invite-gated setup, the journeys to exercise, the honestly-stated sharp edges, and the roadmap — plus the README's entry point into it and a verified-accurate install path.

## ADDED Requirements

### Requirement: The field guide gates setup on collaborator access as step zero

`docs/field-guide.md` SHALL open its setup checklist with obtaining collaborator access, because the trial repository is private and both `/plugin marketplace add radub21/specloop` and `gh` operations require an invite. The checklist SHALL then proceed through the ordered prerequisites to a first working loop.

#### Scenario: A tester reads the setup checklist

- **WHEN** an invited tester follows the field guide from the top
- **THEN** the first step is getting collaborator access, stated as a precondition of the marketplace-add and `gh` steps that follow, and the remaining prerequisites are given in order

#### Scenario: The private-repo constraint is explicit

- **WHEN** a reader reaches the install instructions
- **THEN** the guide states that the repository is private for the duration of the trial, so an uninvited reader cannot add the marketplace or use `gh` against it

### Requirement: The field guide names the journeys to exercise

`docs/field-guide.md` SHALL enumerate the journeys a tester is asked to run and observe: onboarding (`openspec init --tools claude` → `/specloop:gates-init` → `gates validate`), the loop (`/opsx:propose` a small change → `/specloop:tdd-apply`), the unattended `tdd-implementer` agent, and the SessionStart brief. For each it SHALL state what a good outcome looks like, so a tester can tell success from failure.

#### Scenario: A tester picks a journey to run

- **WHEN** a tester looks for what to exercise
- **THEN** the guide lists the onboarding, loop, unattended-agent, and session-brief journeys, each with the observable signal of whether it went well

#### Scenario: Manual testing is framed as the test suite

- **WHEN** a tester asks why their hands-on run matters
- **THEN** the guide states that the prompt surface has no automated oracle, so running the journeys on a real stack is the test

### Requirement: The field guide states the trial's sharp edges honestly, each labeled with status

`docs/field-guide.md` SHALL document the known sharp edges of the current `main`, each labeled so a tester can distinguish a known limitation from a bug worth reporting and a shipped behavior from a proposed fix. It SHALL cover at least: the six-step manual onboarding chain, the invisible-install failure and its from-a-plain-shell check, that hook changes need a fresh session, that `gates-init` can overwrite an existing `.gates.yaml` with only a warning, the propose-on-`main`/one-branch-per-change discipline, that `gh pr merge` is not hook-gated the way `git merge` is, and the `harness`→`gates` migration table for older installs.

#### Scenario: A tester hits a documented limitation

- **WHEN** a tester encounters one of the documented sharp edges
- **THEN** the guide already describes it, marks whether a fix is shipped or only proposed, and thereby steers the tester away from filing a known limitation as a new bug

#### Scenario: The invisible install is diagnosable from outside a session

- **WHEN** a tester sees no Specloop commands, skills, or session brief at all
- **THEN** the guide gives a check runnable from a plain shell (the `CLAUDE_CONFIG_DIR` profile), because no in-session surface can diagnose its own total absence

#### Scenario: An updating tester finds the rename table

- **WHEN** a tester is updating from a Specloop that predates the `harness`→`gates` rename
- **THEN** the guide provides the migration table mapping the old names to the new ones

### Requirement: The field guide records the roadmap so testers separate coming from broken

`docs/field-guide.md` SHALL summarise what is in flight versus what is shipped, so a tester can tell a not-yet-built capability from a regression. It SHALL close by directing the tester to the feedback skill for reporting back.

#### Scenario: A tester wonders whether something is missing or unbuilt

- **WHEN** a tester finds a capability absent
- **THEN** the roadmap section lets them see whether it is in flight (expected) or should exist (a bug to report)

#### Scenario: The guide hands off to the feedback channel

- **WHEN** a tester finishes a journey and wants to report the result
- **THEN** the guide's closing section directs them to `/specloop:feedback`

### Requirement: The field guide is marked time-scoped to the trial

`docs/field-guide.md` SHALL state that it is scoped to the field trial and expected to be retired when the trial ends, so it is not mistaken for durable product documentation.

#### Scenario: A reader checks the guide's shelf life

- **WHEN** a reader opens the field guide after the trial
- **THEN** a note at the top identifies it as trial-scoped and points at the durable docs (`README.md`, `SETUP.md`) for standing guidance

### Requirement: The README carries a field-trial entry point with an accurate install path

`README.md` SHALL add a short, prominent Field-trial section near the top that links to `docs/field-guide.md`, while retaining its durable positioning content. The install path the README presents SHALL be accurate against current `main` — reflecting the shipped enforcement layer and the `gates` shim name — rather than an aspirational one.

#### Scenario: A visitor finds the trial from the README

- **WHEN** a reader opens the README during the trial
- **THEN** a Field-trial section near the top points them at the field guide, without displacing the ladder, boundary, and owner content already there

#### Scenario: The install path matches reality

- **WHEN** a tester copies the README's install and first-run commands
- **THEN** the commands are the ones that work on current `main`, using the current shim and command names, not names or steps that have since changed
