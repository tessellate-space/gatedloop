# Spec Delta

## Purpose
The scored suite that checks the shipped agents' load-bearing behaviour from what each run leaves behind, and the rules for when it runs and what it may name.

## ADDED Requirements

### Requirement: The implementer's halt and stop behaviour has scored cases

The repository SHALL hold a `claude plugin eval` suite under `evals/`, with two `tdd-implementer` cases:

- `implementer-halts-on-weak-spec`, on an approved change whose only task contradicts its spec;
- `implementer-ready-stops-before-merge`, on an approved one-task change that is fully specified.

#### Scenario: The implementer halts instead of guessing

- **WHEN** `implementer-halts-on-weak-spec` runs
- **THEN** the change's ledger holds a `halt` row with cause `weak-spec`
- **AND** the task is not ticked, and no `gates merge` command was run

#### Scenario: The implementer finishes a task and stops before the merge

- **WHEN** `implementer-ready-stops-before-merge` runs
- **THEN** the task's `[x]` is committed, the ledger holds a `ready` row, and the final report reads `READY TO MERGE`
- **AND** no `gates merge` command was run

### Requirement: The review's rule citation has scored cases

The suite SHALL hold two `convention-review` cases:

- `review-cites-stack-agnostic-prompts`, on a diff that hard-codes a runner command in a shipped command file;
- `review-clean-diff`, on a diff that breaks no rule.

#### Scenario: The review cites the rule it applies

- **WHEN** `review-cites-stack-agnostic-prompts` runs
- **THEN** the review reports a finding that names `stack-agnostic-prompts`

#### Scenario: A clean diff draws no finding

- **WHEN** `review-clean-diff` runs
- **THEN** the review reports no finding

### Requirement: Cases are graded on outcomes

Every case SHALL be graded on what the run leaves behind: ledger rows, `tasks.md` ticks, commits, and the final report. No case SHALL be scored only on which tools were called.

A grader SHALL match no wording beyond a token the prompt defines, such as `READY TO MERGE`, a halt cause or a rule-id.

#### Scenario: A reworded prompt with the same behaviour passes

- **WHEN** a prompt's prose is rewritten and the agent still halts with cause `weak-spec`
- **THEN** `implementer-halts-on-weak-spec` still passes

### Requirement: The suite's fixtures name no stack

Each case's workspace SHALL be built by a scaffold kept in `evals/`. The fixture's `.gates.yaml` SHALL bind every gate to a POSIX `sh` script inside the fixture.

The only stack command anywhere in `evals/` SHALL be the planted violation in `review-cites-stack-agnostic-prompts`, and that case's prompt SHALL say that the violation is planted.

#### Scenario: A fixture is stack-free

- **WHEN** a case's scaffold builds its workspace
- **THEN** every gate in the fixture's `.gates.yaml` runs a script in the fixture through `sh`

#### Scenario: A missing prerequisite fails the case loudly

- **WHEN** the scaffold cannot find `openspec`, `gates` or `git` on `PATH`
- **THEN** the scaffold exits non-zero, naming the missing command, and the case scores as errored rather than as a pass

### Requirement: The suite is test data, outside the prompt rules

`evals/` SHALL be treated as test data, not as a shipped prompt. The `prompts`-surface rules, `stack-agnostic-prompts` among them, SHALL NOT apply to it, and `.gates.yaml` SHALL give it a surface of its own.

#### Scenario: The planted violation is not a finding against the repo

- **WHEN** a commit adds the review case's planted violation under `evals/`
- **THEN** the convention review of that commit does not apply `stack-agnostic-prompts` to it

### Requirement: The suite runs on demand and never in `ci`

`scripts/eval-prompts` SHALL run the suite with the scaffold enabled, no ablation arm, reports kept local, and a cost ceiling that `--max-cost-usd` overrides. It SHALL exit non-zero when any case scores below its threshold, and it SHALL print one summary line.

`ci` SHALL NOT run the suite, and this repository SHALL NOT declare the `eval` gate for it.

#### Scenario: A failing case fails the run

- **WHEN** a case scores below its threshold
- **THEN** `scripts/eval-prompts` exits non-zero and its summary names the case

#### Scenario: `ci` stays offline

- **WHEN** `gates run ci` runs
- **THEN** no eval case runs, and no model credential is needed
