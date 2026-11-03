# Design

## Context

See proposal.md for the motivation. The relevant current state in `bin/gates`:

- `_tests_defect` validates `--kind` and a non-empty `--detail`, applies the per-kind caps (`MAX_TEST_DEFECTS_BY_KIND`) and appends a `test-defect` row. Past the `assertion` cap, its refusal quotes the earlier defects' details only.
- A handoff row (`TESTS_HANDOFF_EVENT`) records each task's held tests as `{path: blob}`; `_authoring_state` folds them, a `--task` handoff replacing that task's entry. So "did the held tests change since the previous handoff" is a blob comparison the shim can already make.
- `gates tests check` already locates a task's latest placement and the first run of its oracle gate after it (the red-after-placement check). The `green` evidence check reuses that lookup, asking for a passing run instead.
- The author's defence exists only in its report to the dispatcher (`agents/test-author.md`, re-dispatch paragraph).

## Goals / Non-Goals

**Goals:**

- Neither side of a dispute can make a claim the shim cannot resolve.
- The ledger holds the whole exchange, so a human reading a halt sees both positions.

**Non-Goals:**

- Judging whether a citation supports the claim. The shim checks that the cited evidence exists, not that it proves the point. That judgement stays with the other agent and, past the cap, the human.
- Changing the caps or the halt causes.
- Citations on authored-set review findings (the convention review's findings already cite a rule-id).

## Decisions

**D1. Three citation forms, resolved against the change branch's worktree.** `path` and `path:line` (`path:a-b` for a range) resolve when the file exists in the worktree, including the holding area `.gatedloop/authored/<change>/`, and the line or range is within it. `spec:<capability>#<scenario>` resolves when a `#### Scenario: <scenario>` exists under that capability in the change's delta specs or in `openspec/specs/`, matched case-insensitively with whitespace collapsed. Alternatives considered: free-form URLs (unresolvable offline, rejected) and symbol names (would need a language-aware index, against `zero-dep-shim` and `stack-agnostic-prompts`, rejected; `path:line` covers a symbol).

**D2. `--cite` is repeatable and required for `setup` and `assertion`, not for `green`.** A `green` defect's claim is a fact about a run, and the run is in the ledger, so the shim checks the run instead of asking the agent to point at it. That is stronger evidence than any citation.

**D3. The defence is a flag on `tests handoff`, not a new subcommand.** A defence already is a handoff of unchanged tests (`agents/test-author.md`), so `--defend` makes that existing act carry its reason. The shim refuses `--defend` when the task's held blobs differ from its entry in the previous handoff state, or when no `test-defect` row for the task follows its previous handoff. The `test-defence` row is written next to the handoff row, in the same call.

**D4. Show and the cap refusal read the exchange from the ledger in order.** Defects and defences for a task are interleaved by ledger order, so a reader sees "defect, defence, defect" as it happened.

**D5. Default-on, keyed on the handoff row.** New handoff rows carry `"disputes": "cited"`. The checks in D1–D3 apply when the task's governing handoff row has it, so a change handed off before the upgrade keeps the old rules until its next full handoff. Alternative considered: a manifest key. Rejected because the checks only constrain the plugin's own agents, adopters configure nothing, and a key would offer a way to switch off a guarantee the loop already claims. This needs the maintainer's approval, because the standing rule is that new adopter-facing behaviour is opt-in unless the plan says otherwise. The plan PR asks for it.

## Risks / Trade-offs

- [Agents cite something trivially resolvable, such as the test file itself, to get past the check] → Accepted. The check only removes the evidence-free claim. Whether a citation is to the point is still judged by the other side, and the cap still brings in a human. The prompts say what a useful citation is.
- [A spec scenario renamed mid-change breaks a recorded citation] → Citations are resolved once, when recorded. A later rename does not invalidate a row.
- [More refusals mean more halts in unattended runs] → A refusal is immediate and names the fix (add `--cite`). It costs a retry, not a halt.

## Migration Plan

None beyond D5: in-flight changes keep the old rules. Rollback is reverting the change; the new row kind and fields are extra data in the ledger.
