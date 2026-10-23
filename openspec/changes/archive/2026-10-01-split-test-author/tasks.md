## 1. Manifest and rules target

- [x] 1.1 `schema/gates.schema.json` and `gates validate` accept an optional `loop.test-author` enum (`separate` | `inline`, default `separate`) and reject any other value naming the key and the allowed values; tests with PyYAML and with the built-in parser
- [x] 1.2 Accept `Applies to: tests` as a review-only target: `gates conventions sync` never emits it, `gates validate` accepts it, `gates rules` always includes `tests`-tagged ids; tests cover all three

## 2. Ledger and the authoring commands

- [x] 2.1 Extend the ledger row shape with optional `tests`, `base` and `no_behaviour` fields, backward-compatibly (older rows read `null`)
- [x] 2.2 `gates tests handoff <change> [--task N.M] [--inline]` per design D4, reading the D3 holding area; refusals for an empty area and a task with both tests and `NO-TESTS`; `--task` supersedes one task
- [x] 2.3 `gates tests place <N.M>`: moves the task's holding files onto their real paths, refuses when a real path matches neither its `base` nor an earlier task's placed blob, does nothing (and says so) for a behaviour-free task, records `tests-placed`
- [x] 2.4 `gates tests check [--task N.M]`: the three design D4 conditions (placed paths staged with recorded blobs; unplaced holding files match the handoff; a failing non-75 `unit` run after `tests-placed` for a task with tests); passes off a change branch or with no handoff
- [x] 2.5 `gates tests defect <N.M> --detail "…"` (required detail; refuses a third defect naming the `oracle-conflict` halt) and `gates tests show [<change>]`
- [x] 2.6 Tests in a temporary git repo covering: handoff/place/check across two tasks sharing one test file; place refusing after an out-of-band edit; check failing on an edited placed test, an edited holding file, a missing red run, and a red run with exit 75; a behaviour-free task needing no red run; the third-defect refusal

## 3. Commit hooks

- [x] 3.1 `hooks/gate-commit.sh` and `templates/git-hooks/pre-commit` run `gates tests check` after their `ci` marker check and deny on non-zero with its message; tests drive both with an edited placed test (denied), the authoring commit (allowed), and a clean task commit (allowed)

## 4. The brief and onboarding

- [x] 4.1 `gates tests brief <change>` prints the design D9 sections (artifact paths and task lines; `tests` rules; per-task surface rules; built-in rules with path; the `unit` gate's bound command, printed not run; up to five sibling test paths per task, paths only; shared fixture and helper files; explicit "none" lines, the no-rules one naming the capture step); tests cover every section and each "none"
- [x] 4.2 `commands/gates-init.md` step 6 gains the test-conventions pass (design D9); `templates/rules-doc.template.md` gains one example `tests` section

## 5. The test-author agent

- [x] 5.1 Add `agents/test-author.md` with `model: sonnet`, the design D2 tools, and the eight-part body (brief first; no function bodies and no existing test contents; RED questions and project-rule precedence; holding area only; task order and interfaces; all blocking questions returned together; the per-task report; defect re-dispatch), with a tool budget; no project-specific tool names

## 6. The loop's prompts

- [x] 6.1 `skills/tdd-apply/SKILL.md`: the design D1 authoring phase (dispatch the author, authored-set review per D7, the authoring commit) before the first task, and the per-task sequence (`gates tests place`, the enforced red run, implement, `gates tests check` in the 5f gate)
- [x] 6.2 `skills/tdd-apply/SKILL.md`: defects per design D5 (never edit a test; record the defect; re-dispatch the author at the top level; two-defect `oracle-conflict` halt; placed tests that pass before implementation are a defect) and the `missing-oracle` halt when `separate` and no handoff exists (D6)
- [x] 6.3 `skills/tdd-apply/SKILL.md`: the inline path (D6) and the regression-first route (D10)
- [x] 6.4 `agents/tdd-implementer.md`: requires a handoff under `separate` (halts `missing-oracle` otherwise); runs the inline authoring phase under `inline`; place → red → green per task; defect halts as `oracle-conflict` with `test-defect N.M:` detail for its dispatcher; halt-cause table rows; its description says the author is dispatched first
- [x] 6.5 `agents/convention-review.md`: the authored-set review mode (scope: `specloop.test-quality` + `tests` rules, over the holding area, recorded with `--scope authored`) and, at the task gate, reading `gates tests show` to flag tests added outside the handoff and to judge `NO-TESTS` claims
- [x] 6.6 `gates review record` accepts `--scope authored`; test it
- [x] 6.7 `hooks/_session_brief.py`: the approved-and-ready line offers "dispatch test-author, then the implementer" when `separate` and no handoff exists, and the implementer alone otherwise; tests cover both

## 7. Outcomes

- [x] 7.1 `gates stats --outcomes` derives `authorship` and `test_defects` per change (design D11), in JSON and as two table columns; tests cover separate, inline, mixed and none

## 8. Docs

- [x] 8.1 SETUP.md: `loop.test-author`, the authoring phase and holding area, the cost (one author dispatch and one review per change, one dispatch per defect), and in "Running headless" who dispatches the author; AUTOMATION.md records the lock and the enforced red run as enforcement; README's component table lists `test-author`

## 9. Close

- [x] 9.1 `gates run ci` green on the final tree; `openspec validate split-test-author --strict` passes
