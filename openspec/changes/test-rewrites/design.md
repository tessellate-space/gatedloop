# Design

## Context

See proposal.md, Why. Three facts in the shim today shape the approach:

- **The lock judges only this change's tests.** `gates tests check` (both commit hooks) and `--ref` evaluate `_lock_problems`, whose conditions cover the paths in this change's handoff and placement rows. A pre-existing test that was never handed off is not locked by the shim. Only the per-task convention review flags a test the diff changes outside the handoff (`gatedloop.test-quality #13`).
- **The shim can already carry a full rewrite.** `_tests_handoff` records each handed-off path's pre-change blob as `base[path] = _file_blob(root, path)`. `_tests_place` overwrites an existing file when its current blob is in `{base, handed-off blob} ∪ placed before ∪ merge-base blob`. A defect that voids the placement sends the path back to its base, as condition 1 of the lock requires. None of this needs to change.
- **The author is blind to existing tests by prompt, not by shim.** `agents/test-author.md` §2 forbids reading an existing test's contents and sends "an existing test file that must be extended" to §6 as a blocking question. The brief's "Where tests live" section prints paths only.

So what is missing is a declaration in the plan, the author's sight of the declared files, a handoff that holds the plan to it, and a review that sees what a rewrite dropped.

## How it connects end to end

```
planner (/opsx:propose, steered by the adopter's rules.tasks line)
  └─ tasks.md: "- [ ] 2.1 … [oracle: unit rewrites: tests/toolbar.test.ts]"   ← approved with the plan
gates validate ─ the clause is well formed; warns on a path absent from the tree
gates tests brief ─ prints tests/toolbar.test.ts as it is at HEAD, under 2.1
test author ─ reads that copy (and no other existing test), writes
             .gatedloop/authored/<change>/2.1/tests/toolbar.test.ts.authored (full file)
gates tests handoff ─ refuses 2.1 without that file; records base = the HEAD content
authored-set review ─ gates tests show --diff: what the rewrite added and dropped
implementer, task 2.1
  ├─ gates tests place 2.1        ← overwrites the existing file (unchanged)
  ├─ gates run unit --task 2.1    ← red first, as for any authored test
  └─ commit ─ lock: the rewritten file is 2.1's placed test (unchanged)
```

## Goals / Non-Goals

**Goals:** a task whose job includes changing an existing test can do it inside the loop. The author sees exactly the files the approved plan names and no others, and the rewritten files are locked like any authored test.

**Non-Goals:**
- refusing an undeclared overwrite of an existing test path (D3);
- deleting a test file (D1);
- letting the implementer edit any test, rewritten or not;
- any change to the lock's evaluator.

## Decisions

### D1. The declaration is a clause of the oracle tag

Syntax: `[oracle: <gate> [characterization] rewrites: <path>[, <path>]...]`. The clause comes last in the tag. Paths are repo-relative, written bare (no backticks), separated by a comma and optional whitespace, and contain no whitespace. `none` cannot carry the clause, because a task that rewrites a test has a test, so `[oracle: none rewrites: …]` is a malformed tag. An untagged task cannot declare a rewrite, because the declaration rides on the tag. `characterization` may carry it: a rewrite that only removes assertions (a wall-clock check, say) passes on the tree as it is, and is green first.

The parsed oracle gains `rewrites`, a tuple of paths in declared order, empty when there is no clause. `_oracle_label` appends ` rewrites: <p1>, <p2>` only when the tuple is non-empty. That one change gives three properties already built for tags:
- the approval digest (`_oracle_tag_pairs`, task-oracle D9) covers the paths, so adding, dropping or editing a rewrite on the target voids `check-implement` until re-attestation;
- a plan with no clause hashes exactly as before, so upgrading voids no approval in flight;
- the drift check (`_oracle_drift_problems`) compares whole oracles, so a clause edited on the change branch is refused at handoff, at the lock and under `--ref`, like a retag.

`gates validate` fails, naming the change, the task and the path, on: an absolute path, a `..` segment, a path under gatedloop's state directory, the same path twice in one tag, an empty clause, and the clause on a `none` tag. It **warns**, and does not fail, when a declared path is absent from the working tree, or does not look like a test path to the brief's heuristic (`_is_test_path`). Whether the path exists is checked as a refusal at handoff (D3), against `HEAD`, because that is when it matters. `validate` runs in `ci` on the target. A refusal there would let an unrelated change that renames a test break every other commit's `ci` while this plan is active.

Alternative considered: a `rewrites:` list under the task, or a section of `tasks.md`. Rejected. The approval digest covers only tags (D9 of task-oracle), so a separate list would need its own digest and its own drift check, and the parser would have a second grammar.

**No `removes:` clause.** Deleting a test whose subject is gone is not blocked today. The shim locks no pre-existing, unhanded-off file, so a deletion reaches the per-task review, where it is judged against the task. The declaration this change adds answers a different problem: authoring content the author cannot see. A deletion has no content to author. A rewrite to a smaller file covers dropping some cases. Dropping all of them is a deletion, and an empty test file fails some runners. If adopters report that the review alone is not enough for deletions, the clause can be added later without changing this grammar. It is recorded in `docs/candidates.md`.

### D2. The author sees the brief's copy of a declared file, and nothing else

`gates tests brief` gains a `## Declared rewrites` section after `## Declared oracles`. For each task with a clause, it prints each path followed by its full content at `HEAD`, fenced. A path absent at `HEAD` is printed as `absent at HEAD` and no content, so the handoff refusal comes as no surprise. The brief has no size cap. The plan named the files, and a human approved the list.

`agents/test-author.md` §2 changes in one place. The author may read a declared file's content, **from the brief only**: it never opens the path, and it never reads any other existing test. An existing test that must change but is not declared stays a §6 question, now with a stated answer: the plan declares it as `rewrites:` on the task. The author copies forward every case the task does not change, because the handed-off file is the full content after the task (§4, unchanged). Cases it removes are the ones the task's specs and design say are gone.

Alternative considered: let the author open the declared paths directly. Rejected. The rule then needs the author to check each read against a list, where "read the brief" is one rule the author already follows. Content read from `HEAD` also matches the base the handoff records for a clean tree.

### D3. A declared rewrite must be handed off; an undeclared overwrite is unchanged

`_oracle_handoff_problems` gains two contradictions for each task in scope, beside the four task-oracle added:
- a declared path that does not exist at `HEAD` (`git cat-file -e HEAD:<path>`): "task 2.1 declares rewrites: <path>, which does not exist at HEAD — amend the plan";
- a declared path with no `<N.M>/<path>.authored` in the holding area: "task 2.1 declares rewrites: <path>, but the handoff holds no full file for it".

Under `--task N.M`, only that task's declarations are checked, as for the other contradictions. The base is recorded exactly as today. No new field is written to the handoff row: a rewrite is identified by reading the tag, and its base is already in `base[path]`.

A handoff that writes an existing path that no task declares is handed off as today, with no refusal. Refusing it would be a new adopter-facing refusal, and those are opt-in by the maintainer's rule. The handoff prints one advisory line per such path ("task 3.1 overwrites existing tests/x.test.ts without declaring it; its author could not see that file"). Its exit status is unchanged. A later task that carries a path an earlier task declared (two tasks sharing one file, §5 of the author prompt) is not undeclared: its author saw the content through the earlier declaration. An opt-in `loop.test-rewrites: required`, which would turn the advisory into a refusal, is recorded in `docs/candidates.md`.

### D4. A placed rewrite is the task's authored test

There is no change to placement, the lock, the attempt budget or defects, and this is deliberate. A rewritten file is a handed-off path with a non-null base, which the lock has handled since `split-test-author`. It runs red first on the task's oracle gate, or green first under `characterization`. The implementer never edits it. A `setup` or `assertion` defect voids the placement and returns the path to its base. A `green` defect means what it means for any test. The tests for this change pin these behaviours on a real repository, so a later edit to the lock cannot treat a rewrite differently without a red test.

### D5. Review sees the diff against base

`gates tests show` gains, per task, `rewrites` beside `tests`: each declared path with its base blob and a `+added -removed` line count against the handed-off blob, computed with `git diff --numstat <base> <blob>` on the two blob ids. The text output prints `rewrites <path> (+a -r vs base)`, and the JSON carries `{"rewrites": {path: {"base": blob, "added": a, "removed": r}}}`. `gates tests show <change> --diff` prints each rewrite's unified diff against its base, so a reviewer reads exactly what changed in an existing test.

`agents/convention-review.md`'s authored-set mode reads `--diff` for every rewrite. It judges dropped cases against the task's specs and design: a case removed with no scenario or design reason to remove it is a `gatedloop.test-quality` finding. The reviewer is not the author, so the boundary in D2 does not bind it.

### D6. Prompts state the rule where the rule lives, with no tool names

- `agents/test-author.md`: §1 names the brief's `Declared rewrites` section. §2 carries the one exception (D2). §4 says a declared rewrite's handed-off file is the full post-task content, carrying forward every case the task does not change. §7 lists the two new handoff refusals.
- `skills/tdd-apply/SKILL.md` 5c and `agents/tdd-implementer.md`'s "Authored tests" section each gain one sentence: a placed rewrite of an existing test is an authored test like any other, so never edit it, and a defect against it returns the file to its content before the change.
- `agents/convention-review.md`: the authored-set step in D5.
- Planner guidance lives where `rules.tasks` lines already live, because `/opsx:propose` writes `tasks.md` (`no-forked-upstream-assets`): the `### task-oracle-tags` line in `templates/rules-doc.template.md`, this repo's `docs/conventions.md`, and the `test-rewrites` adoption item (D7). The line gains: "When a task changes behaviour an existing test pins, add `rewrites: <path>` for each such test file." `commands/propose.md` and `commands/planner.md` are unchanged, because they delegate authoring.

Every addition names gates and paths only, never a runner.

### D7. Adoption offers the amended line to projects that tag

A `test-rewrites` catalog item (`since: 0.12.0`) applies when `loop.task-oracle` is declared, with the `decision-only` detector. "Yes" prints the amended `rules.tasks` line, or the rules-doc rule where `gates conventions sync` generates the block. "Not yet" is an answer. The shim edits no adopter file (task-oracle D7). A project that never tags is not asked, because without a tag there is no clause.

## Risks / Trade-offs

- [A plan names a non-test file under `rewrites:`, and the author sees implementation through it] → `gates validate` warns when a declared path does not match the brief's test-path heuristic (`_is_test_path`). The approving human sees the path in the tag, and the digest pins it. It is a warning, because adopters' test layouts (a Storybook config test, a shell test under `infra/`) do not always match the heuristic.
- [The author drops a case it should have carried forward] → `gates tests show --diff` puts every removed line in front of the authored-set review (D5), which judges each removal against the specs.
- [A large declared file makes the brief long] → the plan chose it, and a human approved it. The brief prints only declared files, so its size grows with the plan, not the repository.
- [Undeclared overwrites stay blind] → they behave as today. The advisory line makes each one visible, and the opt-in refusal is a candidate (D3).
- [A rename of a declared test on the target after approval] → `validate` warns on the target, and the handoff refuses against `HEAD`. The route is a plan amendment, which re-attests through the digest.

## Migration Plan

This ships in 0.12.0 (minor). Plans without the clause are unaffected and hash as before. A plan that uses the clause needs 0.12.0 or later. An older shim reads the tag as malformed and fails `gates validate` loudly. Rollback: revert the change, then drop the clause from any in-flight plan and re-attest.
