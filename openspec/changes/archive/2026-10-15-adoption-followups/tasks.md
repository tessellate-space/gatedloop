## 1. Hook state

- [x] 1.1 Recognize a direct copy and whether it is current (design D1). `_hook_state` gains `stale-copy`, and `gates doctor` warns on it, naming `gates hook install` (D7). Tests cover a current copy, an older copy, a composed husky hook, a foreign bare hook, and no hook
- [x] 1.2 `gates hook install` refreshes a stale direct copy per design D3: `.specloop-prev` backup, executable bit, and a message naming both paths. A current copy still gets "nothing to do". Tests cover both, a second refresh overwriting the backup, and a foreign hook still refused

## 2. Adoption kinds and recurring items

- [x] 2.1 Detector `git-hook-current` and predicate `git-hook-copy`, reading one `facts["hook"]` gathered by the doctor's code path (design D2). The loader accepts both and still fails loud on an unknown kind. Tests for each
- [x] 2.2 `recurs` per design D4. The loader accepts a boolean and rejects anything else. `_decision_applies` ignores `adopted` and version-scopes `declined` for a recurring item. Tests cover every scenario in the upgrade-adoption delta, plus a non-recurring item whose behaviour is unchanged

## 3. Catalogue and prompts

- [x] 3.1 Add `git-hook-refresh` (D6) and `confirm-gate` (D5) to `adoption/catalog.json`. A test runs both through `gates adoption status` on fixture projects covering the listed and not-listed scenarios in the delta
- [x] 3.2 `commands/upgrade.md`: a recurring item can come back after an earlier `declined`, and the walk says so when it asks. `commands/gates-init.md`: the hook-install step's description mentions the refresh

## 4. Docs

- [x] 4.1 SETUP's "Upgrading" section and its hook section describe the refresh and the backup file. `RELEASING.md` says a hook-template change needs no new catalogue item because `git-hook-refresh` recurs. `python3 scripts/release docs` exits 0

## 5. Close

- [x] 5.1 `gates run ci` green on the final tree; `openspec validate adoption-followups --strict` passes
