## Why

The git-layer pre-commit template (`templates/git-hooks/pre-commit`) records a `no-transcript` usage row on both its ledger-grade path and its normal path (token-ledger D7), but calls `gates usage record` without `--stage`. The row is appended after the index is built, so it never lands in the commit it describes. Every commit made with the shipped git hook installed leaves `.gatedloop/runs/<change>.jsonl` dirty (#140).

That breaks `gates merge` under `local-squash-merge` every time:

1. step 1 finds the dirty ledger and commits the trailing rows;
2. that commit fires the pre-commit hook, which appends a fresh unstaged row;
3. step 2 can't detach onto the target because the ledger has local changes.

Committing the row by hand doesn't help, because that commit appends another one. The Claude-layer hook (`hooks/gate-commit.sh`, `record_usage`) already passes `--stage`, so only the git layer is affected.

## What Changes

- The git template's two `gates usage record` calls pass `--stage`, as `gate-commit.sh` does, so the row lands in the commit it describes.
- Merge step 1's trailing-rows commit leaves the ledger clean even though its commit is a pathspec commit: after committing, step 1 syncs the ledger's index entry to the new head and re-checks the path. If it's still dirty, step 1 halts with an explicit message instead of letting step 2 fail on checkout.
- SETUP.md and AUTOMATION.md say that a commit at either layer stages its own usage row, and that an adopter with a *copied* hook gets the fix only after `gates hook install`, which `gates doctor` already reports as `stale-copy`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `token-accounting`: a usage row recorded by a commit hook, at either layer, is staged into that commit, so a commit leaves the ledger clean.

## Impact

- `templates/git-hooks/pre-commit`, `bin/gates` (`_commit_ledger_rows`), `tests/`, SETUP.md, AUTOMATION.md.
- Ships in the 0.11.1 patch. The CHANGELOG Upgrading note must tell adopters with a copied hook to re-run `gates hook install`.
