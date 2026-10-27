# Design

## Context

See proposal.md, Why. Today a task's kind is decided once, by the test author, from prose. It is recorded as the presence or absence of `CHARACTERIZATION` and `NO-TESTS` marker files, and the lock's red-run condition reads only `unit`. 0.8.0 added recovery for a wrong guess: the `green` defect and the reopen. This change moves the decision earlier, into the plan that a human approves, and lets the decision name the gate.

## How it connects end to end

```
planner (/opsx:propose, steered by the adopter's rules.tasks line)
  └─ tasks.md: "- [ ] 5.1 … [oracle: integration]"     ← approved with the plan
gates validate ─ tag names a declared, per-task gate
gates tests brief ─ prints each task's declared oracle → test author
test author ─ writes tests for that gate's layer / CHARACTERIZATION / NO-TESTS
gates tests handoff ─ refuses a holding area that contradicts a tag
authored-set review ─ judges the reason against the tag (not against prose)
implementer, per task
  ├─ gates tests place 5.1
  ├─ gates run integration --task 5.1   ← red step on the declared gate
  ├─ implement → green on that gate → gates run ci --task 5.1
  └─ commit ─ lock: red run on the declared gate after placement
gates merge step 1 / gatedloop/tests status ─ the same evaluator, same rule
attempt budget ─ counts from the first red run on the declared gate
```

An untagged task takes today's path at every step: the author decides, the red step is `unit`, and the lock reads `unit`.

## Goals / Non-Goals

**Goals:** a task's oracle is fixed before any test or code exists, by the artifact a human approves. Each consumer reads it from one parser.

**Non-Goals:**
- authoring `tasks.md` (OpenSpec's job);
- a fixed test-layer taxonomy;
- lettered task ids (#46);
- making tags required by default.

## Decisions

### D1. The tag is a gate name plus an optional expectation

Syntax: `[oracle: <gate>]`, `[oracle: <gate> characterization]` or `[oracle: none]`, as the last bracketed span on the task line, after optional whitespace. The parser strips it from the task text that every other consumer reads. A gate is any key under `gates:` except `ci`, `live-check`, `eval` and `confirm`, held in one constant, `NON_ORACLE_GATES`. Each of those four is excluded for its own reason:
- `ci` is green at every commit, so it says nothing about one task;
- `live-check` probes a surface, not a task;
- `eval` is an advisory score;
- `confirm` runs only on the merged tree.

Alternative considered: fixed kinds (`unit | characterization | e2e | none`). Rejected. "e2e" would have to map to one gate, which leaves adopters whose end-to-end tests run under another gate with nowhere to go. It would also bake a test-layer taxonomy into the shim, against `stack-agnostic-prompts`. `characterization` is an expectation (green first), not a layer, so it is a modifier that applies to any gate.

### D2. One parser, read from the evaluated tree

`_task_lines` returns `(id, text, oracle)`, where `oracle` is `None` or `{gate, characterization}` and `none` is `{gate: None}`. The lock and `--ref` read `tasks.md` from the tree they evaluate, the staged index or the commit. That is the same source D2 of `unblock-authored-lock` uses for task completion, so a tag edited mid-branch is judged as of each commit. The plan is approved by content sha, so a tag edit after approval already fails `check-implement` until re-attested. No new mechanism is needed to stop a tag being changed quietly.

### D3. Handoff refusals are contradictions only

The handoff checks four contradictions, listed in the spec. It does not check that the tests *exercise* the declared gate, because the shim cannot know which files a gate runs. The red run on that gate checks it instead: a test the gate never runs cannot go red under it. The lock then refuses the commit, and the implementer records a `setup` defect.

### D4. The lock and the attempt budget take the oracle gate as a parameter

`_is_red_unit_row` and `_unit_verdict_row` generalise to `_is_red_gate_row(r, task, gate)`. Condition 3 of `_lock_problems` passes the task's oracle gate, or `unit` for an untagged task. `_attempt_state` takes the same gate for its `red_seen` window, and red `ci` runs still count as attempts. `gates run <gate> --task` already records a per-task row for any gate, so the shim gains no new recording.

### D5. The implementer prompts name the gate from the brief, never a literal

`tdd-apply` and `tdd-implementer` read the oracle with `gates tests show <change>` (which gains the column) and run `gates run <that gate> --task N.M` for the red step. Prompts never name an adopter's gate. They say "the task's oracle gate (`unit` when the plan declares none)", which keeps `stack-agnostic-prompts` intact. For a `none` task the red step is skipped, and the commit names its covering test or says that no behaviour changes ("Every task names its oracle").

### D6. Disagreement goes back to the plan, not around it

If the test author holds that a tag is wrong, it stops and reports the task, the tag and why: a `weak-spec` finding for whoever dispatched it. The plan is amended and re-attested. This was chosen over an advisory mismatch with a recorded reason, because the point of the tag is that the implementer and author cannot choose their own oracle.

### D7. Adoption writes nothing into the adopter's OpenSpec config

The `task-oracle` catalog item (since 0.9.0) asks "Have the plan declare each task's oracle?". "Yes" (recommended) prints one line for the adopter to add to `openspec/config.yaml` `rules.tasks`, and offers `loop.task-oracle: required`. "Not yet" is also an answer. The shim never edits `config.yaml`. That file is the adopter's constitution, and `gates conventions sync` owns it only in projects that generate it. The detector is `loop.task-oracle` present in the manifest.

### D8. #47 is narrowed, not claimed

`convention-review`'s authored-set check is told to judge a `NO-TESTS` or `CHARACTERIZATION` reason against the task's tag when one exists. A `NO-TESTS` that matches `[oracle: none]` is no longer read as a missing oracle, which is #47's misread. Untagged tasks keep today's judgement, so #47 stays open until a project tags its plans.

## Risks / Trade-offs

- [A wrong tag blocks the author until the plan is re-approved] → this is accepted as the cost of the plan being the contract (D6). The `weak-spec` halt names the task, so the amendment is one line.
- [A gate that takes no per-task scoping runs whole for each red step] → the adopter's gate binding decides that. SETUP says that a gate used as an oracle should accept the same `-- <args>` scoping `unit` does.
- [Lettered task ids (#46) carry tags the parser never sees] → `gates validate` reports a tag on a line the task parser does not match, so the tag is not silently ignored.

## Migration Plan

This ships in 0.9.0 and is opt-in. Existing plans are untagged and unaffected. In-flight changes are not required to tag, even under `required`, if their handoff was recorded before the key was set: the check runs at handoff. Rollback: revert the change. Tags left in `tasks.md` are inert text to an older shim.
