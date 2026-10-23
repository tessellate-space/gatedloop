## 1. The wait

- [x] 1.1 `_gate_lock` prints the first waiting line immediately and later lines at most every 30 s, with holder pid, liveness, hold age and wait time (design D1); tests use a fake clock and a held lock to assert line count and content
- [x] 1.2 `concurrency.max-wait-seconds` (positive integer, default 480) in `schema/gates.schema.json` and both parsers' validation; `gates run` exits 75 with the `specloop: lock busy` message and a ledger row with `precondition: "lock-busy"` when the bound is exceeded, the gate command never running (design D2); tests cover the bound and validation

## 2. Status

- [x] 2.1 `gates lock status [--json]` per design D3 (probe with a non-blocking lock, free/held, liveness, "possibly hung" after one hour, never terminating anything); tests cover free, held-alive, and free-with-stale-metadata

## 3. Git-layer parity

- [x] 3.1 `templates/git-hooks/pre-commit` runs `gates discipline check-commit` on the staged tree and prints its verdict or denial (design D4); tests cover a ledger-only commit and a planning-only commit allowed at the git layer, and a code commit without a marker denied
- [x] 3.2 Add the `git-hook-refresh` item to `adoption/catalog.json` (since 0.5.0, detector comparing the installed hook body to the template, action the `gates-init` hook-install step) if `adoption-prompts` has landed; otherwise record it as a follow-up in the final report — `adoption-prompts` had not landed (no `adoption/catalog.json`), so `git-hook-refresh` is a follow-up in the implementation report

## 4. Prompts and docs

- [x] 4.1 `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md`: the lock-busy retry rule (same command, at most three times, then `environment`), distinct from other exit-75 halts
- [x] 4.2 SETUP.md's gate contract documents the `specloop: lock busy` prefix, `max-wait-seconds`, and `gates lock status`

## 5. Close

- [x] 5.1 `gates run ci` green on the final tree; `openspec validate lock-and-ledger-hygiene --strict` passes
