# Tasks: gates-stats

## 1. Aggregation core (pure, testable)

- [x] 1.1 Add the non-gate event denylist constant and a `stats_from_rows(rows, idle_gap_ms)` pure function in `bin/gates` implementing design D1 (gate time, failed attempts, active loop time with idle-gap exclusion and last-row duration term, per-task + unattributed buckets, event counts, data-quality counts); verify with a new stdlib-only `tests/test_stats.py` covering: gate vs. event row classification, failed-attempt counting, idle-gap exclusion, the slow-gate no-double-count sequence (design Risks), per-task attribution by interval-ending row, and the unattributed bucket.
- [x] 1.2 Make skipped ledger lines countable: add a row-reading path that returns (rows, skipped_count) without changing `_read_ledger_rows`'s existing callers (audit/taint untouched); verify tests cover a ledger mixing valid rows, a non-JSON line, a JSON non-object line, and a row with unusable `ts` — all counted, none fatal — and that the existing test suite still passes (`python3 -m unittest discover -s tests`).
- [x] 1.3 Pin era tolerance: tests feed rows with an extra `scope` field and rows missing optional fields (`duration_ms: null`, `task: null`, absent `attempt`) through `stats_from_rows` and verify normal aggregation with degraded contributions per design D4.

## 2. CLI surface

- [x] 2.1 Implement `cmd_stats` + argparse wiring (`gates stats [--change <name>] [--all] [--json] [--idle-gap <minutes>]`): scope resolution via `_resolve_change_name`, `--all` globbing `.specloop/runs/*.jsonl` sorted by filename, fail-loud non-zero exits naming the missing path/branch for no-ledger, empty `--all`, and main-with-no-change cases; verify with tests running the command against temp directories for each fail-loud case and the single-change happy path.
- [x] 2.2 Implement the human table formatter per design D3 (header, per-gate table, per-task table with `(unattributed)`, data-quality line, limitations sentence, closing pointer to `docs/gate-economics.md`, idle threshold disclosed); verify a test asserts each required *section* is present in output (not exact column cosmetics).
- [x] 2.3 Implement `--json` mode emitting exactly one document in the design D3 schema (raw ms and 0–1 shares, `changes[]` uniform for single and `--all`, `totals`, `idle_gap_ms`); verify tests parse the output with `json.loads`, assert the documented keys and types, and assert byte-identical output across two runs on the same fixture (determinism).

## 3. Playbook doc

- [x] 3.1 Write `docs/gate-economics.md` (~1 page): the five principles as gate shapes per design D5, pointing at SETUP.md's scoped-oracle contract for the fast/full split and naming the machine-level lock as out of scope here; verify no project-specific tool name appears (stack-agnostic-prompts) and the file renders as a standalone read.
- [x] 3.2 Link the playbook from `SETUP.md` with a one-paragraph pointer (when gates feel slow: run `gates stats`, then read the playbook); verify the link path is correct and `./bin/gates run ci` stays green.

## 4. Close the loop

- [x] 4.1 Run the full suite plus `./bin/gates validate` and `./bin/gates run ci`; verify green, and manually run `gates stats` against this repo's own `.specloop/runs/` ledgers as a smoke test of real-era rows.
