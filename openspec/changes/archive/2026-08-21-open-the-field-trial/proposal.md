## Why

Specloop is about to be handed to a handful of testers who will run it in real projects — some of them client work, where a leaked snippet of code or a proprietary command is a trust incident, not a bug report. **Manual testing is the only test suite the prompt surface has**: prompts, skills, and agents have no oracle (that is the whole reason `tests/` covers only the shim), so the way this plugin gets exercised is people running it on stacks it never anticipated and telling us what happened. The newly merged enforcement layer (specloop PR 8) has never seen a foreign machine; onboarding is still a six-step manual chain; the session brief has never had to say something sensible in a stranger's repository. A trial is how those meet reality — but only if reporting back is frictionless *and* safe.

Three deliverables ship as one change because they are one thing: the field guide's "how to report back" section **is** the feedback skill's documentation, and neither is worth shipping without the other. The trial repository stays **private** for now, so the whole thing is gated on invite — that constraint is the first line of the guide, not an afterthought.

## What Changes

- **README refresh (deliverable 1).** Keep the durable content that already earns its place — the adoption ladder, the two-axis boundary, the three-owner table — but add a short, prominent **Field trial** section near the top that points a tester at `docs/field-guide.md`, and verify the install path reads correctly against current `main` (post-specloop PR 8: enforcement hooks now ship, `gates` is the shim name). The README must describe current reality, not aspirations.
- **`docs/field-guide.md` (deliverable 2).** The tester's document, and explicitly time-scoped to the trial. A setup checklist starting from **step zero — get collaborator access** (the repo is private; both `/plugin marketplace add radub21/specloop` and `gh` need an invite); the four journeys to exercise (onboarding, the loop, the unattended agent, the session brief); the sharp edges stated honestly, because the guide's job during a trial is candor, not marketing; the current roadmap so a tester can tell *coming* from *broken*; and a "how to report back" section that hands off to the feedback skill.
- **`/specloop:feedback` skill + issue templates (deliverable 3).** A skill at `skills/feedback/SKILL.md` (per `commands-flat-skills-nested`) that files a GitHub issue against `radub21/specloop`, collecting **both** friction/bug reports **and** positive "this worked in stack X" confirmations — a confirmation is field evidence too, and the cheaper half to collect. Context is gathered **deterministically from a whitelist only**; the complete literal issue body is shown to the tester for **explicit approval before anything is posted**; posting goes through `gh issue create -R radub21/specloop` with a bug/friction-vs-field-report label, and degrades gracefully — if `gh` is absent or unauthenticated it prints the full body and the issues URL for manual filing rather than dropping the report. `.github/ISSUE_TEMPLATE/` templates mirror the same fields so reports arriving outside the skill carry the same structure.

The load-bearing constraint, written into the spec rather than left to prompt vibes: the skill **never** collects diff content, file contents from the adopter's project, gate command bodies, or anything off the whitelist, and **never** posts without showing the tester exactly what will be sent.

## Capabilities

### New Capabilities
- `feedback-channel`: a permanent product surface — the `/specloop:feedback` skill and matching issue templates that turn a running Specloop into a structured, privacy-bounded channel back to its own repository. Whitelisted deterministic collection, mandatory show-before-send approval, and a fail-loud degradation path when no forge CLI is available.
- `field-trial`: the time-scoped trial surface — a `docs/field-guide.md` covering invite-gated setup, the journeys to exercise, the honestly-stated sharp edges, and the roadmap; plus the README's Field-trial entry point and a verified-accurate install path.

### Modified Capabilities
<!-- None. The README's durable positioning content stays owned by `plugin-positioning`; the trial-specific section and install-path accuracy are new requirements under the new `field-trial` capability, so no existing requirement's text changes. See design D6 for why this is a new capability rather than a delta on `plugin-positioning`. -->

## Evaluation impact

- None — this is documentation and a reporting skill; no scored pipeline, no model-facing code path, no gate contract change. The feedback skill names `gh` and a repository slug (see design D2), but adds no gate and no oracle.

## Impact

- **Plugin files added**: `skills/feedback/SKILL.md`; `.github/ISSUE_TEMPLATE/*` (bug/friction and field-report templates, plus `config.yml`); `docs/field-guide.md`. **Modified**: `README.md` (new Field-trial section; install-path accuracy pass). No shim code, no hook, no gate manifest change — so `gates run ci` is unaffected.
- **Assumes current `main` (post-specloop PR 8)** — the guide documents the enforcement layer that specloop PR 8 landed and the `harness`→`gates` rename that preceded it. It does **not** depend on `streamline-onboarding` (proposal-only, PR specloop PR 9): the trial is designed to *generate* the field evidence `streamline-onboarding` consumes, so it documents today's six-step onboarding as a sharp edge rather than waiting for the fix.
- **New external touchpoint**: the feedback skill shells out to `gh` against `radub21/specloop`. This is Specloop's own channel to its own home, not a binding to the adopter's stack — the distinction is argued in design D2, and the skill fails loud (prints the body for manual filing) rather than silently when `gh` is unavailable.
- **Privacy surface**: testers run the skill inside client projects. The whitelist and the show-before-send gate are the containment; both are specified as requirements with WHEN/THEN scenarios, not left to the prompt to remember.

## Non-goals

- **Automatic telemetry or crash reporting.** Nothing leaves a tester's machine without the tester reading the exact payload and approving it. No background collection, no opt-out model — opt-in per report, every time.
- **A general-purpose issue-filing tool for arbitrary repositories.** The skill targets Specloop's own repository; retargeting it at an adopter's project would make it a stack binding, which the rejection test rejects (design D2).
- **Fixing the sharp edges the guide documents.** The guide's job is to state them honestly; the fixes are other changes (`streamline-onboarding`, a `gh pr merge` hook, a `gates-init` stop-and-confirm), most already proposed. Listing an edge here is not committing to fix it in this change.
- **Keeping the field guide after the trial.** `docs/field-guide.md` is explicitly time-scoped and expected to be archived or retired when the trial ends; `/specloop:feedback` is not (design D4).
