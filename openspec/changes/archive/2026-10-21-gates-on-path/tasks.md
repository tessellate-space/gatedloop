## 1. The fallback

- [x] 1.1 Implement the `hooks/session-brief.sh` env-file fallback per design D1. Tests run the real hook with a temp `CLAUDE_ENV_FILE` and a fake plugin root, covering:
  - a fresh file;
  - no duplicate line on a second run;
  - another writer's lines kept;
  - no file written when either variable is unset;
  - the brief's output unchanged.

## 2. Doctor

- [x] 2.1 Add the `gates-on-path` row per design D2. Tests cover:
  - `gates` found as the running shim;
  - found as a different copy;
  - not found, with the remedy built from the shim's own `bin/`.
- [x] 2.2 `plugin-registered` becomes `shim-location` per design D3. Tests cover:
  - a plugin-cache path, with the version named;
  - a checkout;
  - another path;
  - no warning when `CLAUDE_PLUGIN_ROOT` is unset.

## 3. Docs

- [x] 3.1 Add SETUP's troubleshooting entry per design D4, and update the doctor row list wherever SETUP or README names it. `python3 scripts/release docs` exits 0.

## 4. Close

- [x] 4.1 `gates run ci` green on the final tree; `openspec validate gates-on-path --strict` passes
