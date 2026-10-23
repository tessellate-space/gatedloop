## 1. The script

- [x] 1.1 Add `scripts/go-public plan` and `map.json` (design D2); tests use the fake `gh`
- [x] 1.2 Add the reference rewriter and the email scrub (design D3, D4), with fixture tests for code spans, headings, URLs and unknown numbers, and a rewrite report
- [x] 1.3 Add `tree <dir>`, which exports with no history and enforces the design D5 checks; tests
- [x] 1.4 Add `transfer` (resumable; it remaps moved issues' bodies and comments) and `push` (noreply identity, refuses unless D5 holds); tests use the fake `gh`

## 2. Docs

- [x] 2.1 Add "Publishing the public repository" to `RELEASING.md` (design D1), and point `rename-to-gatedloop` design D5 here

## 3. Close

- [x] 3.1 `gates run ci` green; `openspec validate go-public-migration --strict` passes
