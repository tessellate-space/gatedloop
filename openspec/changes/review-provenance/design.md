# Design

## Context

See proposal.md for the motivation. The relevant current state:

- `cmd_review` in `bin/gates` appends a `review` row (`gate: review`, `exit` 0 or 1, `tree` from `git write-tree`, `task`, `scope`) and, when clean, a `review` marker on that tree. Its comment records D1 of the loop-hardening work: review never gates a commit, because a self-recorded LLM verdict proves only that a command was typed.
- The ledger's other evidence (`ci`, `live-check`) is written by the shim running the gate, so it cannot be claimed without the run. Review is the one gate whose run the shim never sees.
- Claude Code's hooks now say who is acting: tool events fired inside a subagent carry `agent_id` and `agent_type`, and `SubagentStop` carries `agent_type`, `agent_id`, `agent_transcript_path` and `last_assistant_message`. Its matcher filters on agent type, including plugin-scoped names. Plugin agents ignore a `hooks` key in their own frontmatter, so plugin hooks live in `hooks/hooks.json`.
- `omitClaudeMd` is a documented agent frontmatter key from Claude Code 2.1.271.

## Goals / Non-Goals

**Goals:**

- The shim learns that a review ran in isolation from the host, the way it learns about `ci` from the run.
- An inline review is visible in the ledger and in the merge's output.
- A project that wants it can make an inline review block the merge.

**Non-Goals:**

- Judging the review's quality. Provenance proves where it ran, not that it was right.
- Making the ledger tamper-proof. An agent with shell access could append a forged row by hand; `docs/candidates.md` ("A tamper-evident ledger") owns that. This change raises the cost of a false claim from "type a command" to "fabricate a transcript file and a row", and records the honest case correctly, which is the case that matters for a loop that is not adversarial.
- Changing when review runs, or making it block commits.

## Decisions

**D1. Provenance is a ledger row, written by a `SubagentStop` hook.** The hook (`hooks/record-review-provenance.sh`) pipes its input to `gates review provenance`, which appends `{gate: "review-provenance", agent_id, transcript, tree, change, ts}`. A ledger row, rather than a marker, because rows are committed with the task and travel with the branch to the merge, and step 1 already reads the change's rows. Alternative considered: a `PostToolUse` hook on the `Agent` tool, keyed on `tool_input.subagent_type`. Rejected because the docs don't specify the `Agent` tool's `tool_response` shape, while `SubagentStop`'s fields are documented. The hook, like `record-ask.sh`, never blocks: a recording failure goes to stderr and the hook exits 0, and the review row then honestly reads `inline`.

**D2. Join on the tree.** `review record` looks for a provenance row whose tree equals the tree it is about to stamp, using the same `_write_tree` (the index). The two are computed in the same worktree moments apart, so an unchanged index joins. If the caller stages more between the review and the record, the join fails and the row reads `inline`. That is the right answer: the review saw a different tree. The prompts already stage before dispatching the review, and `tdd-apply` will say so explicitly.

**D3. `review provenance` checks its input came from a hook.** It requires `agent_type` to name the convention-review agent (bare `convention-review` or plugin-scoped `gatedloop:convention-review`; the prefix depends on the install) and `agent_transcript_path` to be an existing file. This is the EGM rule "a receipt the reviewer writes is not evidence", applied as far as a stdlib shim can: the transcript is the host's record. Reading the transcript's contents is not attempted, because its format is not a documented contract.

**D4. The reviewer's `Bash` is narrowed by a hook, not by removing `Bash`.** The agent needs `git diff` and `gates rules`. `tools: Read, Grep` alone would remove both. A `PreToolUse` `Bash` script (`hooks/gate-reviewer-bash.sh`) acts only when `agent_type` names the convention-review agent and allows a command only when its parsed invocation (reusing `_gate_match.py`'s parsing, so redirections and heredocs are handled as the other gate hooks handle them) is one of `git diff`, `git show`, `git log`, `git status`, `gates rules` or `gates tests show`, with any flags. Compound commands (`&&`, `;`, `|`) are allowed only when every part is in the set. Everything else is denied with the set listed. Alternative considered: `disallowedTools` in frontmatter. Rejected because it can only remove a whole tool.

**D5. `omitClaudeMd: true` on the reviewer.** The reviewer's rules come from `gates rules` and the rules-doc. The project's `CLAUDE.md` is lore the author shares, which is exactly the shared blind spot a fresh reviewer exists to avoid, and it costs tokens on every review. On Claude Code before 2.1.271 the key is ignored and nothing breaks.

**D6. `loop.review: recorded | isolated`, default `recorded`.** This follows the maintainer rule that new adopter-facing behaviour is opt-in. `isolated` is checked in `_merge_prove_head` next to the authored-test lock: for each task, and for the authored set, take the latest `review` row with `exit: 0`; if its `via` is not `subagent`, that is a problem. A missing `via` (rows written before this change) reads as `inline`, so turning `isolated` on for an in-flight change refuses until its reviews are re-run, which is correct. Alternative considered: making `isolated` the default. Rejected for now because hosts without nested subagents (the documented fallback) would start failing merges they pass today. Revisit at 1.0.

**D7. `/gatedloop:upgrade` offers the key.** Like `loop.task-oracle`, the new key gets an entry in `adoption/catalog.json`, so existing adopters are asked once rather than discovering it in the changelog.

## Risks / Trade-offs

- [The plugin-scoped `agent_type` value differs from what D3 and D4 expect] → Both accept the bare and the `gatedloop:`-prefixed name, and the hooks.json matcher is `^(gatedloop:)?convention-review$`. Tests cover both forms.
- [`SubagentStop` does not fire for a background or cancelled subagent] → The review then reads `inline`, which is an over-report, never an under-report. Under `isolated` the remedy is re-running the review.
- [The `Bash` allowlist blocks a read command the reviewer legitimately needs] → The deny reason names the allowed set, so the reviewer reports it rather than looping. Widening the set is a one-line change with a test.
- [Forged provenance] → Out of scope (see Non-Goals). The row records the transcript path, so a later audit can check it.

## Migration Plan

No data migration. Old review rows read as `inline`, which only matters under `isolated`, which nobody has yet. Rollback is reverting the change. Whether an older shim reading a ledger that holds `review-provenance` rows treats them as inert is checked in task 2.1, not assumed.
