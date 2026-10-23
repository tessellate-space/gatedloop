# Proposal

## Why

Issue #27: a closed loop converges only with four things:
- feedback that explains a failure;
- distilled memory between attempts;
- an occasional fresh restart, so it doesn't keep polishing a dead end;
- a stopping rule.

Specloop has the first two halves only partly:
- **Feedback: yes.** Red output is printed in full, and every denial names its remedy.
- **Stopping rule: prose only.** "If a gate stays red after 2 focused fix attempts, HALT" is a sentence in `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md` §5e. `--attempt` is recorded on every ledger row, but nothing counts it, so a loop can keep retrying.
- **Memory: no.** The ledger records outcomes (gate, exit, tree), not lessons. A resuming agent gets `tasks.md` and git, not "what was tried and why it failed".
- **Fresh restart: no.** After the cap the loop only halts to a human. It never tries once more from a clean context carrying only the lessons.

The blocker the issue was parked on is gone. `escalation-outcomes` (0.5.0) gives halts a closed cause set and `gates stats --outcomes` counts them, so the effect of a restart can be measured.

## What Changes

- **Attempt notes.** `gates attempt note <task>` appends an `attempt-note` ledger row with four short fields: hypothesis, what changed, what the oracle said, and what to rule out next. `gates attempt notes <task>` prints a task's notes in order. The loop writes one after every red fix attempt, and a resuming or restarted agent reads the notes, not a transcript.
- **The cap, enforced in code.** For a task, the shim counts red `unit` and `ci` runs after the task's RED-phase run and since its last restart. Once that count reaches the budget, `gates run unit|ci` for the task refuses with exit 1. The message names the budget and the two ways forward: a fresh restart if one remains, else a halt with cause `stalled`. The count comes from the ledger, not from the `--attempt` the caller passes.
- **One fresh restart before escalation.** `gates attempt restart <task>` requires a clean tree at the last commit and records a `restart` row that resets the count; it is allowed `loop.fresh-restarts` times per task. Spawning the fresh agent is the dispatcher's job, never the implementer's (an agent can't nest one). An implementer that exhausts its budget halts with cause `stalled`, and the halt row says whether a restart remains. `tdd-apply`, or an adopter's orchestrator, re-dispatches once with only the spec, the task and the notes.
- **Declarable budget.** `loop.attempts` (default 2) and `loop.fresh-restarts` (default 1; 0 disables restarts) in `.gates.yaml`.
- **Outcomes.** `gates stats --outcomes` counts restarts, and whether the restarted attempt reached green or halted.
- **Adoption.** A `0.6.0` catalogue item offers the budget, with the defaults as the recommended answer.

## Capabilities

### New Capabilities

- `retry-budget`: attempt notes, the enforced cap, fresh restarts and the declarable budget.

### Modified Capabilities

- `escalation-record`: a `stalled` halt records whether a fresh restart remains; `--outcomes` counts restarts.

## Impact

- `bin/gates`:
  - `attempt note`, `attempt notes` and `attempt restart`;
  - the budget check in `gates run` for `unit` and `ci`;
  - the halt row's restart field;
  - `stats --outcomes`.
- `schema/gates.schema.json`: `loop.attempts`, `loop.fresh-restarts`.
- `agents/tdd-implementer.md`, `skills/tdd-apply/SKILL.md` §5e and the halt-cause table: note after each red attempt; read notes on resume; the restart is the dispatcher's.
- `adoption/catalog.json`: one item.
- SETUP, AUTOMATION, README; tests.
