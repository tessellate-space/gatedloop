# Tasks

## 1. The tag and its validation (D1, D2)

- [x] 1.1 Parse a trailing `[oracle: <gate>]`, `[oracle: <gate> characterization]` or `[oracle: none]` in `_task_lines`, returning it beside the id and the stripped text, with `NON_ORACLE_GATES` holding `ci`, `live-check`, `eval` and `confirm`. Verify with tests for each form, stray whitespace, a tag mid-line (not a tag), and the task text other consumers read no longer carrying the tag [oracle: unit]
- [x] 1.2 Make `gates validate` check every tag in the active changes. It fails naming the change, the task and the tag for an unknown gate, an excluded gate or a malformed tag, and reports a tag on a line the task parser does not match (#46). Document the tag syntax and the excluded gates in SETUP.md. Verify with tests for each failure and for a valid tagged plan, and confirm that `scripts/release docs` reports no gap [oracle: unit]

## 2. The brief and the handoff (D3)

- [x] 2.1 Print each task's declared oracle in `gates tests brief`, saying "the author decides" for an untagged task, and add an oracle column to `gates tests show`. Verify with tests on a plan mixing gate, characterization, none and untagged tasks [oracle: unit]
- [x] 2.2 Refuse in `gates tests handoff` each of the four contradictions in the spec, naming the task, the tag and what the plan requires. Add `loop.task-oracle` (`optional` by default, or `required`) to the schema and the shim, so that `required` refuses untagged tasks at handoff and an unknown value fails validation. Document the refusals and the key in SETUP.md. Verify with a test per refusal, a `required` test and a default test [oracle: unit]

## 3. The lock and the attempt budget (D4)

- [x] 3.1 Read the lock's red-run condition, and the characterization first-green condition, on the task's oracle gate, at the index and under `--ref`, with `unit` for untagged tasks. Update AUTOMATION.md's description of what the lock reads. Verify with tests for an `integration`-tagged task red on `integration` (holds), red only on `unit` (refused, naming the right command), a characterization task on a non-`unit` gate, and an untagged task unchanged [oracle: unit]
- [x] 3.2 Count failed attempts from the first red run on the task's oracle gate, with red `ci` runs still counting. Verify with tests for an `integration`-tagged task's window and an untagged task's unchanged window [oracle: unit]
- [ ] 3.3 Hold each tag to the approved plan (D9). When `tasks.md` carries a tag, add a digest of its `(task id, tag)` pairs to the approval sha, at the index and at a ref, leaving out checkbox state and task text. Make the handoff, the lock and `--ref` refuse a task whose tag differs from the target's `tasks.md`, naming the task, both tags and the amend-and-re-attest route. Verify with tests for an untagged plan's unchanged sha, a tick leaving the sha unchanged, a retag on the target voiding `check-implement`, a retag on the branch refused at the lock and under `--ref`, and a task absent from the target not compared [oracle: unit]

## 4. The loop prompts (D5, D6, D8)

- [x] 4.1 Make `skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md` run the red step on the task's oracle gate, as `gates tests show` reports it, skip it for a `none` task, and expect green first for `characterization`, never naming an adopter's gate. Verify that the convention review of the `prompts` surface reports no `stack-agnostic-prompts` finding [oracle: none]
- [x] 4.2 Make `agents/test-author.md` read the declared oracle from the brief, write tests for that gate's layer, and stop with a `weak-spec` report naming the task when it holds a tag is wrong. Retire the 0.8.0 interim "declare an e2e task `CHARACTERIZATION`" rule. Make `agents/convention-review.md`'s authored-set check judge a `NO-TESTS`/`CHARACTERIZATION` reason against the task's tag when one exists (#47). Verify by the same convention review [oracle: none]

## 5. Adoption and the docs that describe the loop (D7)

- [ ] 5.1 Add the `task-oracle` adoption item (`since: 0.9.0`), which prints the `rules.tasks` line and offers `loop.task-oracle: required`, with its detector. Have `commands/gates-init.md` and `templates/rules-doc.template.md` offer the same line at onboarding. Verify with an adoption test for the detector and the item's answers [oracle: unit]
- [ ] 5.2 Describe the red step as "the task's oracle gate (`unit` by default)" in README.md (the authored-test row, the `test-author` agent row and the loop diagram), `docs/topology.md` and `docs/running-at-scale.md`, and mark the `docs/status.md` sharp edge on inferred task kinds as shipped. Verify that `scripts/release docs` reports no gap and that `grep -n "gates run unit"` in those files finds only places that mean `unit` itself [oracle: none]
- [ ] 5.3 Add a `### task-oracle-tags` rule to this repo's `docs/conventions.md` (each task line ends with its oracle tag) and run `gates conventions sync`, so that `openspec/config.yaml`'s `rules.tasks` carries it. Do not set `loop.task-oracle: required` here. Verify that `gates validate` passes with the synced block [oracle: none]

## 6. Integration

- [ ] 6.1 Run, on a fixture change with an `integration`-tagged task, a `characterization` task and a `none` task, the handoff, placement, the red step on each declared gate, the commits, and a `gates merge` step-1 head proof. Then run `./bin/gates run ci` on the finished branch, and verify that both exit 0 [oracle: unit characterization]

## Workflow follow-up

- Open the implementation PR with "Refs #56" (item 4) and "Refs #47". The 0.9.0 release notes describe the opt-in.
