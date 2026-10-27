# Tasks

## 1. The usage row and its reader

- [x] 1.1 Add `usage` to the ledger row vocabulary (`tokens`, `window`, `messages`, `source` fields in `LEDGER_ROW_FIELDS`, `usage` in `NON_GATE_EVENTS`) and the Claude Code transcript adapter per design D3, behind a fixture transcript in `tests/` that includes sidechain entries; tests cover the four token fields, a missing field, an unparsable file (`unreadable-transcript`), and sibling subagent files.
- [x] 1.2 Implement `gates usage record [--task <N.M>] [--transcript <path>]` with the window rule of design D2 and `gates usage show [--change]`; tests cover the window start (task-start vs previous usage row), zero-count second flush, `task: null` with no task start, and `no-transcript` exit 0.

## 2. The hooks write it

- [x] 2.1 `hooks/gate-commit.sh`: after `tests check` passes, pass the hook input's `transcript_path` to `usage record`; a failure of `usage record` never denies the commit. Test with a fake hook input through the existing hook test harness.
- [x] 2.2 `hooks/continue-loop.sh`: flush the task in flight (or `task: null`) before the continue decision; test that a halt followed by a stop leaves a usage row.
- [ ] 2.3 `templates/git-hooks/pre-commit`: record `source: no-transcript` per design D7; `gates hook install` reinstalls the stale copy through the existing recurring adoption item; test the template body.

## 3. Prices and stats

- [ ] 3.1 `economics.currency` and `economics.prices` in `schema/gates.schema.json` and `gates validate` per design D4; tests for shape errors and an absent block.
- [ ] 3.2 `gates stats`: tokens per task and per model, the unrecorded disclosure, `--json` `tokens` key, `--epic` rollup, per design D6; byte-identical output test with and without usage rows, and a ledger with no usage rows at all.
- [ ] 3.3 `gates stats --cost`: priced subtotal, unpriced models named, tokens-only without prices; tests.

## 4. The budget

- [ ] 4.1 `loop.token-budget` in the schema and `gates validate`; `budget` added to `HALT_CAUSES` and to `gates stats --outcomes` halts by cause; tests for the cause round trip.
- [ ] 4.2 The refusal in `cmd_run` per design D5: task-bearing `unit`/`ci` only, never `--full`, never a run with no task; message names budget, spend, the in-flight lag and the halt; tests for at-budget, below-budget, `--full`, and no-task.
- [ ] 4.3 `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md`: the cause table gains `budget` and the refusal's handling (halt, never retry); `gates stats --outcomes` playbook text in `docs/gate-economics.md` names what a budget halt points to.

## 5. Adoption and docs

- [ ] 5.1 Add the `token-budget` catalogue item per design D8 with the record-only recommended answer; test.
- [ ] 5.2 Docs: SETUP (the `usage` subcommands, `economics`, `loop.token-budget`, the sources and the lag); AUTOMATION (the budget is enforced in code; what the Stop hook now writes; counts only, never transcript text); README (the stats line); `docs/gate-economics.md` (a tokens section). `python3 scripts/release docs` exits 0.

## 6. Close

- [ ] 6.1 `gates run ci` green on the final tree; `openspec validate token-ledger --strict` passes.
