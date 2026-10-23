## 1. Budget and count

- [x] 1.1 `loop.attempts` and `loop.fresh-restarts` in `schema/gates.schema.json` and `gates validate` (design D5): defaults, non-negative integers, a warning on `attempts: 0`; tests
- [x] 1.2 The failed-attempt count from the ledger per design D1, and the refusal in `gates run unit|ci` per design D2. Tests cover:
  - the RED run not counting;
  - exit 75 not counting;
  - a green run not resetting the count;
  - a wrong `--attempt` value;
  - a run with no task;
  - the message with and without a restart remaining.

## 2. Notes and restarts

- [x] 2.1 `gates attempt note` and `gates attempt notes` per design D3, with field validation and `--json`; tests
- [x] 2.2 `gates attempt restart` per design D4: refuses on a dirty tree or when no restart remains, and otherwise resets the count. The `stalled` halt row gets `restart_available`. Tests
- [x] 2.3 `gates stats --outcomes` counts `restarts` and `restart-recovered` (design D6), never as interventions; tests

## 3. The loop

- [x] 3.1 Update `skills/tdd-apply/SKILL.md`:
  - §5e: write a note after each failed attempt, and the budget replaces the "2 fix attempts" prose;
  - on resume, read `gates attempt notes`;
  - on a `stalled` halt with `restart_available: true`, dispatch one fresh implementer whose brief holds only the spec, the task and the notes.
- [x] 3.2 Update `agents/tdd-implementer.md`:
  - write notes after each failed attempt, and read them on resume;
  - on a refusal, halt `stalled` and never restart itself;
  - a fresh dispatch's first act is `gates attempt restart`;
  - the halt-cause table row updated.

## 4. Adoption and docs

- [x] 4.1 Add the `retry-budget` catalogue item, `since: 0.6.0`, per design D7; test
- [x] 4.2 Docs:
  - SETUP: the budget keys, the `attempt` subcommands, and what refuses and why;
  - AUTOMATION: the cap is now enforced in code;
  - README: the loop description.

  `python3 scripts/release docs` exits 0.

## 5. Close

- [x] 5.1 `gates run ci` green on the final tree; `openspec validate retry-budget --strict` passes
