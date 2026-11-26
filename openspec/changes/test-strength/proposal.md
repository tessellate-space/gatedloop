# Proposal

## Why

gatedloop guarantees that each task's tests **fail before the feature and pass after it**: an agent that does not implement writes them, they are locked, and a red run is enforced after placement (`test-discipline`). It does not guarantee that those tests **constrain the feature**. A test that only checks "no error was raised", or checks one example where the behaviour spans a range, goes red, goes green, passes review and merges. Convention review judges rules, not test strength, and `verify` checks that every spec scenario has a test, not that the test would catch a wrong implementation.

So the chain from spec to code has two links and gatedloop checks one:

| Link | Question | Checked today by |
|---|---|---|
| Spec → tests | Does every scenario have a test? | `verify` (scenario → acceptance coverage) |
| Tests → code | Would those tests catch wrong code? | nobody; it is assumed |

Mutation testing is the established oracle for the second link: it injects small, standard faults into the code (a flipped comparison, a negated condition, a deleted statement) and checks that the tests fail. A fault the tests do not notice (a *surviving mutant*) is concrete evidence of a weak test.

An adopter can already run a mutation tool as a gate. What is missing is the loop's reaction. A failed mutation check means the **tests** are weak, but the tests are locked, the implementer cannot edit them, and the autonomous implementer halts rather than guess. Dropped into `verify` as a blocking gate, it would stall the change: something failed, and the one party allowed to act on it, the test author, never hears about it.

This passes the rejection test as "makes a stated guarantee enforceable". The guarantee is the existing one that a wrong test goes back to its author (`test-discipline`). It names no stack command: the tool is the adopter's, behind a gate. It authors no artifact.

## What Changes

- **A new optional gate, `mutation`.** The adopter binds it to their stack's mutation tool in `.gates.yaml`. Like every gate, its verdict is its exit code, and undeclared means skipped. It is called with `-- <paths>` scoping, as `unit` is.
- **It runs once per change, at completion, on the change's own code only.** It does not run in the per-commit loop, on other branches, or on code the change did not touch. Where mutants are placed is decided by the tool's standard catalog applied to the change's diff, so no agent chooses where to look, matching how `bin/gates` already selects surfaces deterministically.
- **It is judged per task, so the exit code stays the whole contract.** For each completed task that has tests, the shim runs `gates run mutation -- <that task's changed code paths> <that task's placed test paths>`. A non-zero exit belongs to that task, and no tool output has to be parsed to know which one.
- **A survivor goes back to the test author, not the implementer.** A failed run records a new defect kind, `gates tests defect <task> --kind strength`, carrying the gate's output as its detail. That reopens the task through the existing "a test defect at a completed task reopens it" path. The author revises the task's tests (the strengthened tests are placed and locked as usual) or defends them, for example by arguing that the surviving mutant does not change behaviour. A task takes at most one `strength` defect; if its re-run still fails, the result is reported, not halted on.
- **Advisory by default, blocking only by team choice.** Out of the box a failure is reported at merge and never blocks, like `eval`. A team can opt in to blocking with a manifest setting. Unless they do, the change merges with its surviving mutants listed in the record.

## Non-goals

- **Shipping or naming a mutation tool.** The tool, its catalog of mutation types and its score threshold are the adopter's, in `.gates.yaml`.
- **Mutating the whole codebase.** A periodic full run on `main` is a health report for a team lead, not a loop step, and is out of scope here.
- **LLM-proposed "semantic" mutants** (realistic wrong implementations read from a spec scenario). Recorded as a follow-up candidate: useful evidence, but a judgement, so it could only ever be advisory, and its author would have to be neither the test author nor the implementer.
- **Catching a change that weakens an existing test elsewhere.** Scoping to the diff cannot see that; the lock and review remain the defence.

## Success measures

- **Adoption:** share of projects with `.gates.yaml` that declare `mutation` within two releases.
- **Signal:** per change, the share of tasks whose first `mutation` run fails. A meaningful, non-zero rate is the evidence that the second link was weak.
- **Recovery:** the share of `strength` defects resolved by revised tests rather than defended. A high defend rate means the adopter's catalog is noisy (equivalent mutants) and blocking should stay off.
- **Cost:** median wall-clock added at completion. Target: under the change's own `verify` time on a typical change.

## Open questions

1. **The blocking setting's shape.** A `loop.mutation: advisory|blocking` key, or the existing per-gate declaration style? Decided in design.
2. **Per-task cost.** One run per task is N runs per change. Is a cap or a time budget needed, and is it the shim's or the adopter's? The adopter's tool usually has its own budget flag.
3. **Tasks with shared code.** When two tasks touch the same file, which task's tests does a mutant in that file belong to? Candidate answer: run with the union of both tasks' tests, and report against the later task.
4. **Dependency.** This builds on `checkable-disputes`: a `strength` defect and its defence should carry citations like the other kinds. Sequence this change after that one merges.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gate-binding`: adds the optional `mutation` gate, its call point (change completion, per task) and its scoping.
- `test-discipline`: adds the `strength` defect kind, its cap, and its routing to the author through the completed-task reopen path.
- `merge-step`: reports unresolved `strength` results in the merge record, and refuses only when the team opted in to blocking.

## Impact

- `bin/gates`: the `mutation` gate slot, the per-task completion run, `tests defect --kind strength`, the merge report and the opt-in refusal.
- `schema/gates.schema.json` and `templates/gates.yaml.template`: the new gate and the blocking setting.
- `skills/tdd-apply/SKILL.md`, `skills/verify/SKILL.md`, `agents/test-author.md`, `agents/tdd-implementer.md`: when the run happens, what a `strength` defect asks of the author, and when to defend versus revise.
- README.md and SETUP.md (the new gate and setting), `tests/contract.json`, tests for each check.
- Adopters: nothing changes unless they declare `mutation`.
