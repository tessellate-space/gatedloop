## 1. Shared matcher

- [x] 1.1 Write failing unit tests for `hooks/_gate_match.py` in `tests/` covering
  every spec scenario: `merge` matches while `merge-base`/`merge-tree`/`merge-file`
  do not; quoted prose containing "git merge" does not match; `git -C <path> merge`
  and `git -c k=v merge` match; `cd x && git merge y` matches; leading env
  assignments / `command` / `env` wrappers are skipped; `/usr/bin/git merge`
  matches by basename; unbalanced quotes fall back to substring behavior (still
  fires); `openspec archive <name>` extracts `<name>` from the matched simple
  command; `git checkout -b <branch>` / `git switch -c <branch>` extract
  `<branch>` from the matched command only (a `-b` in a *different* simple command
  does not leak); `openspec new change` matches as consecutive tokens. Verify:
  `python3 -m unittest discover -s tests` fails on the new tests only.
- [x] 1.2 Implement `hooks/_gate_match.py` per design D1–D3: stdlib-only, reads
  hook JSON on stdin plus a kind argument (`git-commit`, `git-merge`,
  `openspec-archive`, `implement-branch`, `openspec-scaffold`), emits
  `shlex.quote`d `matched=`/`hook_cwd=`/per-kind assignment lines for `eval`.
  Verify: all 1.1 tests pass green via `gates run ci`.

## 2. Hooks on the shared matcher

- [x] 2.1 Rewire `hooks/gate-merge.sh` and `hooks/gate-commit.sh` to delegate JSON
  parse + matching to `_gate_match.py` (resolving it plugin-relative, same pattern
  as their `GATES` resolution), deleting their inline python and `case` substring
  patterns. Verify by piping crafted PreToolUse JSON through each script:
  `git merge-base …` input exits 0 untouched; `git merge x` input without a marker
  exits 2 with the denial; `gh issue create --body "… git merge …"` exits 0.
- [x] 2.2 Rewire `hooks/gate-archive.sh`, `hooks/gate-implement.sh`, and
  `hooks/gate-scaffold.sh` the same way, taking `change`/`branch` from the
  matcher's extraction instead of their own token scans. Verify by piping crafted
  JSON: prose mentioning "openspec archive" passes; a real
  `openspec archive <unmerged>` is denied; `git checkout -b <known-change>`
  without approval is denied while `git checkout -b unrelated-branch` passes;
  confirm no `case … in *"…"*` command pattern remains in any `hooks/gate-*.sh`
  (`grep -n '\*"' hooks/gate-*.sh` finds nothing).

## 3. Archive-move commit classification

- [x] 3.1 Write failing unit tests for the planning-grade classification in
  `bin/gates` (design D4): `_staged_change_dirs`-level behavior never yields the
  literal `archive` segment; a staged pure archive move (deletions under
  `openspec/changes/<name>/**`, additions under
  `openspec/changes/archive/<dated>/**`) selects the planning-grade rung, skips
  `openspec validate` for the moved-away dir, and announces the skip; a still-
  present change dir is validated exactly as before. Verify: the new tests fail
  for the current code.
- [x] 3.2 Implement D4 in `bin/gates` (`_staged_change_dirs` + the `check-commit`
  planning-grade rung), keeping the allow message explicit about which rung passed
  and what was skipped and why. Verify: 3.1 tests pass and the pre-existing suite
  stays green (`gates run ci`).

## 4. Denial-message audit

- [x] 4.1 Audit every denial path in `hooks/gate-*.sh` and `cmd_discipline`
  (`check-commit`, `check-propose`, `check-archive`, `check-implement`) against
  design D5: each names the unmet prerequisite concretely and the exact command
  that satisfies it — including `check-archive` gaining the "merge branch
  '<change>' to '<target>' (and push where the target is a remote ref), then
  re-run `openspec archive <change>`" remedy. Verify: run each denial path (or its
  unit test) and confirm every emitted message contains both the prerequisite and
  a runnable command; no message requires reading enforcement source to act on.

## 5. Integration

- [x] 5.1 End-to-end check in a scratch repo with the plugin's hooks wired: run the
  false-positive reproductions from #8/#40 (`git merge-base --is-ancestor`,
  `gh issue create --body '… git merge …'` shape) and confirm they pass; run a real
  unmarked `git merge` and confirm the denial; walk a merged change through
  `openspec archive` + `git commit` of the move with no ledger-row staging and
  confirm the commit lands at planning grade (#16 item 4's repro). Verify: all
  behaviors observed as specified, `gates run ci` green on the final tree.
