## 1. Confirm the mechanics before moving files

- [x] 1.1 Verify how the plugin puts `bin/` on the Bash tool's PATH, and confirm no binary name is recorded in `.claude-plugin/plugin.json` (open question — if one is, it must be updated in lockstep). Confirmed: `plugin.json` names no binary anywhere; the platform adds the whole `bin/` directory to PATH regardless of filename, so renaming `bin/harness` → `bin/gates` needs no lockstep update elsewhere.
- [x] 1.2 Enumerate every reference: `grep -rn '\bharness\b' --include='*.md' --include='*.json' --include='*.sh' --include='*.py' --include='*.yaml' .` — save the list as the completion checklist for section 6. 34 files matched (prompts, hooks, schema, tests, docs, and change artifacts); used as the checklist for sections 2-6.

## 2. Rename the shim and its assets

- [x] 2.1 `git mv bin/harness bin/gates`; confirm the shebang, exec bit, and stdlib-only property are preserved (`zero-dep-shim`)
- [x] 2.2 `git mv schema/harness.schema.json schema/gates.schema.json`; update its `$id` and any `title`/`description` naming the old term
- [x] 2.3 `git mv templates/harness.yaml.template templates/gates.yaml.template`; update its inline comments and the `harnessVersion` key
- [x] 2.4 `git mv commands/harness-init.md commands/gates-init.md`; update its frontmatter `name`/`description` and body
- [x] 2.5 Update `gates init` so it writes `.gates.yaml` from the renamed template

## 3. Manifest key + loader

- [x] 3.1 Accept `gatesVersion` as the current version key
- [x] 3.2 Detect `harnessVersion` as the legacy key: load successfully, warn loudly, name the replacement
- [x] 3.3 Resolve the manifest filename: prefer `.gates.yaml`; fall back to `.harness.yaml` with a loud warning; when both exist, use the new one and report that the old is ignored
- [x] 3.4 Verify the fallback paths never succeed silently (`fail-loud-gates`). Verified live in a throwaway repo: no-manifest, fresh init, legacy filename, legacy key, and both-present all print an explicit warning to stderr — never a quiet success.

## 4. Deprecation forwarder

- [x] 4.1 Add a minimal `bin/harness` that prints a deprecation notice to stderr and `exec`s `bin/gates` with the same argv
- [x] 4.2 Verify the exit code is passed through unchanged for both a passing and a failing gate — a forwarder that swallows a non-zero exit would silently disable every gate. Verified in a throwaway repo: `gates: "exit 7"` forwards exit 7, `gates: "exit 0"` forwards exit 0, both preceded by the deprecation notice on stderr.
- [x] 4.3 Open the follow-up change that deletes the forwarder and the `.harness.yaml` fallback, so the expiry is tracked rather than remembered. Opened `openspec/changes/remove-harness-compat` (proposal + tasks + a REMOVED-requirements delta on `gate-binding`); `openspec change validate --strict` passes.

## 5. Update every shipped reference

- [x] 5.1 `skills/tdd-apply/SKILL.md` and `skills/verify/SKILL.md`
- [x] 5.2 `agents/tdd-implementer.md` and `agents/convention-review.md`
- [x] 5.3 `commands/start.md`, `hooks/session-brief.sh`, `hooks/_session_brief.py`. Only `hooks/session-brief.sh` had references (gate hints, the harness-init slash-command, the "run the local gates" line); the other two had none.
- [x] 5.4 `README.md`, `SETUP.md`, `CLAUDE.md`, `AUTOMATION.md` — including a short migration note naming both the file and the command rename. Added a "Migrating from an earlier Specloop" table row (README) and a "Migrating from harness" section (SETUP) naming the shim, manifest, and command renames plus the one-release forwarder/fallback.
- [x] 5.5 `openspec/config.yaml`: the rules-doc prose referring to the shim by name

## 6. Update the in-flight planning artifacts

- [x] 6.1 `reposition-specloop`: replace `harness`/`.harness.yaml` references, and confirm its open question about the name now reads as resolved rather than open. Confirmed `design.md`'s Open Questions already reads "RESOLVED (D8): gates. Executed by rename-to-gates." No prescriptive `harness` references remained to replace — the only surviving matches are (a) the Non-Goals bullets naming the `harness` → `gates` transformation itself, (b) an unrelated quoted phrase ("testing harnesses") from an external tool survey, and (c) `tasks.md` 1.11-1.13's historical narrative quoting the actual `/specloop:harness-init` invocations observed live during `unfork-commands`, before this rename existed — left as-is since rewriting them would misrepresent what was actually run at the time.
- [x] 6.2 `harden-unattended-loop`: rename `harness run` / `harness gate-marker` throughout proposal, design, spec and tasks. Already written entirely in `gates` vocabulary (`gates run`, `gates gate-marker check`, `bin/gates`) — zero `harness` matches; nothing to change.
- [x] 6.3 `workflow-packs` and `unfork-commands`: same sweep. `workflow-packs/design.md` had one prescriptive `bin/harness` mention (hot-surface selection reasoning), renamed to `bin/gates`. `unfork-commands` is already archived (`openspec/changes/archive/2026-08-18-unfork-commands/`) — its `harness` mentions are historical record, per design D5's carve-out, and are left untouched.
- [x] 6.4 Re-run `openspec validate <each> --strict` after editing. `reposition-specloop`, `harden-unattended-loop`, `workflow-packs`, and `rename-to-gates` itself all report valid.

## 7. Verify mechanically, not by review

- [x] 7.1 Re-run the section 1.2 grep; confirm the only surviving matches are the forwarder, the migration notes, and historical records (archived changes, `docs/specloop-map.html`). Caught 5 files section 5's explicit list missed: `.claude-plugin/marketplace.json`, `.github/pull_request_template.md`, `templates/rules-doc.template.md`, and two live main specs (`openspec/specs/manifest-parsing`, `command-surface`) — fixed all five (the two main specs via a Purpose direct-edit + new MODIFIED delta specs in this change, since D5's allowed list didn't anticipate a live main spec whose modifying change hasn't archived yet; noted as a design gap in the final report). Remaining matches after the fix are exactly: the forwarder (`bin/harness`), README/SETUP/CLAUDE's migration notes, archived changes (historical), this change's own proposal/design/specs/tasks (which narrate the harness→gates transformation by name), `remove-harness-compat`'s artifacts (same reason), and the two main specs' pre-archive requirement bodies (will read `gates` once this change is archived and its deltas apply).
- [x] 7.2 In a throwaway repo: `gates init` → `gates validate` → `gates run ci` all work end to end. Verified: init writes `.gates.yaml`, validate passes, run ci executes and exits 0.
- [x] 7.3 In the same repo: rename the manifest back to `.harness.yaml` and confirm it still validates *with* a warning; invoke `harness validate` and confirm it forwards *with* a deprecation notice. Both confirmed: `gates validate` against the renamed `.harness.yaml` warns and still exits 0; `bin/harness validate` prints the forwarder's deprecation notice, then the filename warning, then validates successfully.
- [x] 7.4 `claude plugin validate .` passes. Confirmed directly and via every `gates run ci` invocation across this run.
