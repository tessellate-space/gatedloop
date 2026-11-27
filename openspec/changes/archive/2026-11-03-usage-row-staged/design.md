## Context

`templates/git-hooks/pre-commit` records a usage row on its ledger-grade path and on its normal path (token-ledger D7: a git-layer commit has no transcript, so it records `source: no-transcript` with null counts). Both calls omit `--stage`. `_usage_record` appends the row and, only with `--stage`, runs `git add -- <ledger>`. Without it the row stays in the working tree. `hooks/gate-commit.sh` passes `--stage` on every path.

`git add` inside a pre-commit hook honours `GIT_INDEX_FILE`, which git exports to the hook. git re-reads that index after the hook runs, so a row staged by the hook lands in the commit for a plain `git commit`, for `git commit -a` (its temporary index becomes the real one), and for `git commit <paths>` (the temporary index the commit is built from). The pathspec form has one catch. git updates the *real* index with the listed paths before the hook runs, so the hook's later addition reaches the commit but not `.git/index`. The ledger then matches HEAD in the working tree and differs in the index, and `git status` reports it changed.

Merge step 1 (`_merge_prove_head` → `_commit_ledger_rows`) commits with `git commit -q -m … -- <ledger>`, which is exactly that pathspec form. Step 2 then detaches onto the target and fails on the dirty path (#140).

## Goals / Non-Goals

**Goals:** a commit at the git layer leaves the ledger clean, and `gates merge` reaches step 2 with the shipped git hook installed.

**Non-Goals:**
- deduplicating the two rows an agent-session commit records (D2);
- changing what a usage row holds or how its window is computed;
- a general "tolerate a dirty ledger" rule in step 2.

## Decisions

### D1. The git template stages the row, as the Claude-layer hook does

Both `"${GATES}" usage record` calls in `templates/git-hooks/pre-commit` become `"${GATES}" usage record --stage`. The row then lands in the commit it describes, as D7 intended, and a ledger-grade commit stays ledger-only because the staged path is under `.gatedloop/runs/**`. Recording still can't deny the commit: `|| true` stays, and a failed stage only prints to stderr.

### D2. Keep the git-layer row alongside the Claude-layer row

The template enforces only in an agent session, so a commit made through the Bash tool fires both hooks. It records a transcript-backed row (Claude layer) and a `no-transcript` row (git layer). Dropping the git-layer row in agent sessions would need the template to detect that the tool hook already ran, which is new coupling between the layers. D7's guarantee also matters most where the tool hook was bypassed (a subprocess, a script), and that is when only the git layer fires. A null-count row never moves the task's usage window and adds nothing to totals, so the duplicate costs one ledger line and no wrong numbers. We keep both, and this is the smallest fix.

### D3. Step 1 leaves the ledger clean after its own commit

This is not only defence in depth. D1 alone doesn't fix #140, because step 1's commit is a pathspec commit (Context). After `_commit_ledger_rows` commits, it runs `git reset -q -- <ledger>` so the index entry matches the new HEAD, which already holds the hook's row. It then re-checks `git status --porcelain -- <ledger>`. If the path is still dirty, it raises `_MergeHalt` at the same step and names the path, so the failure surfaces at step 1 rather than as a checkout error at step 2. It doesn't loop or commit again. The cost is two git calls touching one path that step 1 owns. It's safe because, after the commit, the reset only aligns the index with a HEAD that already contains the working-tree content. `_record_on_branch` (later steps) uses the same helper and gets the same guarantee.

### D4. Adoption: a copied hook needs `gates hook install`

`gates hook install` writes the template body into `.git/hooks/pre-commit` with the shim path recorded, so an existing copy keeps the old calls. A composed install (a hook manager) delegates to `${CLAUDE_PLUGIN_ROOT}/templates/git-hooks/pre-commit` and picks up the fix with the plugin version. `gates doctor` already compares a copy with the shipped template (recorded line emptied) and warns `stale-copy` with "Run `gates hook install`", so no new detection is needed. The 0.11.1 CHANGELOG Upgrading note must say: re-run `gates hook install` if `gates doctor` reports the commit hook as a stale copy. D3 needs no adopter action.

## Risks / Trade-offs

- [The pathspec index behaviour is git-internal] → the tests drive real `git commit`, `git commit -a` and `git commit <paths>` through the installed hook and assert a clean tree, so a git that behaves differently fails loudly.
- [Two usage rows per agent-session commit] → accepted (D2). Null counts don't change totals or windows.
