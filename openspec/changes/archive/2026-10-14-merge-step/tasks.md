## 1. The `confirm` gate and the merge lock

- [x] 1.1 Add `confirm` to the gate table and `schema/gates.schema.json` as optional; `gates run confirm` behaves like any gate (precondition, ledger, output); undeclared prints the design D3 skip note; tests
- [x] 1.2 A `merge` lock via `_gate_lock`'s mechanism, always serialized and bounded by `concurrency.max-wait-seconds` (design D4); tests for contention and the busy exit

## 2. `gates merge` — steps

- [x] 2.1 Step 0 and step 1 per design D2 (lock, preconditions, HEAD recorded under `.git/specloop/merge-state`, trailing ledger rows committed on the branch at ledger grade, the merge hook's incoming-tree checks called as functions, coverage lines printed); tests cover an uncommitted live-check row, a missing marker, and a missing acceptance under a declared policy
- [x] 2.2 Step 2 (fetch, detach, squash; conflict → abort, restore, exit 2 with paths); tests with a real conflict leave target and working tree unchanged
- [x] 2.3 Step 3 (unscoped `ci` on the staged squash; red → reset, restore, exit 3; green → squash commit with the design D2 message) and step 4 (record-merge with the real sha, ledger-grade commit); tests
- [x] 2.4 Step 5 (`confirm` when declared; red or 75 → reset, restore, failure row committed on the branch, exit 5) and step 6 (archive and archive commit, one push, non-fast-forward → one retry from step 2, else exit 6; restore HEAD, fast-forwarding the local target when it was checked out); tests use a bare remote and a concurrent push to force the retry
- [x] 2.5 Crash recovery: a rerun finding a detached HEAD with this change's unpushed merge row restores the recorded HEAD first (design Risks); test

## 3. Triggers and prompts

- [x] 3.1 Add `commands/merge.md` per design D5
- [x] 3.2 Add `agents/merge-runner.md` (Sonnet; mechanical conflicts only; re-run head gates after a resolution; one retry; halt `other` otherwise), naming no stack tool
- [x] 3.3 `skills/tdd-apply/SKILL.md` 7.5 local branch becomes `gates merge <change>`; `commands/archive.md` notes step 6; `agents/tdd-implementer.md` states it never runs `gates merge`

## 4. Onboarding, adoption, docs

- [x] 4.1 `commands/gates-init.md` offers to bind `confirm` when `live-check` is bound; `adoption/catalog.json` gains `confirm-gate` (design D6) if `adoption-prompts` has landed, else note it in the final report
- [x] 4.2 SETUP.md: the merge step, exit codes by step, the `confirm` gate, and what stays the adopter's; README's component table lists `/specloop:merge` and `merge-runner`

## 5. Close

- [x] 5.1 `gates run ci` green on the final tree; `openspec validate merge-step --strict` passes
