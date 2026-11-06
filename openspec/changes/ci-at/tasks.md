# Tasks

## 1. The mode and its validation (D1)

- [x] 1.1 Add `ci-at` (`task` | `ready`) to `LOOP_KEYS` with an effective-mode helper that reads absent or malformed as `task`. Make `gates validate` fail on another value, naming the key and both values, and on `ready` with no global `gates.unit`, naming the missing gate. Add `loop.ci-at` to `schema/gates.schema.json`. Verify with tests for absent, `task`, `ready` with `unit`, `ready` without a global `unit` (a surface-only `unit` override included) and an unknown value [oracle: unit]
- [x] 1.2 Document `loop.ci-at` in SETUP.md as a new `### loop.ci-at` section beside the retry budget: the two values, the default, the `unit` requirement, where the full `ci` runs under each mode, and changing the key between changes rather than mid-change. Verify `scripts/release docs` reports no gap for the key [oracle: none]

## 2. The commit gate under ready (D2, D3, D7)

- [x] 2.1 Under `ready`, make a green `gates run unit` (single or union) write a tree-keyed `unit` marker with its scope. Make `_check_commit_verdict`'s marker rung try the `ci` marker first and then, on a branch naming an active change, the `unit` marker, allowing with the token `unit` and an allow line naming `loop.ci-at: ready`. Make a denial there name `gates run unit`. Verify with tests on real repositories: a `unit`-only commit allowed under `ready` (token `unit`); the same commit denied under `task` and with the key absent; denied under `ready` on `main`, on a `plan/*` branch and on a detached HEAD; a `ci` marker still allowed under `ready` (token `marker`); ledger and planning grades unchanged; no `unit` marker written under `task`; and a `gates merge` squash commit still needing a `ci` marker [oracle: unit]
- [x] 2.2 In `hooks/gate-commit.sh` and `templates/git-hooks/pre-commit`, treat the `unit` token like `marker` (the authored-test lock, then usage), print the check's allow line for `unit`, and end each denial with a gate-neutral remedy. Verify with tests driving both layers on the same repository under `ready`: both allow a `unit`-gated commit and print the line naming the mode, both deny it when `gates tests check` fails, and both deny a commit with no marker. A `ci`-marker commit's tool-layer output stays unchanged [oracle: unit]
- [x] 2.3 Make `gates task start` and a successful `gates tests handoff` print the commit-gate line on stderr (`gates run ci`, or `gates run unit` with the READY note under `ready`), leaving stdout unchanged. Verify with tests for both commands under both modes, asserting stdout is as before and that a refused handoff prints no line [oracle: unit]
- [x] 2.4 Document the `unit` verdict token and the allow line in SETUP.md (the `check-commit` and `--verdict-file` paragraph and the enforcement section) and AUTOMATION.md (what each layer requires under each mode, the gate-neutral denial). Add the commit-gate line to the `gates task start` and `gates tests handoff` entries of SETUP.md's command reference. Verify `scripts/release docs` reports no gap [oracle: none]

## 3. The full ci at READY, and the audit (D4)

- [x] 3.1 Under `ready`, make `gates ledger record-ready` refuse with exit 1, write no row, and name an unscoped `gates run ci` on the head unless `_ready_gates` would report `ci: pass`. Verify with tests: refused under `ready` with no full `ci` row, refused with only a scoped or union `ci` row, allowed after an unscoped green `ci` on the head (ledger-blind), and unchanged under `task` (row appended, `"ci": "fail"` printed) [oracle: unit]
- [x] 3.2 Under `ready`, make `_GreenCiMatcher` also index green `unit` rows for `rows_for` (never for `has_unscoped`), as used by both `cmd_audit` and `_unrecorded_commits`. Verify with tests on real repositories: under `ready` a unit-gated task commit audited by the `Stop` hook before any full `ci` records no taint and no `vouched` row and is classified by session; under `task` the same commit taints; under `ready` a commit with no row taints until a READY `ci` vouches for it; a `unit` row never vouches for an ancestor; and `gates merge` step 1 on a branch no worktree holds names no unit-gated commit under `ready` [oracle: unit]
- [x] 3.3 Document in AUTOMATION.md (the audit layer) and SETUP.md (`loop.ci-at`) that under `ready` the audit accepts `unit` rows, that READY refuses without the full `ci`, and that the merge is unchanged. Verify `scripts/release docs` reports no gap [oracle: none]

## 4. The budget and the outcomes view (D5)

- [x] 4.1 Make `_attempt_state` count, after the RED run, red rows of the commit gate (`unit` under `ready`) beside the oracle gate and `ci`, threading the mode through `_budget_refusal` and `failed_attempt_count`. Verify with tests: under `ready` a red `unit` after an `[oracle: integration]` task's RED run counts; under `task` it does not; an untagged task's red `unit` counts once; and a red READY `ci` with every task checked in HEAD is no task's attempt and is not refused [oracle: unit]
- [ ] 4.2 Under `ready`, make `gates stats --outcomes` count a restart as recovered on a green `unit` of the task followed by its commit, with `task` behaviour unchanged. Verify with tests for both modes [oracle: unit]
- [ ] 4.3 Update SETUP.md's retry-budget section and the `loop.attempts` description in `schema/gates.schema.json` to say the commit gate's red runs count under `ready` and the READY `ci` is change-level. Add a `docs/candidates.md` entry for a code-enforced budget on the READY `ci`. Verify `gates validate` and `scripts/release docs` pass [oracle: none]

## 5. Union-scoped ci (D8)

- [ ] 5.1 Add `ci-scope` (`single` | `union`) to `LOOP_KEYS`, `gates validate` and `schema/gates.schema.json`. Make the multi-surface runner gate-generic and, under `union`, run the `ci` union when the staged diff is fully matched and every hot non-catch-all surface declares a `ci` override, writing the `ci` marker with scope `a+b`. Otherwise run the global `ci` alone. Verify with tests: under `union` two overrides both run and the first non-zero exit wins; identical commands run once; a precondition failure runs nothing; a hot surface without an override runs the global alone; an unmatched path runs the global and names it; the union marker allows a commit but fails `gate-marker check ci --require-scope full`, `_ready_gates` and vouching; key absent or `single` keeps the global run; and an unknown value fails validation [oracle: unit]
- [ ] 5.2 Replace SETUP.md's "A multi-surface `ci` still runs the global `ci`" paragraph with the `loop.ci-scope` behaviour and its default, and update `docs/gate-economics.md` §2 to name `loop.ci-at: ready` and `loop.ci-scope: union` as the two declared splits, keeping §4. Verify `scripts/release docs` reports no gap [oracle: none]

## 6. The prompts (D5, D7, D10)

- [ ] 6.1 Make `skills/tdd-apply/SKILL.md` (5e, 5f, 5h, 4b's authoring commit, the sync route, the budget paragraph, 7.5 and the guardrail list) and `agents/tdd-implementer.md` (§2, §4 and §5) say: the per-task gate is the one `gates task start` names (`gates run ci`, or under `loop.ci-at: ready` `gates run unit` on the staged tree, with the review); under `ready`, run `gates run ci` with nothing staged before `gates ledger record-ready`, which refuses otherwise; and a red READY `ci` gets at most 2 focused fixes, then HALT `stalled`. Verify that the convention review of the `prompts` surface reports no `stack-agnostic-prompts` finding [oracle: none]

## 7. Adoption (D9)

- [ ] 7.1 Make the `surface-key` predicate read a dotted key as a path into each surface mapping, flat keys unchanged. Add the `ci-at` and `ci-scope` items (`since: 0.12.0`) to `adoption/catalog.json`, shaped as in D9. Verify with adoption tests through `gates adoption status`: each item listed on 0.12.0 while its key is absent, not listed on 0.11.1 or once declared, `ci-scope` listed only when a surface declares `gates.ci`, each answer recordable, and a flat `live-check` predicate behaving as before [oracle: unit]
- [ ] 7.2 Name both keys in README.md (where it describes the loop's knobs and gate cost) and in SETUP.md's upgrading section. Verify `scripts/release docs` reports no gap [oracle: none]

## 8. Integration

- [ ] 8.1 On a fixture change in a real repository with `loop.ci-at: ready` and the git-layer hook installed, run two tasks through placement, red, a green `unit` on the staged tree and commit through both layers, a `Stop`-hook audit between them, `record-ready` refused, then an unscoped `ci`, `record-ready` allowed, and `gates merge` step 1's head proof. Verify every step exits as specified and the ledger holds no taint row. Then run `./bin/gates run ci` on the finished branch and verify it exits 0 [oracle: unit characterization]

## Workflow follow-up

- Open the implementation PR with "Refs #162". The 0.12.0 release notes describe both keys as opt-in, say that nothing changes without them, and tell `ready` adopters to refresh the git-layer hook copy.
