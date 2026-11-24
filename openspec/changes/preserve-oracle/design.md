# Design

## Context

See proposal.md, Why. Five facts in the shim at the base shape the approach:

- **The tag parser accepts one or two words.** `_oracle_body_parse` reads `<gate>`, `<gate> characterization` or `none`, then an optional trailing `rewrites:` clause. `_oracle_label` renders the parsed oracle. That label feeds the approval digest (`_oracle_tag_pairs`) and is how `_oracle_drift_problems` names tags. The drift check compares the parsed dicts.
- **A NO-TESTS task already places nothing.** `_tests_place` records an empty placement for a task in `state["no_behaviour"]` and says no red run is required. Condition 3 of `_lock_problems` skips a placement with no paths, and the in-flight check accepts a task that has a `NO-TESTS` reason.
- **The lock pins only this change's handed-off paths.** Condition 1 of `_lock_problems` reads the paths in `tests-placed` rows. A pre-existing test that no task handed off is not pinned, which is issue #217.
- **Each task records its starting tree.** `gates task start <N.M>` appends a `task-start` row whose `tree` is `git write-tree` of the index at that moment. `_latest_task_start` returns the latest one for a task, and `_current_task_after_handoff` names the task in flight from it. Every `gates run` row records `tree` the same way, after the run. `_normalize_tree` strips `.gatedloop/runs/` so that a ledger row never changes the tree a marker compares.
- **"Is this a test path?" already has an answer.** `_is_test_path(rel)` is true when a directory is one of `test`, `tests`, `spec`, `specs` or `__tests__`, or when the file's stem has a `test`, `tests`, `spec` or `specs` token bounded by `.`, `_`, `-` or an end. The brief's "Where tests live" and `gates validate`'s `rewrites:` warning both use it. The manifest has no test-path key. The only path glob it has that names tests is `acceptance.match`.

## Goals / Non-Goals

**Goals:** a refactor task can declare in the plan that it preserves behaviour. The lock then makes that claim checkable at the commit, at the merge head and at the forge. It needs no configuration beyond the tag.

**Non-Goals:**
- locking pre-existing tests for tasks that are not tagged `preserve`. That would change the meaning of every existing tag and is not opt-in;
- a new manifest key for test paths (D3);
- letting a preserve task add characterization tests (D2);
- judging whether the refactor really preserves behaviour beyond the declared gate. The gate is the oracle, and the per-task convention review still reads the diff.

## Decisions

### D1. `preserve` is a modifier word in the tag

Syntax: `[oracle: <gate> preserve]`. It takes the second-word slot that `characterization` uses, so the two cannot be combined. A refactor that needs green-first guards puts them in an earlier task. `preserve` cannot carry `rewrites:`. The parser reports that combination with its own reason, "a task that preserves every test rewrites none", as it does for `none rewrites:`. `none preserve` is malformed, because `none` takes no second word.

The parsed oracle gains `"preserve": True`, and only when the modifier is present, so a parsed tag without it compares equal to the same tag before this change. `_oracle_label` renders `<gate> preserve`. Because the digest is built from the label, a plan without the modifier hashes exactly as before, and a modifier added or dropped on the target voids `check-implement` until it is re-attested. The drift check compares whole oracles, so a modifier added on the change branch is refused at the handoff, at the commit and under `--ref`. `ORACLE_TAG_SYNTAX` and `NON_ORACLE_GATES` apply unchanged, so a preserve task's gate cannot be `ci`.

Alternative considered: a separate `[preserve]` span, or a `preserve:` clause naming the paths to keep. Both were rejected. The approval digest covers only the tag (task-oracle D9), and a clause of paths would ask the plan to list what the lock can already compute.

### D2. A preserve task refuses every test-path change, additions included (open question a)

The issue asks whether `preserve` may add test files. **It may not.** Every test path that differs from the task's `task-start` tree is refused, whether it was modified, deleted or added.

- **Only the author writes tests.** That is the guarantee the lock exists for: "authored before implementation, by an agent that does not implement it". A test added during a preserve task would be written by the implementer, in a task with no handoff for it, and the lock would pin nothing about it. Allowing additions would open a second, unreviewed way to add tests.
- **Characterization tests already have a home.** An earlier task tagged `[oracle: <gate> characterization]` gets authored, reviewed and placed tests that must pass green first and are then locked. Those tests are in the preserve task's `task-start` tree, so this task's lock protects them too. The issue's own fallback, a separate `[oracle: unit]` task, is this route with the right modifier.
- **One rule is simpler to check and to explain.** Allowing additions would require git rename detection to tell a new file from a moved one, since a rename is a deletion plus an addition. Without additions, "no test path differs from the start" is one comparison with no exceptions to it.
- **Rejection test.** Refusing everything makes the claim enforceable. Allowing additions enforces nothing and weakens an existing guarantee.

If adopters report a real case, such as a snapshot file regenerated by a refactor, the answer is a plan amendment that tags that task differently. Silently allowing it is not the answer.

### D3. A test path is what the shim already recognizes; no new key (open question b)

The issue asks whether test paths come from the project's test globs in `.gates.yaml` or from a new setting. `.gates.yaml` has no test globs, so the real choice is between reusing the shim's existing knowledge and adding a key. **Reuse it.** A path counts as a test path when any of these holds:

1. `_is_test_path(path)` is true;
2. the change's ledger names it, as a `base` key of any handoff row or a path in any `tests-placed` row;
3. it matches the manifest's `acceptance.match`, through the same `_matches` the surfaces use.

A path under `.gatedloop/` (`STATE_PREFIXES`) or `openspec/` never counts. The glob comes from the manifest the command already loaded, the working tree's `.gates.yaml`, in staged mode and under `--ref` alike, as every other manifest read of the lock does. A manifest with no `acceptance` block adds no paths. An unreadable manifest fails before the lock runs, as it does today. The plan's artifacts are not tests. Running `_is_test_path` over `openspec/specs/**` would class every spec as one, and those files are hook-denied during implementation anyway.

The predicate is `_counts_as_test_path(path, ledger_paths, acceptance_glob)`, next to `_is_test_path`. `_is_test_path` itself is unchanged, so the brief and the `rewrites:` warning behave as before.

Why not a key:
- **The tag is already the opt-in.** A preserve task should work in a project that only adds the tag. A required key would make the first use fail, and a key with a default is just the heuristic under another name.
- **The failure modes are unequal, and the heuristic errs the safe way.** A false positive (a source file named `spec_parser.py`) is refused loudly at the commit, and the remedy is clear: tag that task differently. The `gates validate` warning (D6) catches the common case at plan time, when the task's text names the file. A false negative (a CamelCase `FooTest.java` outside any `test` directory) is a silent gap. Two sources close the gap without configuration: Java and Kotlin keep tests under `src/test/`, and the change's own handed-off paths count whatever their names.
- **Rejection test.** A test glob is a binding of the adopter's layout. It is legitimate, but only worth adding when a real miss shows the heuristic is not enough. It goes in `docs/candidates.md` as `tests.match`, with the reason it waits: no reported miss yet.

### D4. The lock gains two in-flight conditions for a preserve task

In `_lock_problems`, staged mode (no `at`): when the task in flight (`only`, or `_current_task_after_handoff`) is tagged preserve in the evaluated tree, and something other than state is staged:

- **4a, no test path changed.** Read the task's latest `task-start` tree with `_tree_blobs` (`git ls-tree -r` accepts a tree id). Compare it with the staged map over the union of both key sets. For each path that counts as a test path (D3) and whose blob differs, or that exists on one side only, add one problem. It names the path, the task, the kind (`modified`, `deleted` or `added`) and the route: restore it, or, if the refactor cannot keep the test, HALT `weak-spec`, because the plan's claim that the task preserves behaviour is wrong. An added path's message also says that characterization tests belong in an earlier `characterization` task. If git cannot list the tree, the lock refuses, as `_staged_blobs` does.
- **4b, a green run on the task's tree.** The lock looks for a row after the task's latest `task-start` row for which `_gate_verdict_row(r, task, gate)` holds, `exit == 0`, and `_normalize_tree(row["tree"])` equals `_normalize_tree` of the staged tree (`_write_tree`). Without one, it names `gates run <gate> --task <N.M>`, run with the task's changes and its tick staged. No red run is required, as for `none`.

A preserve task with no `task-start` row cannot be in flight: `_current_task_after_handoff` derives the task in flight from that row. Under `--task <N.M>` with no such row, 4a and 4b report that `gates task start <N.M>` was never recorded.

Existing conditions are unchanged. A preserve task's placement is empty, so conditions 1 to 3 have nothing of its own to check. Condition 1 still pins every path an earlier task placed.

### D5. `--ref` checks each preserve task at the commit that ticks it

**Open question Q1 (raised by plan review, `gatedloop.implementability #1`).** The trees that `task-start` and `gates run` rows record are raw `git write-tree` objects of the index. They are never a commit's tree, so a fresh clone at the forge cannot read them. The `--ref` form below needs an answer on where its trees come from. The options are in the plan PR. The text below and task 2.2 still assume those trees can be read, and will be amended to the maintainer's answer.

`_task_completion` already walks the branch's first-parent commits and records `tick_at[task]`, a walk index. `_Completion` gains `commits`, the walked shas, so a reader can turn the index into a commit. `_lock_completion` walks whenever the evaluated `tasks.md` has a preserve task (today it walks only when a halt or defect row exists).

With `at`, for each preserve task checked at the ref and ticked by a walked commit C:

- the task's latest `task-start` row among the ledger rows C carries gives the start tree;
- 4a compares C's tree (`_tree_blobs(C)`) with the start tree;
- 4b looks for the green row among the rows C carries, against `_normalize_tree` of C's tree.

The tick commit carries the green row, because tdd-apply stages only the ledger row after the commit gate, and the normalized trees agree. A task ticked at the walk's seed (index 0, before the branch) is not checked, as D2 of `unblock-authored-lock` already treats it. Problems name the commit's short sha, as the other `--ref` conditions do.

Alternative considered: compare the ref's whole tree with the start tree. Rejected, because a later task with authored tests legitimately changes test paths after the preserve task is done.

### D6. The brief, the handoff, placement and validate learn the tag

- `_oracle_brief_line`: "preserve on `<gate>` — no tests: write the task's NO-TESTS reason and nothing else; the implementer must keep every test path unchanged and `<gate>` green".
- `_oracle_handoff_problems`: a preserve task is handled like `none`. Tests or `CHARACTERIZATION` are refused, naming the task, the tag and "the plan says it places no tests". `NO-TESTS` is accepted, and the gate-tagged "requires tests" refusal does not apply to it.
- `_tests_place`: for a NO-TESTS task whose tag is preserve, the message after "nothing to place" says that no test path may change from the task's start and that `gates run <gate> --task <N.M>` must pass with the task's changes staged.
- `_task_oracle_problems`: for a preserve tag, it warns about each path in the task's text that `_PATH_SPAN_RE` captures (backticked) and that `_is_test_path` classes as a test. This is the plan-time sight of D3's false positives. It uses only the heuristic, because at plan time the ledger is empty and the manifest's glob could be read but adds little.

### D7. The prompts, the rule and the adoption item

- `agents/test-author.md` §1 and §4: a `preserve` task gets a `NO-TESTS` reason only, and the handoff refuses anything else. A guard the refactor needs is a question for §6, not a test in that task.
- `skills/tdd-apply/SKILL.md` 5c, 5e and 5f, and `agents/tdd-implementer.md`'s per-task bullet: for a preserve task, place nothing, never touch a test path, stage the task's changes and its tick, then run `gates run <gate> --task <N.M>` green before the commit gate. 5e gains one sentence: for a preserve task, the green run counts only on the staged tree, so stage the task's changes and its tick before it, as under `loop.ci-at: ready`. If an existing test must change, the task does not preserve behaviour: discard and HALT `weak-spec` with detail `preserve <N.M>: <path> — <why>`. Add that row to the halt table.
- `rules/plan-lenses.md` `gatedloop.zero-decision` #3: a task tagged `preserve` that changes behaviour, or a refactor task with no `preserve` whose plan states it changes no behaviour. `gatedloop.implementability`: a preserve task whose own work edits, adds or deletes a test path.
- The `### task-oracle-tags` rule and `templates/rules-doc.template.md` gain the clause: "`[oracle: <gate> preserve]` (a refactor: no tests, every existing test unchanged, green on that gate)". `gates conventions sync` regenerates `openspec/config.yaml`.
- `adoption/catalog.json` gets an item `preserve-oracle` (`since: 0.14.0`, `decision-only`, applying when `loop.task-oracle` is declared) that prints the amended line, as `test-rewrites` did.

## Risks / Trade-offs

- [The heuristic misses a test path] → a silent gap for that path only. The change's own handed-off paths and `acceptance.match` count regardless of names. `docs/candidates.md` records `tests.match` for the first reported miss.
- [The heuristic flags a source file] → a loud refusal at the commit. The `gates validate` warning shows it at plan time, and the remedy is a retag through the plan.
- [A 4b run on a stale tree] → refused, by design. The implementer re-runs the gate after its last staged edit, which tdd-apply's "stage first" order already makes the normal path.
- [Older shims read `preserve` as malformed] → `gates validate` fails there. This is the same upgrade note `rewrites:` carried, and the docs say so.
- [The completion walk now runs for plans with preserve tasks] → two blob reads per branch commit, only for those plans.

## Migration Plan

Additive. A plan without `preserve` hashes, hands off and locks exactly as before. Rollback is a revert. A plan already using the tag then fails `gates validate` loudly rather than losing its check.
