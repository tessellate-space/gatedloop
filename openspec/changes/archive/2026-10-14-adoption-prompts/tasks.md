## 1. Catalogue and evaluation (pure)

- [x] 1.1 A pure loader validates `adoption/catalog.json` items (required fields, known detector/predicate/action kinds, options with a recommended first) and fails loud naming the item on any violation (design D1)
- [x] 1.2 Pure evaluators for the detector kinds (`manifest-key`, `rules-target`, `schema-key`, `decision-only`) and predicate kinds (`manifest-key` with `any_of`, `path-exists`), each taking already-loaded inputs; tests cover acted and not-acted for each kind
- [x] 1.3 A pure `undecided(items, project_facts, decisions, installed_version)` implements design D3 (applies, not acted, no applicable decision; `later` applies only at its recorded version; detector beats record); tests cover each branch including `later` across a version change

## 2. Record and commands

- [x] 2.1 `gates adoption record <id> <adopted|declined|later>` writes `.specloop/adoption.json` atomically with `by`/`at`/`version` per design D2, preserving other decisions; refuses unknown ids and decisions without writing
- [x] 2.2 `gates adoption status [--json]` per design D3, reading the installed version from `.claude-plugin/plugin.json` beside the shim; exits non-zero only when it cannot decide
- [x] 2.3 End-to-end tests in a temporary project: fresh project lists every applicable item; setting a manifest key hides its item; `declined` hides permanently; `later` hides until the plugin version differs (simulate by pointing the version source at a fixture)

## 3. Catalogue content and repo checks

- [x] 3.1 Add `adoption/catalog.json` with the five design D8 items, question and option texts written for an adopter, and `detail` texts for the `confirm` items
- [x] 3.2 Amended (design D1 "Unreleased items"): `gates adoption status` skips items whose `since` is later than the installed version; `scripts/release publish` refuses before its first write while any item's `since` is later than the version being published; the `ci` catalogue test asserts well-formed `since` only; tests for all three
- [x] 3.3 `scripts/release`: add `adoption/` to `SHIPPED_PATHS`; `cut` prints the design D7 warning (schema changed since the tag, no item with `since` equal to the new version) and continues; tests cover warn and no-warn; RELEASING.md gains the checklist line

- [x] 3.4 Amended (design D1, D8): predicate kinds `surface-key` and `any`; `runner-strictness` uses `any` of `manifest-key gates.verify`, `manifest-key gates.integration`, `surface-key live-check`; tests cover a project whose only blocking runner is a surface live-check

## 4. Brief, command, onboarding

- [x] 4.1 `hooks/_session_brief.py` adds the design D4 line (items, failure, or nothing); tests drive it with a stubbed `gates adoption status`
- [x] 4.2 Add `commands/upgrade.md` implementing the design D5 walk (status, list, one question per item with "Decide later", action per kind, record immediately, closing status; never commits)
- [x] 4.3 `commands/gates-init.md`: steps that correspond to a catalogue item record the answer there; a final step runs the upgrade walk for anything still undecided (design D6)

## 5. Docs

- [x] 5.1 README and SETUP.md gain a short "Upgrading" section: update the plugin, the session brief tells you when settings wait, `/specloop:upgrade` walks them, commit `.specloop/adoption.json`

## 6. Close

- [x] 6.1 `gates run ci` green on the final tree; `openspec validate adoption-prompts --strict` passes
