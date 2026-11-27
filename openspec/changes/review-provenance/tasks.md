# Tasks

## 1. Provenance, recorded by the host

- [ ] 1.1 Add `gates review provenance`: read SubagentStop hook JSON on stdin, refuse (exit 1, naming what is missing) unless `agent_type` is `convention-review` or `gatedloop:convention-review` and `agent_transcript_path` is an existing file, append a `review-provenance` row (agent id, transcript path, `_write_tree` tree) on a change branch, and do nothing off one; verify with a new `tests/test_review_provenance.py` covering both agent-type forms, a missing transcript, another agent type, and the merge target [oracle: unit]
- [ ] 1.2 Add `hooks/record-review-provenance.sh` and a `SubagentStop` entry in `hooks/hooks.json` matching `^(gatedloop:)?convention-review$`; the script pipes its input to `gates review provenance` and always exits 0, reporting failures on stderr (as `record-ask.sh` does); verify with a hook test that feeds a recorded SubagentStop payload and asserts one row, and a failing shim still exits 0 [oracle: unit]

## 2. Every review row says how it ran

- [ ] 2.1 Stamp `via: subagent|inline` in `cmd_review` by joining on the tree against the change's `review-provenance` rows, print which in the command's output, and read a row with no `via` as `inline`; extend `tests/test_review_record.py` for per-task and `--scope authored` rows, with and without provenance, and a row staged after the review (reads `inline`); check that the previous release's shim reads a ledger holding `review-provenance` rows without error, and record the result in the commit message [oracle: unit]

## 3. The reviewer's limits, in configuration

- [ ] 3.1 Add `hooks/gate-reviewer-bash.sh` as a second `Bash` `PreToolUse` script: when `agent_type` names the convention-review agent, allow only `git diff`, `git show`, `git log`, `git status`, `gates rules` and `gates tests show` (any flags; compound commands only when every part is allowed), parsing through `_gate_match.py`, and deny everything else naming the allowed set; leave every other agent and the main session untouched; verify with tests for an allowed read, a denied `git commit`, a denied `gates review record`, a mixed compound command, and the same commands from `tdd-implementer` [oracle: unit]
- [ ] 3.2 Set `omitClaudeMd: true` in `agents/convention-review.md`'s frontmatter and change its description's "Read-only" to say how that is enforced; verify with a test that reads the shipped frontmatter [oracle: unit]
- [ ] 3.3 In `skills/tdd-apply/SKILL.md` (5f and 4b step 2) and `agents/tdd-implementer.md`, say that the index must be staged before the review is dispatched, and that the inline fallback is recorded as `via: inline` and refused at merge under `loop.review: isolated`; verify by re-reading both against `stack-agnostic-prompts` and the convention review [oracle: none]
- [ ] 3.4 Document both hooks in AUTOMATION.md's enforcement section (what each records or denies, and that `omitClaudeMd` needs Claude Code 2.1.271 or later); verify the doc names each hook script that `hooks/hooks.json` registers [oracle: none]

## 4. Opt-in refusal at merge

- [ ] 4.1 Add `loop.review` (`recorded` default, `isolated`) to `schema/gates.schema.json` and `gates validate`, and rewrite `tests/contract.json` with `python3 tests/test_contract.py --write`; verify `gates validate` rejects `loop.review: strict` naming both values [oracle: unit]
- [ ] 4.2 In `_merge_prove_head`, take each task's and the authored set's latest clean `review` row; under `isolated`, add a problem naming every one whose `via` is not `subagent`; under `recorded`, print the count of inline reviews; verify in `tests/test_merge_prove_head.py` with an inline review refused, a later subagent review superseding it, and the default reporting only [oracle: unit]
- [ ] 4.3 Add a `loop.review` entry to `adoption/catalog.json` so `/gatedloop:upgrade` offers it, defaulting to leaving the key unset; verify with the adoption tests' catalogue checks [oracle: unit]
- [ ] 4.4 Describe `loop.review` and the `via` field in README.md and SETUP.md, including when to choose `isolated` (a host with nested subagents) and what an inline review means; verify `python3 scripts/release docs` reports no gap [oracle: none]
