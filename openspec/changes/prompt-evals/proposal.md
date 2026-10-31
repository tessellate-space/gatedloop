# Proposal

## Why

Nothing tests the prompts, which hold the loop's behaviour. CLAUDE.md and the `.gates.yaml` header both say so. `ci` covers the shim, the version fields and the plugin manifest, and no gate checks whether `tdd-implementer` halts instead of guessing, or whether `convention-review` cites the rule it applies. A prompt edit that breaks either is caught only if the maintainer notices it in a real run. That leaves a stability promise on the agents' behaviour uncheckable, and it is the v1 gap that no amount of shim testing closes.

Claude Code 2.1.299 ships `claude plugin eval`, which runs scripted cases against a plugin and scores them with graders. Each case is a `prompt.md`, or a `case.yaml`, with `graders/*.md`. A case may name a `scaffold_script` that stages a workspace, and graders can read files the run left behind. The agents' load-bearing promises leave their evidence in files: ledger rows, `[x]` ticks and the final report. So they can be graded on outcomes, never on wording.

## What Changes

- **An eval suite under `evals/`.** Four cases, each graded on what the run left behind:
  - `implementer-halts-on-weak-spec`: a task that contradicts its spec. The implementer records a `halt` row with cause `weak-spec`, ticks nothing, and never runs `gates merge`.
  - `implementer-ready-stops-before-merge`: a one-task change that is fully specified. The task's `[x]` is committed, a `ready` row is recorded, the report says `READY TO MERGE`, and `gates merge` is never run. This is the contrast case for the halt case.
  - `review-cites-stack-agnostic-prompts`: a diff that plants a hard-coded runner command in a shipped command file. The review's finding cites `stack-agnostic-prompts`.
  - `review-clean-diff`: a diff that breaks no rule. The review reports no finding.
- **Fixtures that name no stack.** A shared scaffold builds each case's repository: an OpenSpec project, one approved change, and a `.gates.yaml` whose gates are bound to POSIX `sh` scripts inside the fixture.
- **`scripts/eval-prompts`**, repo tooling that is never part of the contract. It runs the suite with the flags this repo needs, under a cost ceiling, and prints one summary line.
- **A reminder at release.** `scripts/release status` reports when a shipped prompt has changed since the tag. It names the command to run, and it never refuses. RELEASING.md gains the step.
- **No `eval` gate in `.gates.yaml`.** The suite is run on demand and at release, not on every change's completion (design D4).

## Capabilities

### New Capabilities
- `prompt-evals`: the scored suite that checks the shipped agents' load-bearing behaviour, and when it runs.

### Modified Capabilities
- `plugin-release`: `status` reports a shipped prompt change since the tag as a reminder to run the suite.

## Impact

- New: `evals/` (cases, graders and the shared scaffold), `scripts/eval-prompts`, and a test module for the wrapper and the `status` reminder.
- Changed: `scripts/release` (`status` and its `--json`), `RELEASING.md`, `CLAUDE.md` (the "prompts stay untested" line), `.gitignore` (`evals/results/`) and `.gates.yaml` (an `evals` surface).
- `evals/` sits at the plugin root, so it is copied with the plugin on install. It is test data, never a prompt the plugin loads.
- Running the suite costs model usage on the maintainer's own credential. `ci` never runs it.
