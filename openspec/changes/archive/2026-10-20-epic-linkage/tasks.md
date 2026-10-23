## 1. Linkage

- [x] 1.1 Read `x-specloop-epic` from a change's `.openspec.yaml` through `_load` (PyYAML not required), for active and archived changes (design D1); tests
- [x] 1.2 Add the epic checks to `gates validate` per design D2: missing, self, nested, or an active child of an archived epic, each naming the change; tests for each

## 2. Guarantees

- [x] 2.1 `discipline check-implement` refuses an epic per design D3. Tests drive the real `gate-implement.sh` hook with PreToolUse JSON and set `CLAUDECODE` explicitly
- [x] 2.2 `discipline check-archive` refuses an epic with an open child per design D4, listing children and states; tests through `gate-archive.sh`, plus a drained epic allowed

## 3. Roll-up

- [x] 3.1 `gates epics [--json]` with child states per design D5, sharing the outcomes classifier. Tests cover every state, `drained`, and agreement with `stats --outcomes`
- [x] 3.2 `gates stats --epic <name> [--json]` per design D6; tests
- [x] 3.3 The session brief's epic lines per design D7. A test shows a repository with no epics produces a byte-identical brief

## 4. Docs

- [x] 4.1 Docs:
  - `docs/running-at-scale.md`: "Draining an epic" per design D8, using only shipped commands;
  - SETUP: `x-specloop-epic` and the two guarantees;
  - README: the command reference.

  `python3 scripts/release docs` exits 0.

## 5. Close

- [x] 5.1 `gates run ci` green on the final tree; `openspec validate epic-linkage --strict` passes
