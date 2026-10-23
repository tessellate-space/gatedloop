## 1. Remove the forwarder

- [x] 1.1 `git rm bin/harness`
- [x] 1.2 Grep the repo for any remaining reference to `bin/harness` as a live path (not a historical record) and fix it

## 2. Remove the manifest fallback

- [x] 2.1 In `bin/gates`: drop `LEGACY_NAMES` from manifest resolution; `_find_manifest` only ever looks for `.gates.yaml` / `.gates.yml` / `.gates.json`
- [x] 2.2 Drop the `harnessVersion` acceptance in `_errors`; `gatesVersion` is the only recognized key
- [x] 2.3 Remove the "both exist" and legacy-filename/legacy-key warning branches from `load_manifest`
- [x] 2.4 Update `tests/test_manifest.py`: delete `TestLegacyVersionKey`, and confirm no other test depends on the fallback

## 3. Update the spec and shipped docs

- [x] 3.1 Mark the two compatibility requirements REMOVED in `openspec/specs/gate-binding/spec.md` (via this change's delta spec)
- [x] 3.2 Remove the forwarder/fallback migration notes from `README.md`, `SETUP.md`, `CLAUDE.md` (README.md/SETUP.md's "still works for one release" notes rewritten; CLAUDE.md's only mention is already-past-tense narrative that doesn't claim the old names still work, so it needed no edit)

## 4. Verify

- [x] 4.1 `python3 -m unittest discover -s tests` green
- [x] 4.2 In a throwaway repo with a `.harness.yaml`: confirm `gates validate` now fails with "no manifest found" rather than a warning
- [x] 4.3 `claude plugin validate .` passes
