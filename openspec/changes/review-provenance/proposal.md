# Proposal

## Why

The loop says convention review MUST run as the `convention-review` subagent, never inline (`skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`), and the agent is described as read-only. Neither claim is checked. `gates review record` is written by the caller, so a review the implementer ran in its own context, under the "degraded mode" fallback, records the same `clean` row as a real subagent review. The reviewer also has `Bash` and loads the project's `CLAUDE.md`, so "read-only" and "isolated" are prose.

Google's elephant-goldfish-model (EGM) shows the alternative: a reviewer's isolation is set in host configuration, a review that did not run in a fresh context is reported as such and never as clean, and the evidence comes from the host's own records, not from the reviewer or its caller. Claude Code now exposes what that needs: `SubagentStop` hooks carry `agent_type`, `agent_id` and `agent_transcript_path`, tool hooks fired inside a subagent carry `agent_type`, and agent frontmatter takes `omitClaudeMd`.

This passes the rejection test as "makes a stated guarantee enforceable". It authors nothing and names no stack command.

## What Changes

- **Review provenance, recorded by a hook.** A `SubagentStop` hook matching the `convention-review` agent records a `review-provenance` ledger row: the agent id, its transcript path, and the tree it stopped on. The caller never writes it.
- **Every review row says how the review ran.** `gates review record` stamps the row `via: subagent` when provenance exists for the same tree, and `via: inline` otherwise. Per-task and authored-set (`--scope authored`) reviews are both covered. The command's output names which, so an inline review is visible at the moment it is recorded.
- **The reviewer's limits move into configuration.** `agents/convention-review.md` gains `omitClaudeMd: true`. A `PreToolUse` hook on `Bash` denies any command from the `convention-review` agent outside a fixed read-only set (`git diff`, `git show`, `git log`, `git status`, `gates rules`, `gates tests show`).
- **The inline fallback stays, but is named.** The prompts keep the fallback for hosts without nested subagents, and say it records `via: inline`.
- **An opt-in refusal.** A new manifest key, `loop.review` (`recorded`, the default, or `isolated`). Under `isolated`, `gates merge` step 1 refuses a change whose latest clean review for any task, or for the authored set, is `via: inline`. Under the default, step 1 only reports the count of inline reviews.
- **Unchanged:** review verdicts never block a commit (the D1 reasoning in `bin/gates` above `cmd_review` stands: a review is an LLM judgement, and blocking on it would enforce only that a command was typed).

## Capabilities

### New Capabilities

- `review-provenance`: how a convention review's isolation is enforced and recorded, which review rows count as isolated, and when the merge refuses a review that ran inline.

### Modified Capabilities

None. The existing review recording (`gates review record`, its row and marker) keeps its behaviour. The new row field and the opt-in refusal are specified in the new capability.

## Impact

- `bin/gates`: `review record` gains the `via` stamp, a new `review provenance` subcommand fed by the hook, the `loop.review` key, and a check in `_merge_prove_head`.
- `hooks/hooks.json`: a `SubagentStop` entry and a second `Bash` `PreToolUse` script. New `hooks/record-review-provenance.sh` and `hooks/gate-reviewer-bash.sh`.
- `agents/convention-review.md` (frontmatter), `skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md` (the fallback's wording).
- `schema/gates.schema.json`, `tests/contract.json`, `adoption/catalog.json` (a new key for `/gatedloop:upgrade`), README.md, SETUP.md and AUTOMATION.md.
- Requires Claude Code 2.1.271 or later for `omitClaudeMd`; on older versions the key is ignored and the hooks still apply.
- Related, not in scope: the `prompt-evals` change could grade a review's isolation from transcripts the same way. That is a note for its author, not an edit to an approved plan.
