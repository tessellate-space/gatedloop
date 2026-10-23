# Proposal

## Why

The maintainer upgraded OpenSpec from 1.13.1, the version 0.5.0 was tested against, to 1.14.3. Three things in 1.13.2–1.14.3 touch Specloop.

1. **Specloop's approval keys are now "unrecognized change metadata".**
   - **Strict failure (1.14.0).** `openspec status`, `validate` and `archive` name `.openspec.yaml` keys OpenSpec doesn't know, and `validate --strict` fails on them. Specloop writes `approved_by`, `approved_at` and `approved_sha` into every attested change, so every approved change now fails `--strict` and prints a warning on every status, validate and archive.
   - **The fix upstream offers (1.14.2).** Top-level keys starting with a lowercase `x-` belong to tools, are ignored, and pass `--strict`.
   - **Who is affected.** Specloop's own loop runs non-strict validation, so this is noise for most adopters, not a break. It fails anyone who runs `--strict`, which includes this repository's own close-out step.
2. **A hang in hooks (fixed in 1.14.3).** `validate --all` could spin forever on a terminal that reports zero columns, as some pre-commit runners do. `OPEN_SPEC_INTERACTIVE=0` and `CI` now turn the spinner off. The shim runs `openspec` from hooks and from the git pre-commit layer, so it should always say it is not interactive, whatever version is installed.
3. **The tested version.** `TESTED_OPENSPEC_VERSION` is 1.13.1, so `gates doctor` warns everyone on 1.14.

`initiative`, the one upstream key that looked like an epic, is a removed legacy feature. The 1.14 CLI refuses `--initiative`, so `epic-linkage` duplicates nothing.

## What Changes

- **`x-` metadata.** Specloop's change metadata is written as `x-specloop-approved-by`, `x-specloop-approved-at` and `x-specloop-approved-sha`.
  - Every reader accepts either spelling, preferring the new one, so existing approvals, including those on the merge target that `check-implement` reads with `git show`, stay valid with no migration.
  - `gates approval attest` writes the new spelling and removes the old.
  - `gates approval migrate [<change>]` renames the keys on active changes in place. The approval sha covers no `.openspec.yaml`, so it is unchanged.
- **`gates doctor`** warns when an active change still carries the old spelling, naming `gates approval migrate`, and `/specloop:upgrade` offers the migration through a recurring `approval-keys` catalogue item (issue #39's third request).
- **Not interactive.** Every `openspec` subprocess the shim starts gets `OPEN_SPEC_INTERACTIVE=0` in its environment.
- **The version.** `TESTED_OPENSPEC_VERSION` moves to 1.14.3, and this repo's workflow pins 1.14.3.
- **Docs.** SETUP's approval section names the new keys and the migration; README's prerequisites name the tested version.

Out of scope, recorded in `docs/candidates.md`:
- splitting this repository's own 55 requirements that exceed 1.14.1's 500-character strict limit;
- using `openspec list --archived --json`, requirement names in `show --json`, and `openspec version --check --json` in the shim.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `loop-enforcement`: Specloop's change metadata is `x-`-prefixed, and readers accept the earlier spelling.

## Impact

- `bin/gates`:
  - the approval key readers and the writer;
  - `approval migrate`;
  - the doctor row;
  - an `old-approval-keys` detector kind;
  - one helper that every `openspec` subprocess goes through;
  - `TESTED_OPENSPEC_VERSION`.
- `adoption/catalog.json`: the `approval-keys` item.
- `.github/workflows/specloop.yml`: the pin.
- SETUP, README, `docs/candidates.md`.
- Tests.
