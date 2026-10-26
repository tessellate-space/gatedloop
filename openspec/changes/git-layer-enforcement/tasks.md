# Tasks

## 1. Agent sessions are declared

- [x] 1.1 `discipline.agent-env` in `schema/gates.schema.json` and `gates validate` (list of non-empty identifiers, default `[CLAUDECODE]`); `gates discipline agent-session` per design D1; tests for default, a second variable, an invalid value.
- [x] 1.2 `templates/git-hooks/pre-commit` uses `discipline agent-session` and the three-step shim resolution of design D2; the template test and the hook tests pass with `CLAUDECODE` and with a declared second variable.

## 2. The push gate

- [x] 2.1 `gates discipline check-push <sha>` per design D3: merge-row pass, incoming-tree checks pass, each unmet check named with `gates merge` as remedy; tests drive a real repo with a target branch, a `gates merge` squash (passes), a raw merge with no markers (denied), a feature-branch push (ignored), a deletion (ignored).
- [x] 2.2 `templates/git-hooks/pre-push` reading git's stdin lines and calling `check-push` only for the merge target; test the hook end to end through `git push` to a local bare remote, inside and outside an agent session.

## 3. Install, doctor, adoption, onboarding

- [ ] 3.1 `gates hook install` installs both templates under one owner detection, writes the shim path fallback, and the stale check normalizes that line, per design D2 and D4; tests for fresh install, husky composition, refuse-and-instruct, a stale copy of either hook.
- [ ] 3.2 `gates doctor` `git-push-hook` row with the five states; test each.
- [ ] 3.3 Adoption: `git-hook-refresh` detector covers both hooks; new `git-push-hook` item per design D4; `commands/gates-init.md` offer names both hooks; tests for the catalogue.

## 4. Docs

- [ ] 4.1 AUTOMATION.md coverage table per design D5; SETUP.md (`discipline.agent-env`, the push gate, `hook install` for two hooks, the shim-path fallback); README.md requirements say which hosts run which layer. `python3 scripts/release docs` exits 0.

## 5. Close

- [ ] 5.1 `gates run ci` green on the final tree; `openspec validate git-layer-enforcement --strict` passes.

## Workflow follow-up

- If `test-lock-remote-check` lands first, add the lock evaluation to `check-push` in task 2.1; otherwise leave the condition out and note it in that change.
