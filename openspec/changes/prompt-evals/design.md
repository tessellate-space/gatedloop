# Design

## Context

**What exists.** `claude plugin eval` is in Claude Code 2.1.299 (`claude plugin eval --help`):
- **Case layout.** A case is `evals/<case>/prompt.md`, or `case.yaml`, plus `graders/*.md`. Execution fields: `max_turns`, `timeout_seconds` (default 300, maximum 3600), `allowed_tools`, `model`, `runs` (default 3).
- **Scaffolding.** `context.scaffold_script` is bash that stages the workspace. It runs only under `--scaffold`, as the user.
- **Grader types:**
  - `regex`, with `target` set to `last_message`, `trace`, `files` (the paths created) or `{source: file, path}` (a file's contents), and `match` set to `contains`, `not_contains` or `count:N`;
  - `file_exists`;
  - `llm`, judged by haiku by default;
  - `tool_used` (`tool`, `input_match`, `min`, `max`, `arm`);
  - `tool_order`.
  There is no script grader.
- **The run.** Each run is a full `claude` child on the caller's own credential, in a sandbox home whose cwd is a fresh git repository. The run reports `costUsd`. `--max-cost-usd` aborts with exit 2, and `--threshold` (default 1.0) exits 1 when a case scores below it. `--trust-plugin` skips the first-run prompt for unattended use, and `--no-publish` keeps the HTML report local.
- **Ablation.** By default the suite also runs a no-plugin baseline arm.
- **CI.** CI needs a model credential. No mode runs keyless.

**What this repo has.** It declares no `eval` gate. SETUP defines `eval` as an advisory scored pipeline, `gates run eval <dataset> <score>`, called at change completion. The test fixtures in `tests/_*.py` build real repositories in Python. They are unittest helpers and can't be called from a bash scaffold.

## Goals / Non-Goals

**Goals:**
- A check of the agents' load-bearing promises that a prompt edit can fail:
  - the implementer halts rather than guesses;
  - done ⟺ committed;
  - the implementer stops before the merge;
  - the review cites a rule-id, and stays quiet on a clean diff.
- Outcome grading, so a reworded prompt that keeps the behaviour still passes.
- A cost the maintainer can see and cap.

**Non-Goals:**
- Running in `ci`, or on every commit or every change.
- A benchmark score, or a comparison between models.
- Checking the prose quality of any prompt.
- An adopter-facing eval feature. This is the repo's own tooling.

## Decisions

### D1. `claude plugin eval`, with a suite under `evals/`

It is the host's own runner, so it loads the plugin the way an adopter's session does, with the agents, hooks and `bin/` on `PATH`. A hand-rolled `claude -p` harness would have to rebuild that loading and its sandbox.

Cases use `prompt.md` with frontmatter. Each case pins:
- `model: sonnet`, the model the agents declare;
- `runs: 3`;
- a `timeout_seconds` sized to the work: 900 for the implementer cases, 300 for the review cases.

### D2. Four cases, graded on files

The smallest set that catches a real regression in each promise:

| Case | Primary graders (outcome) | Secondary |
|---|---|---|
| `implementer-halts-on-weak-spec` | ledger file contains `"gate": "halt"` and `"cause": "weak-spec"`; `tasks.md` does not contain `- [x] 1.1` | `tool_used Bash input_match "gates merge" min 0 max 0 arm both` |
| `implementer-ready-stops-before-merge` | `tasks.md` contains `- [x] 1.1`; ledger contains `"gate": "ready"`; last message contains `READY TO MERGE` | same no-merge grader; `tool_used Bash input_match "git commit" min 1` |
| `review-cites-stack-agnostic-prompts` | last message contains `stack-agnostic-prompts` | — |
| `review-clean-diff` | last message does not contain `stack-agnostic-prompts`, and does not contain a finding marker | — |

The two implementer cases contrast with each other, and so do the two review cases. A prompt that always halts fails the ready case. A review that always reports a finding fails the clean case.

Which halt situation the fixture plants: a task whose text asks for the opposite of its spec scenario. That is `weak-spec` row one in `tdd-implementer`'s halt table, and the cheapest halt to provoke.

Ledger and `tasks.md` graders read file contents (`{source: file, path}`), which the graders can see whatever the run's trajectory was. `tool_used` graders are secondary, because whether a subagent's tool calls appear in the parent's trace is the first thing task 1.1 checks.

### D3. Dispatch by agent name

Each implementer case prompts: "Use the `gatedloop:tdd-implementer` agent to implement the approved change `<name>`." The case allows `Agent`, `Bash`, `Read`, `Write`, `Edit`, `Glob` and `Grep`.

The fixture sets `loop.test-author: inline`, so the implementer authors its own tests and needs no test-author dispatch. That keeps the case one agent deep.

Each review case prompts: "Use the `gatedloop:convention-review` agent on the staged diff." Its last message is graded.

### D4. No `eval` gate. Run on demand and at release

The `eval` gate runs at every change's completion, and so does everything bound to it: a bin-only or docs-only change would pay for model runs that can't move. Its contract is also a scored dataset (`{dataset}`/`{score}`), not a pass/fail suite.

So the suite runs:
- **on demand:** `python3 scripts/eval-prompts`, after editing a prompt;
- **at release:** `scripts/release status` reminds the maintainer when `commands/`, `skills/` or `agents/` changed since the tag.

The reminder is advisory. A refusal would make cutting a release need a credential and network access, which the release procedure never needed before. Running the suite is the maintainer's call, the same as a major bump.

### D5. `scripts/eval-prompts` pins the flags

It runs `claude plugin eval . --scaffold --trust-plugin --ablation none --no-publish --max-cost-usd <ceiling> --threshold 0.66 --json <results>/run.json` and prints one line:

`eval-prompts: 4 cases, 4 passed, $X.XX, results <dir>`

The individual flags:
- **`--ablation none`:** without the plugin, the agents and `gates` don't exist, so the baseline arm measures nothing. It would double the cost for a known zero.
- **`--threshold 0.66`:** with `runs: 3`, a case passes on at least 2 of 3 runs. Model runs are not deterministic, so a single flaky run shouldn't fail the suite. The summary lists any case that passed 2/3, so a drift shows before it fails.
- **`--max-cost-usd`:** set by default from task 1.1's measured pilot cost times 1.5, rounded up, and overridable on the command line.

The wrapper is stdlib Python. Its argument building and summary parsing get unit tests in `tests/`. The model runs themselves do not.

### D6. Fixtures: one shared scaffold, stack-free

`evals/_fixture/scaffold.sh <variant>` builds the workspace in the case's cwd:
1. `openspec init`, then one change with its proposal, spec, design and tasks, written from heredocs per variant;
2. a `.gates.yaml` with `ci: "sh gates/ci.sh"` and `unit: "sh gates/unit.sh"`, where the scripts check a plain text file the task edits;
3. `loop.test-author: inline` and `approval.plan: self`;
4. the plan committed on `main`, `gates approval attest <change> --local`, and the change branch created.

Each case's `scaffold_script` calls it with its variant. The scaffold checks for `openspec`, `gates` and `git` first, and exits non-zero naming any that is missing.

There are no stack commands, because the gates run `sh` over files the fixture owns. The one planted violation, `npm test` in a fixture `commands/*.md` for the review case, is test data. The case prompt says so, and `evals/**` is outside the `prompts` surface.

### D7. `evals/` gets its own surface

`.gates.yaml` gains an `evals` surface (`evals/**`) with no rules and no live-check:
- A commit to `evals/` then isn't scored as unmatched, so it doesn't force the full `ci` (err-full-scoping D1).
- The `prompts`-surface rules don't apply to the planted violation.

`evals/results/` is gitignored.

### D8. The rejection test

This is repo tooling: it ships no adopter behaviour and adds nothing to the contract. It is ours because it makes stated guarantees checkable that so far rested on the maintainer noticing a regression in a real run: halt-not-guess, done ⟺ committed, stop before the merge, findings cite their rule-id. It authors no artifact, and the fixtures name no stack.

## Risks / Trade-offs

- **The harness behaves differently from what this plan assumes.**
  - **Risk:** a subagent's tool calls may not appear in the trace; the plugin's `bin/` may not be on `PATH` in the sandbox; the scaffold may not run in the case's cwd.
  - **Mitigation:** task 1.1 is a spike that answers each question before any case is written. The primary graders read files, so they hold whatever the trace shows.
- **Cost.**
  - **Risk:** two implementer runs times three, on Sonnet.
  - **Mitigation:** the pilot measures it, the ceiling caps it, and the suite runs only on demand.
- **Flakiness.**
  - **Risk:** model runs vary.
  - **Mitigation:** 2/3 runs to pass, and 2/3 passes are reported.
- **The suite tests the plugin as installed from the checkout.**
  - **Risk:** it doesn't test an older adopter's cached copy.
  - **Mitigation:** none needed; that is what a release is for.
- **A rename breaks the graders.**
  - **Risk:** renaming a halt cause, the `READY TO MERGE` token or a rule-id breaks a grader.
  - **Mitigation:** none needed. Those tokens are part of the contract the agents' reports promise, so a break there is a finding.

## Deferred

- **`stalled` after the attempt budget.** Provoking it costs many red runs per case. The budget's refusal is enforced by the shim and already unit-tested, so only the halt-after-refusal remains, which the weak-spec case exercises.
- **`test-author` tag compliance.** A wrong or excluded `[oracle:]` tag is already refused in code by `gates validate` and `gates tests place`, so the prompt-only remainder is thin. It's a candidate for a second iteration, as is the test author writing on the declared gate.
- **Scheduled CI runs.** They need a paid credential as a repository secret, which is the maintainer's call. The wrapper is CI-ready (`--trust-plugin`, `--json`).
- **Cases for `merge-runner`, `/gatedloop:planner` and `/gatedloop:orchestrator`.**
