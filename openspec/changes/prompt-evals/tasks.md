# Tasks

## 1. Spike and fixture

- [ ] 1.1 Spike, recorded in `evals/README.md`: using one throwaway case, establish whether `claude plugin eval . --scaffold` runs the scaffold in the case's cwd, whether the loaded plugin's `bin/` and `openspec` are on `PATH` there, whether a dispatched subagent's tool calls appear in the graded trace, and the pilot cost of one implementer run and one review run; adjust D2's secondary graders or D5's ceiling to the findings, and say so in the PR [oracle: none]
- [ ] 1.2 Add `evals/_fixture/scaffold.sh <variant>` per design D6. It builds the `weak-spec`, `ready`, `review-violation` and `review-clean` variants, and exits non-zero naming a missing `openspec`, `gates` or `git`. Add the `evals` surface to `.gates.yaml` and `evals/results/` to `.gitignore` (D7) [oracle: none]

## 2. Cases

- [ ] 2.1 Add `evals/implementer-halts-on-weak-spec/` and `evals/implementer-ready-stops-before-merge/`, with the graders in design D2 [oracle: none]
- [ ] 2.2 Add `evals/review-cites-stack-agnostic-prompts/` and `evals/review-clean-diff/`, with the graders in design D2. The violation case's prompt says the violation is planted [oracle: none]

## 3. Wrapper and release reminder

- [ ] 3.1 Add `scripts/eval-prompts` per design D5. Unit-test its flag building, its `--max-cost-usd` override, and the summary line parsed from a recorded `--json` result: all pass, a 2/3 case, and a failing case giving a non-zero exit [oracle: unit]
- [ ] 3.2 `scripts/release status` reports `prompts_changed` and prints the advisory reminder per the plugin-release delta. Unit-test that a prompt edit since the tag lists the path, that no prompt edit prints nothing, and that the exit code and suggested level don't change [oracle: unit]

## 4. Docs and close

- [ ] 4.1 Add a "Prompt evals" step to RELEASING.md. Rewrite CLAUDE.md's "Prompts stay untested" line and the `.gates.yaml` header to say what the suite covers and that `ci` still doesn't. Record the measured cost of a full run in `evals/README.md` [oracle: none]
- [ ] 4.2 Run `python3 scripts/eval-prompts` once on the branch and paste its summary line into the PR. `gates run ci` green; `openspec validate prompt-evals --strict` passes [oracle: none]
