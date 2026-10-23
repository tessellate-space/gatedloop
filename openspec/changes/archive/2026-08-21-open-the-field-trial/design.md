## Context

See proposal.md — Why. This change adds no code to `bin/gates`, no hook, and no gate; it is a documentation surface (`README.md`, `docs/field-guide.md`), a skill (`skills/feedback/SKILL.md`), and issue templates (`.github/ISSUE_TEMPLATE/`). It assumes current `main`: PR specloop PR 8 (`harden-unattended-loop`) merged the enforcement layer, and the `harness`→`gates` rename landed before it.

The constraint that shapes every decision below is that testers run inside **client projects**. A feedback tool that is convenient but leaks a proprietary command or a snippet of client code into a public-ish GitHub issue is a net negative — it costs a trust relationship to save a copy-paste. So the design's centre of gravity is not "collect rich context" but "collect only what is provably safe, and never send anything the human has not read."

`plugin.json` already carries `"repository": "https://github.com/radub21/specloop"`, and the repo has a `.github/pull_request_template.md` but no `.github/ISSUE_TEMPLATE/` yet. Both facts matter below (D2, D3).

## Goals / Non-Goals

**Goals:** a tester can go from invite to a first reported result without guessing; every report — friction or confirmation — arrives structured and privacy-bounded; the trial's sharp edges are documented honestly enough that a tester distinguishes a known limitation from a real bug.

**Non-Goals** (design-level, beyond the proposal's): designing the fixes for any documented sharp edge; any automatic/background collection; retargeting the feedback skill at repositories other than Specloop's own; a gate or oracle for feedback (it produces no exit code, so per `workflow-packs` D1's rule it is not a gate).

## Decisions

### D1: Three deliverables, one change — because the seam between them is the point

The README points at the guide; the guide's closing section points at the skill; the skill's issue body mirrors the templates. Split across three changes, the guide would ship describing a "how to report back" flow that does not exist yet, or the skill would ship with no document telling a tester when to reach for it. They are one user-facing thing — *run it, find something, tell us* — and the honest unit of work is the whole loop, authored together so the cross-references resolve on the day it lands.

**Rejected alternative:** ship the feedback skill first (it is the permanent surface) and the guide later. Rejected because the trial *is* the reason the skill exists right now; a permanent skill with no trial to feed it would be scheduled behind more urgent work and the trial would open with a docs-only "please file an issue," which is precisely the weaker alternative D5 rejects.

### D2: Naming `gh` and the repository is Specloop's own channel, not a stack binding

`stack-agnostic-prompts` bans a shipped prompt from hard-coding the **adopter's** test/build/probe commands, routing all such invocation through `gates run <gate>`. The feedback skill names `gh` and posts to `radub21/specloop`. This is not a violation, and the reason is the rule's own reviewer's test: *would this prompt still be correct in a project that uses none of the named tools?* Yes — the adopter's project varies, but Specloop's home does not. `gh` here is not a binding to the project under test; it is Specloop talking to its own repository, the same way `harden-unattended-loop` already ships `gh pr view` for approval attestation without anyone calling that a stack binding. The tool being named belongs to Specloop's own workflow, not the adopter's stack — which is the exact line the rule draws.

Two implementation constraints fall out, and both are spec requirements rather than prompt suggestions:

- **The repository slug has one source of truth.** `plugin.json` already carries `repository: https://github.com/radub21/specloop`. The skill resolves the slug from that manifest (via `${CLAUDE_PLUGIN_ROOT}`, honoring `plugin-relative-paths` and `self-contained-plugin`) rather than hard-coding `radub21/specloop` in prompt prose that would silently target the wrong repo after a fork or rename. This is the "read the slug from plugin metadata" option the brief flagged, adopted because it costs nothing and removes the one string most likely to rot.
  - **Rejected alternative:** hard-code `radub21/specloop` inline in the skill and each template. Rejected on drift risk alone — a fork inherits the string and would file its testers' reports into *our* issue tracker, which is both wrong and a privacy leak across projects.
- **`gh` is a hard dependency of the *happy path* only, never of the skill succeeding.** Absence of `gh` is a first-class branch (D3's degradation), not an error the tester has to decode.

### D3: The privacy boundary is a positive whitelist, a literal-body approval gate, and a fail-loud degradation — all three as requirements

The proposal states *what* is collected; the design records *why each mechanism is shaped the way it is*, because the wrong shape fails silently in exactly the client-project case this exists to protect.

- **Collection is an allowlist, not a denylist.** The skill gathers only: plugin version, OpenSpec CLI version, `gates doctor`/`gates validate` output, which command/gate was involved, the `.gates.yaml` *shape* (gate **names** and surface **globs** only — never a gate command body), and OS/platform. Everything else is excluded by default. A denylist ("collect context but strip secrets") fails open: the day someone adds a new context source, it ships to GitHub unless a reviewer remembered to add it to the strip list. An allowlist fails closed — a new source is invisible until deliberately whitelisted. Given the cost of a leak is a client relationship, closed is the only defensible default.
  - The `.gates.yaml` *shape* carve-out is the subtle one and is specified precisely: gate names (`ci`, `unit`, …) and surface globs (`backend/app/**`) are Specloop's own vocabulary and safe; the command **bodies** those names map to (`just deploy-prod --token=…`) are the adopter's and are never read. A report that needs a gate body is a report the tester pastes in by hand, having seen it.
- **Approval shows the complete literal issue body, not a summary.** The tester sees the exact markdown that will be posted, byte for byte, and must explicitly approve before anything leaves the machine. A summary ("I'll include your versions and platform") is not good enough — the whole failure mode is a field the tester did not realize was being sent, and only the literal payload surfaces that. This is written as a scenario, not prompt tone.
  - **Rejected alternative:** post immediately with a "you can edit or delete the issue afterward" note. Rejected because deletion does not un-leak — a client command sitting in a public issue for thirty seconds is already indexed, already in notification emails. The gate has to precede the send.
- **No-`gh` degrades loud, never silent.** If `gh` is missing, unauthenticated, or offline, the skill prints the full markdown body **and** the issues URL (`<repository>/issues/new`) so the tester files it by hand, and says plainly that it did not post. Dropping the report silently would be the `fail-loud-gates` anti-pattern applied to the one channel whose entire purpose is not losing signal.

### D4: The skill is permanent; the guide is time-scoped — and they are separated so one can outlive the other

Reporting a bug against the tool you are running is a durable capability, not a beta affordance — an adopter six months from now hitting a real defect wants exactly this skill, whitelist and approval gate included. So `/specloop:feedback` is permanent product surface and lives with the other skills.

`docs/field-guide.md` is the opposite: it names testers-in-progress, an invite-only private repo, and a roadmap snapshot that is stale the moment the trial closes. It is explicitly time-scoped, carries a note saying so, and is expected to be archived or deleted when the trial ends. Keeping the two in different capabilities (D6) is what lets the guide be retired without touching the skill.

**Rejected alternative:** fold the feedback flow into the guide as prose ("run `gh issue create` like this") and ship no skill. That is D5's rejected alternative from the other direction — it would tie a permanent capability's lifetime to a temporary document's.

### D5: The rejection test — a near-miss that passes on question four, read through the *climb* job

This is the decision the `rejection-test` rule exists to force, and the feedback skill is a genuine near-miss, so it is recorded honestly rather than waved through.

| Question | Verdict | Reasoning |
|---|---|---|
| Does it author an artifact? | not this | The skill files a GitHub issue and the guide is documentation; neither is an OpenSpec artifact (proposal/specs/design/tasks). |
| Does it know a stack command? | not this | It names `gh` and Specloop's own repo (D2), never the adopter's test/build/probe commands. |
| Does it make a stated guarantee enforceable? | weak | There is no prompt-stated guarantee it hardens into an invariant — this is the question it does **not** clear, which is what makes it a near-miss. |
| Does it get a team running faster? | **this** | Read through `reposition-specloop` D3's *climb* job: a feedback channel is *how onboarding friction gets found and fixed*. It does not speed up the team running it today; it speeds up every future team, by turning a tester's friction into a filed, structured, privacy-safe report that a fix can be built from. |

**Verdict: passes on question four via the climb job.** The single unifying question — *does it move a phase from `act` to `close`, or move a team up a rung faster?* — resolves it: the trial and its channel are the evidence-gathering step that lets the *climb* surfaces (onboarding, `gates-init`, `streamline-onboarding`) actually get faster, rather than getting faster by guess.

**Rejected alternative, recorded because it is the obvious cheaper one:** a docs-only guide with a "please open an issue, here are the fields" section and the `.github/ISSUE_TEMPLATE/` templates — no skill. Rejected because the skill's entire value-add is the part a human will not do reliably by hand: gathering the whitelisted context *deterministically* (a tester filing manually will paste whatever seems relevant — including, exactly, the client command that should never leave the machine) and showing the literal body before send. The templates alone move the failure mode in the wrong direction: they *ask* for context without bounding it. The skill is the thing that makes the privacy boundary mechanical rather than a request. So the templates ship *and* the skill ships — the templates catch reports that arrive by other routes; the skill is the safe default route.

### D6: Two new capabilities, not a delta on `plugin-positioning`

The README changes are tempting to file as a `plugin-positioning` delta, since that capability owns "README and SETUP separate what is owned from what is delegated." Rejected: the durable positioning content (the ladder, the boundary, the three owners) is not changing — no existing `plugin-positioning` requirement's *text* is modified, and a MODIFIED delta that restates a requirement only to append "…and also link the field guide" would misrepresent what changed. The trial-specific README section and the install-path-accuracy check are genuinely new behavior, and they belong to a capability that can be **retired with the trial** (D4). So:

- `feedback-channel` — the skill, the templates, the whitelist/approval/degradation contract. Permanent.
- `field-trial` — the guide, the README entry point, the install-path accuracy requirement. Time-scoped.

The install-path accuracy requirement lives in `field-trial` rather than `plugin-positioning` deliberately: it is a *trial* obligation ("the path a tester copies must actually work on today's `main`"), and phrasing it as a standing `plugin-positioning` requirement would over-claim a permanent guarantee this change is not set up to keep enforcing after the trial.

### D7: The guide documents sharp edges as they are on `main` today — including ones whose fix is only proposed

The guide's candor obligation means it states the current reality even where a fix is already designed, and labels each edge with its status so a tester is not misled into thinking a proposal has landed. The concrete set to document, each with its evidence trail:

- **Onboarding is a six-step manual prerequisite chain** — `streamline-onboarding` (PR specloop PR 9) is proposal-only; the guide documents the six steps, not the one-command future.
- **The invisible install** — a wrong `CLAUDE_CONFIG_DIR` profile means no commands, no error, undiagnosable from inside a session (streamline D3). The guide gives the from-a-plain-shell check (`echo $CLAUDE_CONFIG_DIR`), because no in-session surface can diagnose its own total absence.
- **Hook changes require a fresh session** to take effect — a first-session tester who updates the plugin will not see hook behavior until they restart.
- **`gates-init` can overwrite an existing `.gates.yaml` with only a warning** (FR4; stop-and-confirm is proposed in `streamline-onboarding` D7, not shipped).
- **Git discipline: propose on `main`, one branch per change** — from a branch, OpenSpec loses sight of other in-flight changes.
- **`gh pr merge` is not hook-gated the way `git merge` is** — flagged in PR specloop PR 8's own "Flagged by the run" section; the merge gate has a hole exactly on the PR integration path the enforcement layer itself introduced.
- **The `harness`→`gates` migration table**, for a tester updating from an older install.

**Rejected alternative:** document only what works and omit the edges to keep the trial encouraging. Rejected outright — a trial that hides its own failure modes gets bug reports for known limitations and burns the tester's goodwill on things we already knew. Candor is the feature.

### D8: Both positive and negative reports, distinguished by label at the source

The skill collects confirmations ("worked in stack X") as first-class reports, not just failures. A confirmation is field evidence — it is what tells us a stack we never anticipated actually works — and it is the cheap half to collect, so there is no reason to make it a second-class path. The two are distinguished by GitHub **label** (`friction`/`bug` vs `field-report`) applied at creation and mirrored by two issue-template entries, so the tracker sorts itself without a triage step. The whitelist, approval gate, and degradation path are identical for both — privacy does not depend on whether the news is good.

## Risks / Trade-offs

- **The whitelist is only as safe as its enumeration** → mitigated by making it a positive allowlist (D3): the failure mode of forgetting an item is *under*-collection (a less useful report), never *over*-collection (a leak). The direction of error is chosen deliberately, the same way `SETUP.md`'s glob matching chooses fail-hot.
- **A tester approves a body without reading it** → residual and accepted; the literal-body gate (D3) is the strongest mechanism available short of not sending at all, and a human who rubber-stamps their own client's command is past what a tool can prevent. The whitelist is the real protection; approval is the second layer.
- **The repository is private, so `gh` auth is a prerequisite the tester may not have** → this is why setup step zero is "get collaborator access" and why the no-`gh` path prints a manual-filing URL (D3); a tester without access still produces a report, just not an auto-filed one.
- **The guide goes stale as the roadmap moves** → accepted and bounded by D4/D7: it is time-scoped by construction, labels each edge with status, and is expected to be retired at trial end rather than maintained indefinitely.
- **`gh pr merge` hole documented but not fixed here** → deliberately out of scope (proposal Non-goals); documenting it is the candor obligation, fixing it is a separate change.

## Open Questions

None that change the specs, the approach, or the task breakdown. Two items are deliberately left to implementation because either answer is spec-compatible: the exact label strings (`bug`/`friction`/`field-report`) and whether the two report kinds are one skill prompt with a branch or one flow with a type question — both satisfy D8's "distinguished at the source" requirement, and neither changes a scenario.
