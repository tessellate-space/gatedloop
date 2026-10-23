## 0. Preconditions

- [x] 0.1 Confirm `harden-unattended-loop` has merged (design D1) before starting
      §5 (permission-scaffolding absorption) — its D4 step is what §5 relocates.
      The other sections do not depend on it and may start first.
- [x] 0.2 Confirm `settle-fr5` (PR specloop PR 7) has merged — its verdict (`Applies to: code`
      dropped by design, not a defect) is load-bearing for §3's boundary language
      and is assumed settled throughout this change's artifacts.

## 1. The OpenSpec prerequisite chain (design D2 steps 0–2)

- [x] 1.1 Add the OpenSpec-CLI-presence check to `commands/gates-init.md` as the new
      step 1: detect whether the CLI is installed, offer to install it, wait for
      confirmation
- [x] 1.2 Add `openspec init --tools claude` as the new step 2, replacing today's
      "confirm OpenSpec is initialized" preflight bullet that assumes it already ran
- [x] 1.3 Fold today's "confirm the authoring half is installed" check into step 2's
      completion condition (it re-runs `openspec init --tools claude` today only
      when commands are missing; the new step runs it unconditionally on first
      onboarding and re-checks afterward)
- [x] 1.4 Verify against a project with no OpenSpec CLI at all: onboarding installs
      it, initializes OpenSpec, and reaches gate binding without a manual step in
      between — requires a live conversational run, not just a read of the prompt

## 2. The FR4 confirmation gate (design D7)

- [x] 2.1 Replace the existing "warn once... then continue" bullet in
      `commands/gates-init.md` preflight with a stop-and-confirm gate ahead of step
      2's `openspec init --tools claude` call
- [x] 2.2 State `openspec schema fork <source> <name>` as the alternative in the
      same message, not as a separate note
- [x] 2.3 On decline, leave generated files untouched and report which downstream
      steps cannot proceed
- [x] 2.4 Verify both paths in a throwaway project: locally-edited generated files
      present (must stop and ask); clean generated files (must proceed without
      asking) — requires a live conversational run

## 3. Conventions capture as a core step (design D5, D6)

- [x] 3.1 Add the harvest sub-step to `commands/gates-init.md`: read
      CONTRIBUTING-shaped files, agent instruction files (`CLAUDE.md`/`AGENTS.md`),
      linter/formatter configuration, and — per FR3 — an existing
      `openspec/config.yaml` `context:` block
- [x] 3.2 Draft candidate rule-doc entries (`### <id>` / `Applies to: code` default
      / `Rule:` one-liner / prose) from harvested material; present each to the
      adopter before writing
- [x] 3.3 Write only confirmed entries into the project's rules-doc; wire
      `.gates.yaml surfaces[].rules` for surfaces the adopter selects
- [x] 3.4 Run `gates conventions sync` after confirmed entries are written; confirm
      `gates validate` passes with no drift
- [x] 3.5 Write the "one source, two projections" language (design D6) into
      `commands/gates-init.md`'s own explanation of the sync step, replacing any
      "one source, two consumers" phrasing that implies identical content reaches
      both
- [x] 3.6 Verify against a project with no harvestable material: the step reports
      "nothing found" plainly rather than writing placeholder content — requires a
      live conversational run
- [x] 3.7 Verify against a project whose `openspec/config.yaml` already has a
      `context:` block with real conventions in it (the FR3 shape): confirm they
      surface as harvest candidates — requires a live conversational run

## 4. F5 contract probe + doctor preflight (design D3, D4)

- [x] 4.1 Record the tested OpenSpec CLI version as a constant the shim can read
- [x] 4.2 Add a `gates doctor` check covering: OpenSpec CLI presence + version
      (warn, don't fail, on mismatch), `.gates.yaml` `gatesVersion` currency, and
      whether the plugin's commands/hooks appear registered for the active session
- [x] 4.3 Wire `gates doctor` as `commands/gates-init.md`'s step 0, run
      automatically before any other step
- [x] 4.4 Add the `CLAUDE_CONFIG_DIR` troubleshooting note to `SETUP.md` for the
      fully-invisible-install case that no in-session diagnostic can reach
- [x] 4.5 Verify `gates doctor` against a deliberately mismatched OpenSpec version:
      it warns and does not block onboarding or fail `gates validate` — requires a
      live conversational run or a scripted check of the shim's exit code

## 5. Absorb `harden-unattended-loop` D4 (design D1) — after §0.1

- [x] 5.1 Relocate D4's permission-scaffolding offer into the restructured
      command's step 6 (after the integration-process ask, before final validate +
      `ci` + report)
- [x] 5.2 Confirm no behavioural change to D4's own decision (opt-in,
      `.claude/settings.local.json`, never `settings.json`, the `gates *` /
      `openspec *` / `git commit *` allow list, `ask` on `git merge *`) — this task
      only moves where the step runs, not what it does
- [x] 5.3 Confirm `harden-unattended-loop`'s design/tasks needed no edit as a result
      (`git diff` against that change's files after this section is empty)

## 6. No-scaffold-stop, made explicit (design D8)

- [x] 6.1 Add the "no scaffold at all" detection to the gate-binding step: no
      source files, no build markers, no targets found (distinct from "stack
      unlisted but a real project exists")
- [x] 6.2 On no-scaffold, name what's missing and stop without writing a
      `.gates.yaml` or asking the adopter to fabricate a `ci` command
- [x] 6.3 Verify the two cases stay distinct in a throwaway project: an empty
      directory (must stop) vs. a project with an unrecognized but real build setup
      (must still ask for a hand-written `ci`, as today) — requires a live
      conversational run

## 7. Close out

- [x] 7.1 Re-read the rewritten `commands/gates-init.md` end to end against the
      rejection test (design D9): confirm no step authors an artifact and every
      tool name is present to offer, never to invoke
- [x] 7.2 Confirm `git diff --name-only` for this change's implementation touches
      only `commands/gates-init.md`, the shim (`bin/gates`), `schema/gates.schema.json`
      (if the doctor/version fields need schema support), `SETUP.md`/`README.md`,
      and `tests/` — not `skills/`, `agents/`, or `hooks/` beyond what §4 already
      lists
- [x] 7.3 Run the full onboarding flow end to end against a fresh throwaway
      project, no OpenSpec CLI installed, no `.gates.yaml`: confirm it reaches a
      valid, `ci`-checked manifest with no manual step outside the single command —
      requires a live conversational run, the closing verification for this
      change's whole premise
