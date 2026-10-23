# Proposal

## Why

The 2026-10-22 competitive survey found one thing every loop runner in the field reports and this plugin cannot: what a task cost. The durable ledger records `duration_ms` and nothing else about spend, and the `gate-economics` spec lists "token cost" among the things the ledger cannot answer. A team deciding whether the loop pays for itself, or which change burned the month's budget, reads a billing page instead of the ledger that already holds everything else about the run. The host writes per-message token usage next to the session, and the plugin's hooks already receive that transcript's path, so the gap is a reader, not a missing source.

## What Changes

- **Usage rows.** A new `usage` ledger row records, per task, the tokens the host session spent on it: input, output, cache-read and cache-write, broken down by model, with the window it covers. The plugin's commit hook writes one at every gated commit, and its Stop hook flushes one for the task in flight, so a halted or abandoned task is costed too. Only counts are stored, never transcript content.
- **A host-agnostic shape.** The row names its source. One reader exists today (the Claude Code transcript); a session with no readable transcript, such as a human's or another host's, records null counts with the reason, never a failure.
- **Stats.** `gates stats` gains tokens per task and per change, discloses what was unrecorded, and `--epic` rolls tokens up. `gate-economics`'s "cannot answer token cost" disclaimer is retired.
- **Prices are a binding.** An optional `economics.prices` block in `.gates.yaml` maps a model name to per-million-token prices; `gates stats --cost` multiplies and prints a currency figure. Without prices, stats print tokens and say so. The shim never ships a price list.
- **A token budget, enforced in code.** Optional `loop.token-budget` caps a change's recorded tokens. Once recorded usage reaches it, task-bearing `gates run unit|ci` refuses with exit 1, naming the budget, the spend and the halt to record. A new closed halt cause `budget` joins the escalation set, and `gates stats --outcomes` counts it.
- **Adoption.** One catalogue item offers the budget, with "record only, no budget" as the recommended answer.

## Capabilities

### New Capabilities

- `token-accounting`: usage rows, their window and sources, the price binding, and the token budget.

### Modified Capabilities

- `gate-economics`: `gates stats` reports tokens and no longer lists token cost as unanswerable.
- `escalation-record`: the closed cause set gains `budget`.

## Impact

- `bin/gates`: `usage record` and `usage show`; the transcript reader; the budget check in `gates run`; `stats` tokens and `--cost`; `stats --outcomes` and `--epic`.
- `hooks/gate-commit.sh`, `hooks/continue-loop.sh`, `templates/git-hooks/pre-commit`: pass the transcript path through to `usage record`.
- `schema/gates.schema.json`: `loop.token-budget`, `economics.prices`.
- `agents/tdd-implementer.md`, `skills/tdd-apply/SKILL.md`: the `budget` halt cause in the cause table.
- `adoption/catalog.json`: one item.
- README, SETUP, AUTOMATION, `docs/gate-economics.md`; tests.

Rejection test: authors no artifact; names no stack command (a model name in `economics.prices` is the adopter's binding, like a gate body); makes a stopping rule enforceable; makes the loop's economics measurable without leaving the ledger.
