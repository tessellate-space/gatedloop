## 1. Establish the baseline before deleting anything

- [x] 1.1 In a throwaway repo, run `openspec init --tools claude` and record the installed `.claude/commands/opsx/*` and `.claude/skills/openspec-*` inventory
- [x] 1.2 Diff each of `commands/explore.md`, `commands/propose.md`, `commands/archive.md` against its upstream counterpart; record every delta in the change's design notes as either "staleness" (expected) or "intentional improvement" (must be preserved or contributed upstream)
- [x] 1.3 Confirm the expected result — that all deltas are staleness — and HALT for a human decision if any delta turns out to be a genuine improvement
  - HALTED as designed: two deltas were genuine improvements. Decided (design D7) — the
    archive commit is a guarantee and is kept as a delegating command; the propose
    handoff is a menu and moves to the session brief (task 5.3).

## 2. Delete the forked commands

- [x] 2.1 Remove `commands/explore.md` and `commands/propose.md`
- [x] 2.2 Reduce `commands/archive.md` to a delegation: run `/opsx:archive`, then commit the move and stop loudly if the commit fails — holding no copy of upstream's prompt
- [x] 2.3 Verify `claude plugin validate .` still passes with the reduced command set
- [x] 2.4 Verify the remaining commands are exactly `harness-init`, `start` and the reduced `archive` (plus the `tdd-apply` skill)

## 3. Make the upstream surface a checked prerequisite

- [x] 3.1 Add a preflight step to `commands/harness-init.md`: check `.claude/commands/opsx/` exists
- [x] 3.2 On absence, offer to run `openspec init --tools claude`; on decline, report that authoring will be unavailable and write no partial configuration
- [x] 3.3 On presence, warn once if the generated commands have been modified locally — `openspec update` may overwrite them
- [x] 3.4 Test all four paths in a throwaway repo: integration present, present-but-modified, absent-and-accepted, absent-and-declined

## 4. Swap the convention rule

- [x] 4.1 Remove the `namespaced-refs` rule from the rules-doc (its premise — that `/opsx:` is legacy — is false)
- [x] 4.2 Add `no-forked-upstream-assets` in its place, forbidding shipped assets that shadow upstream ones and reserving `/specloop:` for assets with no upstream equivalent
- [x] 4.3 Verify `harness rules` resolves the new id and `harness validate` still fails loudly on a dangling one

## 5. Rewrite every cross-reference

- [x] 5.1 `grep -rn '/specloop:\(explore\|propose\)'` across the repo; enumerate every hit before editing (`/specloop:archive` survives and is not a target)
- [x] 5.2 Update `skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md`
  - No edit needed: neither referenced a deleted command. Their only namespaced reference
    is `/specloop:archive`, which survives. `README.md`, `CLAUDE.md` and
    `.github/pull_request_template.md` did need updating and were not on the original list.
- [x] 5.3 Update `hooks/_session_brief.py` and `commands/start.md` so the brief offers `/opsx:` for authoring and `/specloop:` for the loop, and carry the handoff relocated from `propose.md` (D7): when a change is apply-ready, offer both the interactive and the subagent path, and never auto-start
- [x] 5.4 Update `SETUP.md`
- [x] 5.5 Re-run the grep and confirm zero remaining references to the deleted commands

## 6. README: show the seam

- [x] 6.1 Replace the single-pipeline workflow diagram with the two-column upstream/Specloop split from design D5
- [x] 6.2 Update the "What you get" table — remove the two deleted commands, re-describe `archive` as a delegation that adds the commit, and state what OpenSpec provides alongside
- [x] 6.3 Update the Install section to include `openspec init --tools claude` as a prerequisite step
- [x] 6.4 Add a short migration note: `/specloop:explore|propose` → `/opsx:explore|propose`, and note that `/specloop:archive` keeps its name but now delegates
- [x] 6.5 Document `openspec schema fork` as the supported way to customise authoring, and state that editing a generated `opsx` command is not — it does not survive `openspec update`
- [x] 6.6 Confirm whether `openspec update` actually overwrites modified `.claude/commands/opsx/*` before the migration note recommends running it
  - Verified at CLI v1.6.0: plain `openspec update` compares only the `generatedBy` version
    recorded in the generated skills' frontmatter, so at the same version it is a no-op and
    local edits survive. `openspec update --force` regenerates in place — edits gone, no
    backup, no prompt. A version bump takes the same regenerating path.
  - **Superseded at CLI v1.8.0** (see 8.4): `dist/core/update.js:122-125` unions a second,
    independent trigger — `getToolsNeedingProfileSync(...)` — into the regeneration set, so
    tool/workflow profile drift regenerates even at a matching version. "Same version ⇒
    no-op" is no longer true, and both places that told adopters so are corrected.

## 7. Verify the seam end-to-end

- [x] 7.1 In a throwaway repo with the plugin installed: `/opsx:propose` a trivial change, then `/specloop:tdd-apply` it, and confirm the handoff works with no missing-command errors
  - **Missing-command half: verified mechanically.** Every `/opsx:*` and `/specloop:*`
    reference across `commands/`, `skills/`, `agents/`, `hooks/`, `templates/`, README,
    SETUP and CLAUDE.md was resolved against a freshly-inited upstream command set and
    the plugin's own assets. All resolve. The only two unresolved are `/specloop:explore`
    and `/specloop:propose` in the README migration table's "Was" column — historical
    labels naming what was removed, not invocations.
  - **Live half: partly closed.** The earlier claim that slash commands "cannot be driven
    from a tool call" was wrong — `claude -p --plugin-dir <dir>` with the prompt on stdin
    runs them headlessly. Done live against the brownfield fixture: the plugin loads and
    the full surface resolves (`opsx:{apply,archive,explore,propose,sync}` +
    `specloop:{archive,harness-init,start,tdd-apply,verify}`), so **no missing-command
    errors** is verified rather than inferred. `/specloop:harness-init` ran and produced a
    correct binding analysis interactively.
  - **Closed.** Ran end to end against the brownfield fixture: `/opsx:propose` authored
    `live-os-theme-sync` and committed its artifacts; `/specloop:tdd-apply` picked that
    task list up with no missing-command error and drove 6 of 7 tasks to three commits.
    The handoff this change exists to create works.
  - The loop's *behaviour* under that run — which guarantees held, which could not be
    observed — is recorded as the measured baseline in `harden-unattended-loop` §0, since
    that is the change that makes them enforceable. Two results worth carrying: the run
    stopped at the blocking live-check rather than fabricating a green, and it
    misattributed its own edits to a non-existent third party.
  - Three fixtures remain as git worktrees of `personal-finance-coach` on branches
    `specloop-test/{brownfield,greenfield,stale}`, each with a `TEST-PLAN.md`. The
    greenfield and stale paths have been exercised for detection only, not for the loop.
- [x] 7.2 Confirm the recovered upstream features are reachable — `--store` is accepted, and `/opsx:sync` exists
- [x] 7.3 Confirm the SessionStart brief renders correctly with the new command set
  - Surfaced a pre-existing defect: `hooks/session-brief.sh` re-appended `hooks/` to its
    own directory in the no-`CLAUDE_PLUGIN_ROOT` fallback, so the documented standalone
    invocation silently dropped the whole OpenSpec half of the brief (the pipeline
    swallows the error). Fixed; both resolution paths verified.

## 8. Fix the detection defects found by task 7.1

Found by running the plugin against three real fixtures rather than by reading it. All
four are the same mistake: the preflight and the brief **asserted** the workflow's shape
instead of **detecting** it.

- [x] 8.1 `openspec list --json` exits 0 even with no `openspec/` anywhere, so its exit
      status can never prove initialization — gate on `root.source != "implicit"` instead
      (`implicit` = no root found, `nearest` = resolved)
- [x] 8.2 Replace the `.claude/commands/opsx/` directory-existence test with a per-command
      check of the five commands Specloop's own prompts reference. Deriving the requirement
      from our references rather than upstream's file list avoids re-coupling to upstream's
      manifest, which `no-forked-upstream-assets` exists to prevent
- [x] 8.3 `hooks/session-brief.sh` appended its menu outside the `if [ -n "$changes_summary" ]`
      guard, so it advertised `/opsx:sync` and friends unconditionally. Gate every entry on
      the command being installed; with no OpenSpec, offer onboarding instead of a dead menu
- [x] 8.4 Correct the `openspec update` claim in `commands/harness-init.md` and `SETUP.md`:
      at CLI 1.8.0 a tool/workflow profile drift regenerates even at a matching version, so
      "no-op while the version matches" is no longer true
- [x] 8.5 Collapse `commands/start.md`'s static menu — it was a second, unguarded copy of
      the brief's, and `start.md` already injects the brief's output. One source, not two
- [x] 8.6 Correct the "no-ops quietly without OpenSpec" claim in `CLAUDE.md` — the state
      half no-opped, the menu half never did
- [x] 8.7 Verify the rewritten brief against all three fixtures: brownfield renders the full
      menu, stale omits `/opsx:sync`, greenfield offers onboarding only

## 9. Resolved: the shipped template did not validate

- [x] 9.1 `templates/harness.yaml.template` declared `surfaces[0].rules: [conventions]`
      against `conventions.rules-doc: openspec/config.yaml`, but no rules-doc defines a
      `conventions` rule-id — not an adopter's, not this repo's own — so `harness init`
      followed by `harness validate` failed out of the box. Observed live in the brownfield
      fixture.
      **Fixed in `harden-manifest-parser`** (task 3.2): the template now defaults to a
      single inline prose rule, which needs no rules-doc, with the rule-id form demoted to
      commented guidance. A regression test asserts the shipped template validates.
      `reposition-specloop` 1.12 carries the remaining decision — whether the template
      should point back at a rule-id once a real conventions source exists.

- [x] 9.2 Onboarding binds a gate without ever running it — relocated to
      `reposition-specloop` 1.13, which is the change that promotes onboarding to an owned
      surface. Not fixed here.
