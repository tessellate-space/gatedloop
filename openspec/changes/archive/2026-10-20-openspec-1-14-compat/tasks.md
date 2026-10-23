## 1. Approval keys

- [x] 1.1 Add `_approval_meta` per design D2, and route every approval-key reader through it: the working tree, `git show` from the target, `approval check`, and the acceptance brief. Tests cover old-only, new-only, and both (new wins), including through `check-implement` against a merged 0.5.0-style approval
- [x] 1.2 `_write_approval_keys` writes the new keys and removes old ones (design D2). A test runs real `openspec validate --strict` when `openspec` is on PATH and skips otherwise, plus a pure test of the written keys
- [x] 1.3 Add `gates approval migrate [<change>]` (design D3) and the doctor row `approval-keys` (design D4); tests

- [x] 1.4 The `old-approval-keys` detector kind and the recurring `approval-keys` catalogue item, `since: 0.5.1` (design D4a); tests for the detector and the listed and not-listed cases

## 2. OpenSpec invocation

- [x] 2.1 Add the `_openspec` helper with `OPEN_SPEC_INTERACTIVE=0` and route every existing `openspec` subprocess through it (design D5). A test uses a fake `openspec` on PATH that records its environment
- [x] 2.2 Set `TESTED_OPENSPEC_VERSION = "1.14.3"` and the workflow pin `@fission-ai/openspec@1.14.3` (design D6); the doctor tests are updated

## 3. Docs

- [x] 3.1 Docs:
  - SETUP's approval section names the new keys, the fallback and `gates approval migrate`, with a migration-table row for the rename;
  - README's prerequisites name OpenSpec 1.14.3;
  - `docs/candidates.md` gains the three design D7 entries.

  `python3 scripts/release docs` exits 0.

## 4. Close

- [x] 4.1 `gates run ci` green on the final tree; `openspec validate openspec-1-14-compat --strict` passes
