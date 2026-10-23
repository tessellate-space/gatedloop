## 1. The plugin identity

- [x] 1.1 Spike, per design D4: verify against Claude Code's docs, and against a local marketplace, what an existing `specloop@specloop` install sees after the marketplace and plugin are renamed. Record the result in design.md before 1.2, then choose between the forwarder plugin and a notice in the last `specloop` release
- [x] 1.2 Rename the plugin and marketplace to `gatedloop`, and add the forwarder plugin if 1.1 says it can reach existing installs (design D4). Tests check the manifests, the forwarder's stubs and its notice

## 2. Read-both and the new names

- [x] 2.1 Add the resolver helpers and the once-per-command warning (design D2): state dir, metadata keys, status contexts, rule ids, hook markers, record branches. Both directories present is refused. Tests cover each identifier, read under the old name and under the new
- [x] 2.2 Every write uses the new names. `marker publish` posts both contexts, and a `.specloop/`-only project keeps writing there (design D2). Tests

## 3. Migration

- [x] 3.1 Add `gates migrate-name` per design D3. Tests cover the `git mv`, an untracked directory, the key rewrite, the hook markers, the printed edits, idempotence, and archived changes left untouched
- [x] 3.2 Add the doctor `name` row and the recurring `rename` catalogue item, `since: 0.7.0` (design D3); tests

## 4. The text

- [x] 4.1 Rename across commands, skills, agents, hooks' messages, templates, schema descriptions, the workflow, README, SETUP, AUTOMATION, RELEASING, CLAUDE.md, `docs/` (including `docs/specloop-map.html` → `docs/gatedloop-map.html`) and `AGENT_INSTALL.md`, whose clone URL is fixed per design D5. Add migration notes to README, SETUP and RELEASING
- [x] 4.2 Add the allow-list grep as a test (design D6) and make it pass. `python3 scripts/release docs` exits 0

## 5. Expiry and close

- [x] 5.1 Propose `remove-specloop-forwarders` (design D7) as its own change directory, a plan only
- [x] 5.2 `gates run ci` green on the final tree; `openspec validate rename-to-gatedloop --strict` passes. The public repository is created afterwards by `go-public-migration` (design D5)
