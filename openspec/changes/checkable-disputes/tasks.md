# Tasks

## 1. Citations

- [ ] 1.1 Add a citation resolver for `path`, `path:line`, `path:a-b` (worktree, holding area included) and `spec:<capability>#<scenario>` (change delta specs, then main specs; case-insensitive, whitespace collapsed), returning the citations that do not resolve; verify with a new `tests/test_dispute_citations.py` covering each form, an out-of-range line, a missing file, a held test path and a missing scenario [oracle: unit]
- [ ] 1.2 Stamp `"disputes": "cited"` on new handoff rows, and make `gates tests defect --kind setup|assertion` require a repeatable `--cite` when the governing handoff carries it: refuse naming each unresolved citation, store the citations on the row, and keep accepting citation-free defects for older handoffs; verify in the same module and the existing defect tests [oracle: unit]

## 2. Green evidence

- [ ] 2.1 Refuse `gates tests defect --kind green` unless a passing run of the task's oracle gate is recorded after its latest placement, reusing the after-placement lookup `gates tests check` uses; verify with a failing-only run (refused) and a passing run (recorded) [oracle: unit]

## 3. Recorded defence

- [ ] 3.1 Add `--defend <why>` and `--cite` to `gates tests handoff --task`: refuse when the task's held blobs differ from its previous handoff entry or no defect follows that handoff, otherwise write a `test-defence` row next to the handoff row; verify the three scenarios of the defence requirement [oracle: unit]
- [ ] 3.2 Show each defect's citations and its answering defence in `gates tests show` (text and `--json`), and print every defect and defence with citations in the `assertion`-cap refusal; verify with a task holding defect, defence, defect [oracle: unit]
- [ ] 3.3 Rewrite `tests/contract.json` for the new flags with `python3 tests/test_contract.py --write`, and document `--cite` and `--defend` in README.md and SETUP.md; verify `python3 scripts/release docs` reports no gap [oracle: unit]

## 4. The prompts

- [ ] 4.1 In `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md`, say each defect cites the failing assertion or fixture (`path:line`) and the spec scenario it contradicts, and that a `green` defect needs its passing run recorded first; in `agents/test-author.md`, say a defence is `gates tests handoff --task N.M --defend ... --cite ...` with the tests unchanged, and that changed tests are a revision without `--defend`; verify by re-reading against `stack-agnostic-prompts` and the convention review [oracle: none]
