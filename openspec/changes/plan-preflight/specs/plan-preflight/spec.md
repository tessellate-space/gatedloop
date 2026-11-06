# Spec Delta

## Purpose

Close the planning phase: before a person approves a plan, the planner runs a loop in which fresh-context checkers read the plan cold, at a depth the shim computes from the plan's blast radius, until the loop ends green, on a recorded question, or stalled. Its verdicts are recorded for the approver and never block, and no approval or merge guarantee changes.

## ADDED Requirements

### Requirement: The plan loop runs its stages in order

Under `loop.plan-preflight: run`, the propose path SHALL run the plan loop before the plan PR asks for approval. A round SHALL run, in order: `gates plan round`, plan review through each lens of the tier, and, under the full tier, the test author in preflight mode, `gates tests handoff --dry-run` and the authored-set review. A round SHALL end at the first stage that has a finding, and the finding SHALL return to the planner, who amends the plan before the next round.

#### Scenario: A lens finding ends the round

- **WHEN** under the full tier the implementability lens reports a finding in round 1
- **THEN** no test author is dispatched in round 1, and the round's record shows lens verdicts only

#### Scenario: A green round

- **WHEN** every checker the round's tier runs records `clean` on the round's plan digest
- **THEN** `gates plan status <change>` reports the loop as green

### Requirement: The loop stops on a question only a human can answer

A checker's finding that only a human can answer SHALL be recorded with `gates plan record --verdict question` and a report stating the question and its options. `gates plan status` SHALL then report the loop as stopped on a question, and the propose path SHALL open or update the plan PR as a draft with the question at the top of its body.

#### Scenario: A product choice the specs leave open

- **WHEN** the zero-decision lens reports that task 2.1 needs a choice between two retention periods, and the planner records it as a question
- **THEN** `gates plan status` reports `question` with the recorded options, and no further round opens until `gates plan resume`

### Requirement: The round budget is counted by the shim

`gates plan round <change>` SHALL count the rounds of the current loop from the change's `plan-round` rows. The budget SHALL be `loop.plan-preflight.rounds` (default 3) under the full tier and 1 under the light tier. When the budget is spent, it SHALL append a `plan-round` row with outcome `stalled`, exit 1 and say so. A round SHALL open only on a plan that passes `gates plan check`, and a refused open SHALL count no round.

#### Scenario: A stalled loop

- **WHEN** a full-tier loop has had three rounds and the planner runs `gates plan round` again
- **THEN** it exits 1 saying the loop stalled, and `gates plan status` reports `stalled`

#### Scenario: Static findings cost no round

- **WHEN** `gates plan round` finds an untagged task under `loop.task-oracle: required`
- **THEN** it exits 1 naming the task, and appends no `plan-round` row

### Requirement: A resumed loop has a fresh budget and a recorded reason

`gates plan resume <change> --reason <text>` SHALL start a new loop with a fresh round budget and append a `plan-round` row with outcome `resume` and the reason. It SHALL refuse an empty reason. `gates plan status` SHALL list every resume with its reason.

#### Scenario: Resuming after a human answered

- **WHEN** the loop stopped on a question and the planner runs `gates plan resume <change> --reason "retention: 30 days, per review"`
- **THEN** the next `gates plan round` opens round 1 of loop 2, and the status lists the resume and its reason

### Requirement: The floor is computed from deterministic signals

`gates plan tier <change>` SHALL compute a floor of `full` when any one signal is high, and `light` otherwise. The signals SHALL be: task lines (default threshold 20); named paths (12); hot surfaces for those paths (2); a MODIFIED, REMOVED or RENAMED requirements section; an oracle tag naming a gate in `full-at.oracles` (empty by default), or with `rewrites:` when that list is non-empty; and a hot `blast-radius: high` surface. It SHALL print each signal's value and whether it is high.

#### Scenario: A light floor

- **WHEN** a plan has four tasks tagged `[oracle: unit]`, names three files on one surface, has only ADDED requirements and no high-radius surface
- **THEN** `gates plan tier` prints a `light` floor with every signal low

#### Scenario: A modified requirement makes the floor full

- **WHEN** a plan has two tasks and a spec delta with a `## MODIFIED Requirements` section
- **THEN** `gates plan tier` prints a `full` floor naming that signal

#### Scenario: A declared costly oracle makes the floor full

- **WHEN** `.gates.yaml` declares `full-at.oracles: [e2e]` and a three-task plan has a task tagged `[oracle: e2e]`
- **THEN** `gates plan tier` prints a `full` floor naming the oracle signal

#### Scenario: No costly oracle is declared

- **WHEN** `full-at.oracles` is absent and a three-task plan has a task tagged `[oracle: integration rewrites: tests/a.test.ts]`
- **THEN** the oracle signal is low

#### Scenario: Task count alone is a size backstop

- **WHEN** a plan has twelve tasks, all tagged `[oracle: unit]`, on one surface, with only ADDED requirements
- **THEN** `gates plan tier` prints a `light` floor

#### Scenario: A high-radius surface makes the floor full

- **WHEN** the plan names a path on a surface declaring `blast-radius: high`
- **THEN** `gates plan tier` prints a `full` floor naming that surface

### Requirement: The classifier may only raise the tier

The effective tier SHALL be the higher of the floor and the classifier's combined verdict, before overrides. A combined verdict of `light`, at any confidence, SHALL never lower a `full` floor.

#### Scenario: The classifier says light on a full floor

- **WHEN** the floor is `full` and the classifier returns `tier: light` with every dimension below its threshold
- **THEN** the effective tier is `full`, and the record shows both the floor and the verdict

#### Scenario: The classifier raises a light floor

- **WHEN** the floor is `light` and the classifier returns `tier: full`
- **THEN** the effective tier is `full`, and the record carries the classifier's answers

### Requirement: The classifier's contract is typed answers

A classifier SHALL receive `{digest, dimensions}` as JSON on stdin, and never whole artifacts. It SHALL return JSON on stdout matching `schema/plan-tier.schema.json`: `tier` (`light` or `full`), `confidence` (a number from 0 to 1, or null), `evidence` (a list of `{dimension, value, confidence}`) and an optional `reason` (a string or null). The shim SHALL validate every verdict against that shape, from either provider, in stdlib code.

#### Scenario: A verdict with no reason is valid

- **WHEN** a classifier returns `{"tier": "light", "confidence": 0.81, "evidence": [{"dimension": "persisted-data", "value": 0.12, "confidence": 0.9}], "reason": null}`
- **THEN** the shim accepts it, and the record shows no reason

#### Scenario: Validating the built-in lens's verdict

- **WHEN** `gates plan classify <change> --verdict v.json` is given an object whose `tier` is `medium`
- **THEN** it exits 1 naming the schema error, and stores no verdict

### Requirement: Blast radius is asked as typed dimensions, combined by the shim

The shim SHALL combine a verdict as `full` when its `tier` is `full` or when any evidence item for an enabled dimension meets that dimension's threshold, and `light` otherwise. Evidence for an unknown dimension SHALL be recorded and ignored.

#### Scenario: Dimension answers raise the tier

- **WHEN** the floor is `light` and a classifier returns `tier: light` with `persisted-data` at 0.74 against a threshold of 0.5
- **THEN** the combined verdict is `full`, the effective tier is `full`, and the record names `persisted-data` as the dimension that raised it

### Requirement: The dimensions are shipped data, overridable in the manifest

The dimensions SHALL be defined in the shipped data file `rules/plan-tier-dimensions.json`, each with an id, a kind (`probability`, `choice` or `score`), its question and its raise threshold. `loop.plan-preflight.dimensions` SHALL override a dimension's threshold, or turn it `off`. The same dimensions SHALL be given to both providers.

#### Scenario: A threshold override

- **WHEN** the manifest sets `dimensions: {persisted-data: 0.8}` and the classifier answers 0.74 for it
- **THEN** that dimension does not raise the tier

### Requirement: Classifier confidences are recorded and never lower the tier

The round row SHALL record the verdict's confidence and each evidence item's confidence. No confidence SHALL lower the floor or the combined verdict.

#### Scenario: A confidence is recorded

- **WHEN** a classifier returns `confidence: 0.42` and `irreversible` at 0.61 with confidence 0.38
- **THEN** the round row records 0.42 and 0.38, and the combined verdict is `full` because 0.61 meets the threshold

### Requirement: The shim builds the classifier's input as a bounded digest

`gates plan digest <change>` SHALL build the plan digest deterministically, in this priority order: the signals and floor; the named paths with their surface and `blast-radius`; the spec delta section headers with their requirement titles; the task lines without oracle tags or checkboxes; the proposal's "What Changes" bullets; and the design's decision headings.

#### Scenario: A digest that fits

- **WHEN** the digest's compact JSON is within `classifier-input-limit`
- **THEN** the classifier receives every section untrimmed, and `trimmed` is empty

### Requirement: The printed digest is exactly what the classifier saw

`gates plan digest <change> --json --limit N` SHALL print byte-for-byte the input an external classifier is given at limit `N`. The built-in `gatedloop.blast-radius` lens SHALL read the same digest, with no limit.

#### Scenario: Seeing what the classifier saw

- **WHEN** a classifier ran at the manifest's limit of 48000 bytes
- **THEN** `gates plan digest <change> --json --limit 48000` prints the same bytes it received on stdin

### Requirement: An over-limit digest is trimmed from the bottom, and the trim is recorded

When the digest exceeds `loop.plan-preflight.classifier-input-limit` (bytes, default 48000), the shim SHALL drop entries from the bottom of the priority list, the decision headings first, then the "What Changes" bullets, then the task lines, each from its last entry up, until it fits. The digest's `trimmed` field and the round row SHALL name each trimmed section and how many entries it lost.

#### Scenario: A trimmed digest

- **WHEN** the full digest is 60000 bytes, the limit is 48000, and dropping the decision headings and five task lines brings it within the limit
- **THEN** the classifier receives the trimmed digest, and the round row records `decisions` and `tasks: 5` as trimmed

### Requirement: A digest over the limit after trimming yields full with no call

When the signals, floor, named paths and spec delta headers alone exceed the limit, the shim SHALL make no classifier call, run no built-in fallback, and set the effective tier to `full`, recording `classifier: skipped, cause: digest over limit`.

#### Scenario: Too large to classify cheaply

- **WHEN** the first three digest sections alone are 60000 bytes against a limit of 48000
- **THEN** `gates plan tier` reports `classifier: skipped, cause: digest over limit` and an effective tier of `full`, and the classifier command is not run

### Requirement: An external classifier is a bound command

The manifest key `loop.plan-preflight.classifier` SHALL name a command, and `classifier-timeout` its timeout in seconds (default 60). `gates plan tier` and `gates plan round` SHALL run a declared classifier in the repository root with the input on stdin and the shim's environment passed through unchanged. They SHALL use its output when it exits 0 and validates, and the record SHALL name the provider `external`.

#### Scenario: A declared classifier with valid output

- **WHEN** the manifest declares a classifier command that prints `{"tier": "full", "confidence": 0.9, "evidence": [{"dimension": "public-interface", "value": 0.88, "confidence": 0.9}], "reason": null}`
- **THEN** `gates plan tier` reports provider `external` and that verdict, and the effective tier is `full`

### Requirement: The shim handles no classifier secret

The shim SHALL NOT read `.env` or any secret for a classifier, SHALL NOT print or record the command's environment, and SHALL capture the command's stderr to a log under `.gatedloop/out/`.

#### Scenario: The command's stderr is captured, not recorded

- **WHEN** a declared classifier writes to stderr
- **THEN** the stderr goes to a log under `.gatedloop/out/`, and no ledger row or printed output carries it or the command's environment

### Requirement: Classifier fallback is visible, never silent

When no classifier is declared, or the declared command exits non-zero, times out, or returns output that is not JSON or fails the schema, `gates plan tier` SHALL print `classifier: builtin` with the cause, and the built-in `gatedloop.blast-radius` lens SHALL supply the verdict through `gates plan classify`. The round's record SHALL carry the provider and the cause.

#### Scenario: Invalid output falls back, recorded

- **WHEN** the declared classifier exits 0 and prints `{"tier": "full"}` with no `evidence`
- **THEN** `gates plan tier` prints `classifier: builtin` with a cause naming the missing `evidence`, and the next round row records provider `builtin` and that cause

#### Scenario: A timeout falls back, recorded

- **WHEN** the declared classifier runs longer than `classifier-timeout`
- **THEN** the shim stops it, `gates plan tier` prints `classifier: builtin, cause: timeout 60s`, and the round row records it

#### Scenario: An unavailable command falls back, recorded

- **WHEN** the declared classifier command does not exist and the shell exits 127
- **THEN** `gates plan tier` prints `classifier: builtin, cause: exit 127`, and the round row records it

#### Scenario: No classifier declared

- **WHEN** the manifest declares no classifier and the floor is `light`
- **THEN** `gates plan tier` prints `classifier: builtin, cause: none-declared`, and the propose path dispatches the plan-review agent with the `gatedloop.blast-radius` lens

### Requirement: A light floor needs a classifier verdict before a round opens

On a `light` floor, `gates plan round` SHALL refuse to open a round until a valid classifier verdict, or a cause recorded with `gates plan classify --unavailable <cause>`, exists for the current plan digest. With an `--unavailable` cause, the effective tier SHALL be the floor.

#### Scenario: Skipping the classifier

- **WHEN** the floor is `light`, no classifier is declared, and no built-in verdict has been passed to `gates plan classify`
- **THEN** `gates plan round` exits 1 saying a classifier verdict is needed

### Requirement: Raising the tier is free and recorded

`gates plan round --tier full` SHALL raise that round's tier, and a `Plan tier: full` line in `proposal.md` or `design.md` SHALL raise every round's tier. Neither SHALL need a reason. The round row SHALL record the source, `raised-flag` or `raised-plan`.

#### Scenario: The planner raises a light tier

- **WHEN** the effective tier is `light` and the planner runs `gates plan round <change> --tier full`
- **THEN** the round runs at `full`, and its row records the light computed tier and the source `raised-flag`

#### Scenario: The plan raises its own tier

- **WHEN** `proposal.md` holds the line `Plan tier: full` on a light floor
- **THEN** every round runs at `full` with the source `raised-plan`

### Requirement: Lowering the tier needs a reason in the plan

The tier SHALL be lowered only by a line `Plan tier: light — <reason>` in `proposal.md` or `design.md`. It SHALL lower the effective tier to `light` whatever raised it, and the round row SHALL record the source `lowered-plan` and the reason. A `Plan tier: light` line with no reason SHALL be a `gates plan check` finding, and `gates plan round` SHALL refuse to open a round while it stands. No flag SHALL lower the tier.

#### Scenario: Lowering with a reason

- **WHEN** the floor is `full` because of nine tasks, and `design.md` holds `Plan tier: light — nine one-line docs tasks, no code`
- **THEN** rounds run at `light`, and `gates plan status` shows the floor, the override and its reason

#### Scenario: Lowering without a reason

- **WHEN** `proposal.md` holds `Plan tier: light` with no reason
- **THEN** `gates plan check` exits 1 naming the line, and `gates plan round` opens no round

### Requirement: The tier's record shows every layer

Each `plan-round` row SHALL record the signals, the floor, the classifier's provider, fallback cause, verdict, confidences, reason and evidence, the override's source and reason, and the effective tier. `gates plan status <change>` SHALL print them in text, `--json` and `--markdown`.

#### Scenario: The approver reads the tier

- **WHEN** a round ran on a light floor raised to `full` by an external classifier
- **THEN** `gates plan status <change> --markdown` shows the floor, provider `external`, the classifier's reason, and the effective tier `full`

### Requirement: Plan review judges through one lens per run

The plugin SHALL ship `agents/plan-review.md`, a read-only agent that reads the plan's artifacts and only the files `gates plan brief <change> --lens <id>` names, and judges through that one lens. Every finding SHALL cite the lens id and a check number, as `<lens-id> #<n>`. Run through `gatedloop.blast-radius`, it SHALL return only the classifier JSON. The prompt SHALL name no project-specific tool.

#### Scenario: A finding cites its lens

- **WHEN** plan review through `gatedloop.implementability` finds that task 1.3 needs an artifact task 5.1 creates
- **THEN** its finding cites `gatedloop.implementability #2` and names both tasks

### Requirement: Lenses are ids plus rules, selected by the shim

The built-in lenses `gatedloop.implementability`, `gatedloop.zero-decision` and `gatedloop.blast-radius` SHALL be defined in `rules/plan-lenses.md`, one `### <lens-id>` section each, resolved from the plugin. `gates plan brief <change>` SHALL list the lenses the tier runs: `gatedloop.implementability` under light, and both judging lenses under full. A missing file or section SHALL fail loud.

#### Scenario: The lenses of each tier

- **WHEN** the effective tier is `light`
- **THEN** `gates plan brief <change>` lists `gatedloop.implementability` only, and under `full` it lists `gatedloop.implementability` and `gatedloop.zero-decision`

### Requirement: Loop provenance is recorded and never blocks

`gates plan round`, `gates plan record` and `gates plan resume` SHALL append `plan-round` and `plan-review` rows to `.gatedloop/runs/<change>.jsonl`, each carrying the loop, the round, the approval digest of the plan and a digest of its task lines. `gates plan record` SHALL refuse when no round is open, when the plan's digests changed since the round opened, or when the checker is not one the round's tier runs. No approval, handoff, merge, implementation or stats verdict SHALL read these rows.

#### Scenario: A verdict on amended content

- **WHEN** the planner amends `tasks.md` after round 2 opened and then runs `gates plan record <change> --checker lens:gatedloop.zero-decision --verdict clean`
- **THEN** it exits 1 saying the plan changed since the round opened

#### Scenario: Rows that decide nothing

- **WHEN** a change's ledger holds plan-loop rows
- **THEN** `gates handoff`, `gates merge` and attempt counting give the verdicts they give without them

### Requirement: Shim-run checkers are recorded from the shim's own run

`gates plan round` SHALL record the `plan-check` verdict, and `gates plan record --checker dry-run` SHALL run the dry run itself and record its exit, accepting no `--verdict`.

#### Scenario: Claiming a dry run

- **WHEN** the planner runs `gates plan record <change> --checker dry-run --verdict clean`
- **THEN** it exits 1 saying the shim records that checker from its own run

### Requirement: Preflight output persists across rounds

`gates tests brief <change> --preflight` SHALL print the preflight store as the place to write, and list the stale tasks: those whose digest changed or is absent, and those holding a path that a stale task holds. A clean `--dry-run` SHALL write the current digests.

#### Scenario: An amendment to one task line

- **WHEN** after a clean dry run the planner amends only task 2.1's line
- **THEN** the next `gates tests brief <change> --preflight` lists 2.1 as stale and every other task as kept

### Requirement: The preflight store is committed with the plan

The preflight store `openspec/changes/<change>/preflight/` SHALL hold the held tests in the holding area's layout and suffix, the per-task digests, the classifier verdict and each round's reports, and SHALL be committed on the plan branch with the plan.

#### Scenario: The store travels with the plan branch

- **WHEN** a round's store is committed on `plan/x` and pushed, and the branch is checked out in a fresh clone
- **THEN** `gates tests brief x --preflight` in that clone lists as kept every task the first clone's last clean dry run covered

#### Scenario: Committing the store is planning-grade

- **WHEN** the planner commits the store together with the plan and the change's ledger on `plan/x`
- **THEN** both commit hooks allow it as planning-grade, with no ci run

#### Scenario: The store archives with its change

- **WHEN** the change is archived
- **THEN** its `preflight/` directory is under the archived change's directory

### Requirement: The preflight store's shape is checked

`gates plan check` SHALL report as a finding each path under `openspec/changes/<change>/preflight/` outside the store's layout: `authored/<N.M>/` files with the `.authored` suffix or named `CHARACTERIZATION` or `NO-TESTS`, `digests.json`, `classifier.json`, and `reports/*.md`.

#### Scenario: A stray file in the store

- **WHEN** `openspec/changes/x/preflight/notes.txt` exists
- **THEN** `gates plan check x` exits 1 naming that path

#### Scenario: OpenSpec accepts the store

- **WHEN** a change holds a populated `preflight/` directory
- **THEN** `openspec validate <change> --strict` and `openspec status --change <change>` report what they report without it

### Requirement: A preflight never touches the real holding area

No preflight command SHALL read or write `.gatedloop/authored/<change>/`. A real `gates tests handoff`, without `--dry-run`, SHALL keep reading only that directory.

#### Scenario: The real holding area is untouched

- **WHEN** a full-tier loop authors, dry-runs and reviews
- **THEN** `.gatedloop/authored/<change>/` does not exist and was never created

### Requirement: A dry-run handoff runs the handoff's refusals and records nothing

`gates tests handoff <change> --dry-run` SHALL read the preflight store and run the same checks as a real handoff, including under `--task <N.M>`, with the same messages and exit status. It SHALL write no ledger row and no git object, and SHALL NOT require the change to be approved.

#### Scenario: A held set that contradicts a tag

- **WHEN** a task is tagged `[oracle: unit]`, its store directory holds `CHARACTERIZATION`, and `--dry-run` runs
- **THEN** it exits 1 with the real handoff's message for that contradiction, and the ledger is unchanged

#### Scenario: A clean dry run on an unapproved plan

- **WHEN** the change carries no approval and its store satisfies every refusal
- **THEN** `--dry-run` exits 0, says nothing was recorded, and writes no ledger row

### Requirement: A dry run does not compare tags with the target

`gates tests handoff --dry-run` SHALL NOT compare the tasks' oracle tags with the merge target's `tasks.md`, and SHALL print a line saying so. A real handoff SHALL keep the comparison.

#### Scenario: An amended plan whose tags differ from the target

- **WHEN** the plan branch retags a task that the merge target's `tasks.md` tags differently
- **THEN** `--dry-run` does not refuse over the difference, and a real handoff of the same tests still does

### Requirement: The preflight's authored set can be shown without a handoff

`gates tests show <change> --preflight` SHALL report the preflight store in the text and `--json` shapes `gates tests show` uses. Each rewrite's counts, and its diff with `--diff`, SHALL be taken against the path at `HEAD`. It SHALL read no ledger row and write nothing.

#### Scenario: Reviewing a preflight's tests

- **WHEN** the store holds tests for tasks 1.1 and 2.1 and no handoff is recorded
- **THEN** `gates tests show <change> --preflight` lists both tasks with their paths

#### Scenario: A held rewrite's diff

- **WHEN** task 2.1 declares `rewrites: tests/a_test.py` and its store directory holds the full file
- **THEN** `gates tests show <change> --preflight --diff` prints that file's unified diff against `HEAD`

### Requirement: Plan checks fail loud and write nothing

`gates plan check <change>` SHALL exit 1 on any finding, naming each finding's task and path, and otherwise exit 0 and say the plan is clean. It SHALL write nothing. An unknown change SHALL exit 1. With `--json` it SHALL print `{change, preflight, tier, against, findings: [{kind, task, path, detail}]}`.

#### Scenario: A clean plan

- **WHEN** every tag is well formed and every declared rewrite exists at the base
- **THEN** `gates plan check` exits 0 and writes no file

#### Scenario: An unknown change

- **WHEN** `gates plan check missing` runs and no such change exists
- **THEN** it exits 1 and says so

### Requirement: Plan checks report what the handoff would refuse

`gates plan check` SHALL report this change's oracle-tag errors and warnings as `gates validate` words them, and, under `loop.task-oracle: required`, every untagged task.

#### Scenario: Untagged tasks under a required oracle

- **WHEN** the manifest declares `loop.task-oracle: required` and task 3.2 carries no tag
- **THEN** `gates plan check` exits 1 naming task 3.2

### Requirement: Plan checks report a rewrite of a file absent at the base

`gates plan check` SHALL report each `rewrites:` path absent at the base: `HEAD`, or `<ref>` with `--against <ref>`. When an earlier task's line names the path, the finding SHALL say that the earlier task creates the file.

#### Scenario: A rewrite of a file an earlier task creates

- **WHEN** task 1.1's line names `` `tests/new_test.py` ``, the file is absent at `HEAD`, and task 2.1 is tagged `[oracle: unit rewrites: tests/new_test.py]`
- **THEN** `gates plan check` exits 1 with a finding for task 2.1 saying task 1.1 creates the file

### Requirement: The drift check names what the plan names that moved

With `--against <ref>`, `gates plan check` SHALL report each path the plan names, excluding the change's own directory, that was modified, deleted or renamed between the plan's base commit and `<ref>`. The base SHALL be the latest commit in `<ref>`'s history touching the change's directory when `<ref>` holds the change, and `git merge-base HEAD <ref>` otherwise. An unresolvable `<ref>` SHALL exit 1.

#### Scenario: A named file changed while the plan waited

- **WHEN** the approved plan's design names `` `bin/tool.py` `` and a later commit on the target modifies it
- **THEN** `gates plan check <change> --against <target>` exits 1 naming `bin/tool.py` as modified

#### Scenario: Nothing named moved

- **WHEN** commits land on the target that touch no path the plan names
- **THEN** `--against` adds no finding

### Requirement: The plan preflight is opt-in

`loop.plan-preflight` SHALL accept `run` or `skip`, or a mapping with `mode` (`run` or `skip`), `rounds`, `full-at` (`tasks`, `files`, `surfaces`), `classifier`, `classifier-timeout`, `classifier-input-limit` and `dimensions`, and SHALL default to `skip`. PyYAML and `_mini_yaml` SHALL read both forms alike. `gates validate` SHALL refuse any other mode, an unknown key, a non-positive or boolean integer, and `run` together with `loop.test-author: inline`, naming both keys.

#### Scenario: A boolean-looking value

- **WHEN** `.gates.yaml` declares `loop.plan-preflight: on`
- **THEN** `gates validate` exits 1 naming the key and the accepted values `run` and `skip`, under either parser

#### Scenario: The mapping form

- **WHEN** `.gates.yaml` declares `loop.plan-preflight` as `{mode: run, full-at: {tasks: 5}}`
- **THEN** `gates plan tier` uses 5 as the task threshold and the defaults for the rest

#### Scenario: Preflight with an inline author

- **WHEN** the manifest declares `loop.plan-preflight: run` and `loop.test-author: inline`
- **THEN** `gates validate` exits 1 naming both keys

### Requirement: Surfaces may declare their blast radius

A surface SHALL accept `blast-radius: high` or `blast-radius: normal`, defaulting to `normal`. `gates validate` SHALL refuse any other value.

#### Scenario: A misspelt radius

- **WHEN** a surface declares `blast-radius: hgh`
- **THEN** `gates validate` exits 1 naming the surface and the accepted values

### Requirement: The propose path always runs the plan check

`/gatedloop:propose` SHALL run `gates plan check <change>` before it commits the plan, whatever `loop.plan-preflight` says, and SHALL return its findings to the planner to amend. Under `skip` it SHALL dispatch no checker.

#### Scenario: The preflight is off

- **WHEN** `loop.plan-preflight` is absent
- **THEN** the propose command runs `gates plan check` and dispatches no plan review and no test author

### Requirement: The test author's preflight mode records nothing

In preflight mode the test author SHALL write only to the store that `gates tests brief --preflight` prints, and only for the stale tasks it lists. It SHALL end with `gates tests handoff --dry-run` and never run a real handoff. It SHALL return, as `blocked: weak-spec`, a task whose tests need what only a later task provides (naming both tasks) and a red-first task whose tests can only pass.

#### Scenario: A task-order deadlock

- **WHEN** task 1.3's tests need an artifact that only task 5.1 creates
- **THEN** the preflight author returns `blocked: weak-spec` naming tasks 1.3 and 5.1, and runs no real handoff

### Requirement: Held tests are never committed off a change branch

`gates tests check`, which both commit hooks run, SHALL refuse a staged path under `.gatedloop/authored/` whenever the current branch resolves to no active change, naming each path. On a branch that names an active change, the verdict SHALL be unchanged.

#### Scenario: A held test staged on a plan branch

- **WHEN** on `plan/x`, `.gatedloop/authored/x/1.1/tests/a_test.py.authored` is staged with the plan
- **THEN** `gates tests check` exits 1 naming that path, and both the tool hook and the git-layer `pre-commit` hook deny the commit

#### Scenario: The authoring commit on a change branch

- **WHEN** on the change branch `x`, the holding area is staged for the authoring commit
- **THEN** `gates tests check` gives the verdict it gives today

### Requirement: A preflight test is never committed runnable

`gates tests check` SHALL refuse, on any branch, a staged file under `openspec/changes/<change>/preflight/authored/` whose name lacks the `.authored` suffix and is not `CHARACTERIZATION` or `NO-TESTS`, naming each path and the name it should have.

#### Scenario: An unsuffixed test in the store

- **WHEN** on `plan/x`, `openspec/changes/x/preflight/authored/1.1/tests/a_test.py` is staged
- **THEN** `gates tests check` exits 1 naming it and `tests/a_test.py.authored`, and both commit hooks deny the commit

#### Scenario: A suffixed store

- **WHEN** on `plan/x`, the store's held files all carry the suffix
- **THEN** this refusal does not fire
