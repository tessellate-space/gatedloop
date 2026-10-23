## 1. Matcher

- [x] 1.1 `_gate_match.py` drops redirection tokens (and a detached target) before argument extraction, per design D1's two patterns; tests for `2>&1`, `> out`, `2>/dev/null`, `<in`, `&>log` on every kind
- [x] 1.2 Heredoc bodies are excluded up to the terminator line and lines after the terminator are still matched; `--help`/`-h` yields `matched=0`; tests cover a heredoc mentioning `git merge`, a real command after a heredoc, and `openspec archive --help 2>&1`
- [x] 1.3 An unparsable merge ref emits `ref_parse=failed`, and `gate-merge.sh` denies with the design D1 message; test through the hook

## 2. Merge gating scope

- [x] 2.1 `gate-merge.sh` exits 0 when the current branch is not the integration target, and treats a detached HEAD at the target's tip as integrating (design D2); tests cover main-into-change (allowed), change-into-main (gated), and detached-at-tip (gated)

## 3. Marker evidence

- [x] 3.1 Delete `hooks/clear-ci-marker.sh` and its `hooks/hooks.json` entry; a test asserts a scratch-file write between `gates run ci` and commit leaves the commit allowed (design D3)
- [x] 3.2 `gate-marker check ci` prints the design D4 diagnosis (all-added → "staged after the gate ran"; otherwise up to 10 differing paths); both commit hooks surface it; tests cover both shapes

## 4. Propose gate

- [x] 4.1 `discipline check-propose` resolves the change from the written path, allows planning writes unless the change is in implementation (design D5), accepts a detached HEAD, labels "unproposed" only for a directory untracked at the target tip, and treats every schema artifact path alike (`tasks.md` excepted); tests cover detached HEAD, a `plan/*` branch, a tracked dir, an untracked dir, and an in-implementation change

## 5. Change resolution and worktrees

- [x] 5.1 `_resolve_change_name` per design D6 (slash refused; directory-backed branches only; archived fallback); `gates run` on a detached HEAD without `--change` prints the no-row line; tests cover `plan/x`, a docs branch, a slash in `--change`, and an archived change
- [x] 5.2 `gates discipline check-worktree` per design D7, called by `gate-commit.sh` and the git-layer pre-commit before the marker check; tests create two worktrees on one branch

## 6. Prompts

- [x] 6.1 `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md` carry design D8's rules 2, 4 and 6 and the D7 forced-checkout rule, naming no stack tool

## 7. Close

- [x] 7.1 `gates run ci` green on the final tree; `openspec validate hook-correctness --strict` passes
