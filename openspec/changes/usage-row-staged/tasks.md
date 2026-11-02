## 1. The git layer stages its usage row

- [ ] 1.1 In `templates/git-hooks/pre-commit`, pass `--stage` to both `gates usage record` calls (ledger-grade and normal path). Tests install the hook in a real repo on a change branch with a ledger and, for `git commit`, `git commit -a` and `git commit <paths>`, assert that the commit holds the `no-transcript` row and `git status --porcelain` is empty for the ledger (design D1, D2) [oracle: unit]

## 2. Merge step 1 leaves the ledger clean

- [ ] 2.1 In `_commit_ledger_rows`, after the commit, reset the ledger's index entry to HEAD and re-check its status, halting at the same step with an explicit message if it's still dirty. A test runs `gates merge` with the shipped git hook installed in the lane and trailing rows pending, and asserts that step 1's commit holds the hook's row and the merge gets past step 2's detach (design D3) [oracle: unit]

## 3. Docs

- [ ] 3.1 In SETUP.md's git-hook section and AUTOMATION.md's token-ledger notes, say that a commit at either layer stages its own usage row, and that a copied hook needs `gates hook install` (reported by `gates doctor` as `stale-copy`). Note the Upgrading line the 0.11.1 CHANGELOG must carry (design D4) [oracle: none]
