## 1. The rule

- [x] 1.1 Add `docs-follow-surface` to `docs/conventions.md` per design D2; add it to the `prompts` and `shim` surfaces in `.gates.yaml`; run `./bin/gates conventions sync` and commit the regenerated `openspec/config.yaml`; `gates validate` passes

## 2. The inventory check

- [x] 2.1 `scripts/release docs` per design D3 (inventory from files, forward and reverse checks, `DOCS_EXEMPT` with reasons, one line per gap with file and line, exit 1 on any); tests in `tests/test_release.py` with a fixture tree cover an undocumented command, a stale `gates` subcommand mention, an exempt item, and a clean pass
- [x] 2.2 `cut` runs the docs check first and refuses before any write while it fails; `status --hook` names `/release-docs` (design D5); tests

## 3. The docs pass

- [x] 3.1 Add `.claude/commands/release-docs.md` per design D4
- [x] 3.2 RELEASING.md procedure and explanation (design D5); CLAUDE.md's release paragraph names the docs pass

## 4. First use

- [x] 4.1 Run `scripts/release docs` against current `main` and fix every gap it reports in README.md and SETUP.md (this is the pre-0.5.0 baseline; later changes in the release keep it clean under the new rule)

## 5. Close

- [x] 5.1 `gates run ci` green on the final tree; `openspec validate release-docs-sync --strict` passes
