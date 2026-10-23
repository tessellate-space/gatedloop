## 1. Not run is not red

- [x] 1.1 Treat exit 75 at merge steps 3 and 5 per design D1: restore, commit nothing, exit 75, and print a message naming the holder or the precondition. Check `merge-runner` and tdd-apply 7.5's wording on 75. Tests use the merge fixture to cover a held `ci` lock past its bound, a failed precondition, and red keeping today's message

## 2. Merge priority

- [x] 2.1 Add the priority claim per design D2: written while a merge waits, honoured by other waiters, ignored and removed when its pid is dead, and shown by `gates lock status`. Tests use a scripted holder and two waiters, and assert the order. They also cover a stale claim
- [x] 2.2 Add `concurrency.merge-wait-seconds` to the schema, `gates validate` and the merge's wait (design D3); tests

## 3. The checkpoint

- [x] 3.1 `commands/gates-init.md` step 9 writes `ask: ["Bash(gates merge *)"]` with design D4's reasoning
- [x] 3.2 Add the doctor row `merge-checkpoint`, the `file-contains` detector kind and the recurring `merge-checkpoint` catalogue item, since 0.6.0 (design D5). Tests cover each

## 4. Docs

- [x] 4.1 Docs:
  - SETUP: the merge exit-code table gains 75 at steps 3 and 5; lock priority and `merge-wait-seconds`; the scaffolding's new `ask` and why;
  - AUTOMATION: the human-checkpoint row.

  `python3 scripts/release docs` exits 0.

## 5. Close

- [x] 5.1 `gates run ci` green on the final tree; `openspec validate merge-lane-friction --strict` passes
