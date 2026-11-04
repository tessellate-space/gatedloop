# Tasks

## 1. The clause and its validation (D1)

- [x] 1.1 Parse a trailing `rewrites: <path>[, <path>]...` clause in the oracle tag into a `rewrites` tuple (empty when absent). Refuse the clause on `none` as malformed, and append it to `_oracle_label` only when non-empty, so the approval digest and the drift check cover it. Verify with tests for one path, several paths, stray whitespace, the clause after `characterization`, an empty clause and `none rewrites:` (both malformed), a tag without the clause hashing to the same approval sha as before, a clause added on the target voiding `check-implement`, and a clause added on the change branch refused at handoff and under `--ref` [oracle: unit]
- [x] 1.2 Make `gates validate` fail, naming the change, the task and the path, on an absolute path, a `..` segment, a path under the state directory and a duplicate path. Make it warn on a path absent from the working tree or not matching `_is_test_path`. Verify with a test per failure, one per warning, and a valid plan that passes [oracle: unit]

## 2. The author's sight and the handoff (D2, D3)

- [x] 2.1 Add a `## Declared rewrites` section to `gates tests brief`: under each declaring task, each path with its full content at `HEAD`, fenced, or `absent at HEAD`. Verify with tests on a real repository that the brief prints the declared file's `HEAD` content even when the working tree differs, says `absent at HEAD` for a missing path, and still prints only paths for the undeclared tests in "Where tests live" [oracle: unit]
- [x] 2.2 Refuse in `gates tests handoff` a declared path absent at `HEAD` and a declared path with no `<N.M>/<path>.authored`, naming the task and the path, for the whole set and under `--task`. Print one advisory line for each existing path a task overwrites with no declaration, unless an earlier task declared it, with the exit status unchanged. Verify with tests on real repositories for each refusal (nothing recorded), the advisory line (handoff recorded, base as before), and a later task carrying an earlier task's declared path (no advisory) [oracle: unit]

## 3. The lock and review (D4, D5)

- [ ] 3.1 Add to `gates tests show` each task's `rewrites` (base blob, lines added and removed against base) in text and JSON, and a `--diff` flag that prints each rewrite's unified diff against its base. Run `python3 tests/test_contract.py --write` for the new flag. Verify with tests for the counts, the diff text and the JSON shape. Pin D4 with tests on a real repository and a worktree, for a declared rewrite that is handed off, placed over the existing file, and run red on `unit` (commit allowed); the same with no red run (refused); an edited placed rewrite (refused); a `characterization` rewrite green first (allowed); and a defect requiring the base content back [oracle: unit]

## 4. Prompts, adoption and docs (D6, D7)

- [ ] 4.1 Make `agents/test-author.md` §1, §2, §4 and §7 state the one exception (read a declared rewrite from the brief only, carry forward every case the task does not change, and send an undeclared existing test to §6 naming the path, unless the approved design gives its complete post-task text, which the author hands off verbatim at that path; design D2), and the two handoff refusals. Make `skills/tdd-apply/SKILL.md` 5c and `agents/tdd-implementer.md` say that a placed rewrite is an authored test, never edited. Make `agents/convention-review.md`'s authored-set mode read `gates tests show --diff` and judge removed cases. Verify that the convention review of the `prompts` surface reports no `stack-agnostic-prompts` finding [oracle: none]
- [ ] 4.2 Add the `test-rewrites` adoption item (`since: 0.12.0`, `decision-only`, applying when `loop.task-oracle` is declared) that prints the amended `rules.tasks` line. Amend the same line in `templates/rules-doc.template.md` and in this repo's `docs/conventions.md` `### task-oracle-tags`, then run `gates conventions sync`. Document the clause, the validate warnings, the handoff refusals and the advisory line, and `--diff` in SETUP.md; update README.md's test-author row, AUTOMATION.md (a rewrite is locked like any authored test) and `docs/stability.md`'s tag syntax. Add two entries to `docs/candidates.md`: an opt-in refusal of undeclared overwrites, and a `removes:` clause. Verify with an adoption test for the item's detector, `applies_when` and answers, `gates validate` passing with the synced block, and `scripts/release docs` reporting no gap [oracle: unit]

## 5. Integration

- [ ] 5.1 Run, on a fixture change in a real repository whose tasks are a red-first rewrite of an existing test, a `characterization` rewrite and an untagged task that overwrites an existing path without declaring it: the brief, the handoff, placement, each red or green step, the commits and a `gates merge` step-1 head proof. Then run `./bin/gates run ci` on the finished branch, and verify that both exit 0 [oracle: unit characterization]

## Workflow follow-up

- Open the implementation PR with "Refs #157". The 0.12.0 release notes describe the clause and tell existing adopters with `loop.task-oracle` to add the amended `rules.tasks` line (the `test-rewrites` item asks them).
