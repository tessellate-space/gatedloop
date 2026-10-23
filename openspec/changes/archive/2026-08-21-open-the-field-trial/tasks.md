## 1. The feedback skill (permanent surface)

- [x] 1.1 Create `skills/feedback/SKILL.md` per `commands-flat-skills-nested` (a `<name>/SKILL.md` directory, not a flat command)
- [x] 1.2 Implement whitelisted collection ONLY: plugin version, OpenSpec CLI version, `gates doctor`/`gates validate` output, the command/gate involved, `.gates.yaml` shape (gate **names** + surface **globs**), OS/platform. Everything else excluded by default — a positive allowlist, never a denylist (design D3)
- [x] 1.3 Guarantee gate command **bodies** are never read — record the gate name and its surface globs, never the string the name maps to (design D3)
- [x] 1.4 Resolve the repository slug from `plugin.json`'s `repository` via `${CLAUDE_PLUGIN_ROOT}` (`plugin-relative-paths`, `self-contained-plugin`); never hard-code `radub21/specloop` in prose (design D2)
- [x] 1.5 Assemble the complete literal issue body and show it in full to the tester; post nothing until explicit approval — a summary must not substitute for the literal body (design D3)
- [x] 1.6 Support both kinds of report, distinguished by label at creation: `field-report` for a positive "worked in stack X" confirmation, `bug`/`friction` for a problem; identical privacy + approval rules for both (design D8)
- [x] 1.7 Post via `gh issue create -R <slug>` with the label; confirm the post is the FIRST network call that could publish, i.e. it happens only after approval
- [x] 1.8 Degrade loud when `gh` is missing/unauthenticated/offline: print the full body and the `<repository>/issues/new` URL for manual filing, and state plainly that nothing was posted — never drop the report silently (`fail-loud-gates` spirit, design D3)

## 2. Issue templates (structure for reports arriving outside the skill)

- [x] 2.1 Add `.github/ISSUE_TEMPLATE/bug-friction.md` (or `.yml`) mirroring the skill's whitelisted fields, labeled for bug/friction
- [x] 2.2 Add `.github/ISSUE_TEMPLATE/field-report.md` (or `.yml`) mirroring the same fields, labeled for a positive field report
- [x] 2.3 Ensure no template instructs a reporter to paste diffs, project files, or gate command bodies — templates ask for the whitelisted context only (design D3)
- [x] 2.4 Add `.github/ISSUE_TEMPLATE/config.yml` if a contact/blank-issue policy is wanted; leave `.github/pull_request_template.md` untouched

## 3. The field guide (time-scoped)

- [x] 3.1 Create `docs/field-guide.md` with a top note stating it is trial-scoped and expected to be retired at trial end, pointing at `README.md`/`SETUP.md` for durable guidance (design D4)
- [x] 3.2 Setup checklist starting at **step zero — get collaborator access**, stating the repo is private so marketplace-add and `gh` both need an invite; then the ordered prerequisites to a first working loop
- [x] 3.3 Document the four journeys with a "good outcome looks like…" for each: onboarding (`openspec init --tools claude` → `/specloop:gates-init` → `gates validate`), the loop (`/opsx:propose` → `/specloop:tdd-apply`), the unattended `tdd-implementer` agent, the SessionStart brief; frame manual testing as the test suite (no prompt oracle)
- [x] 3.4 Document the sharp edges, each labeled shipped-vs-proposed (design D7): six-step onboarding chain; the invisible install + the `echo $CLAUDE_CONFIG_DIR` plain-shell check; hooks need a fresh session; `gates-init` overwrites `.gates.yaml` with only a warning (FR4); propose-on-`main`/one-branch-per-change; `gh pr merge` not hook-gated like `git merge` (PR specloop PR 8); the `harness`→`gates` migration table
- [x] 3.5 Add a roadmap / in-flight summary so testers can tell *coming* from *broken*
- [x] 3.6 Close with a "how to report back" section handing off to `/specloop:feedback`

## 4. README refresh (deliverable 1)

- [x] 4.1 Add a short, prominent **Field trial** section near the top linking to `docs/field-guide.md`, without displacing the ladder / boundary / three-owner content
- [x] 4.2 Verify the install and first-run commands against current `main`: shim named `gates`, enforcement layer shipped (specloop PR 8); fix any name or step that has since changed so the README describes current reality, not aspiration

## 5. Validation and close-out

- [x] 5.1 `openspec validate --change open-the-field-trial --strict` passes
- [x] 5.2 `./bin/gates run ci` exits 0 (this change adds docs/skill/templates, no shim or manifest change)
- [x] 5.3 `claude plugin validate .` passes with the new skill and templates present
- [x] 5.4 Confirm the two new capabilities archive cleanly: `feedback-channel` and `field-trial` each carry a `## Purpose` and at least one scenario per requirement
