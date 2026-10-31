# Tasks

## 1. The ledger row version (D1, D2)

- [x] 1.1 Add `v` to `LEDGER_ROW_FIELDS` and `LEDGER_ROW_VERSION = 1`, and make `_append_ledger_row` set `v` itself. Verify with tests that every appended row kind carries `"v": 1` and that a `v` passed by the caller is overwritten [oracle: unit]
- [x] 1.2 Add `_ledger_row_ok` and call it from `_read_ledger_rows`, `_read_ledger_rows_and_skipped`, `_jsonl_objects` and `_parse_jsonl_rows`. Verify with tests that a ledger with no `v` reads unchanged in `gates stats`; that a `v: 2` row makes `gates stats`, `gates acceptance check` and `gates merge` exit 1 with a message naming the file and both versions, and `gates merge` writes no merge row; that a non-integer `v` counts as an unreadable line; and that a committed `v: 2` row read through `_ledger_rows_at` is refused the same way [oracle: unit]

## 2. The contract snapshot (D3, D4)

- [x] 2.1 Move the parser construction in `main()` into `_build_parser()`, with no change in behaviour. Verify that `gates --help` and every subcommand's `--help` print the same text before and after [oracle: unit characterization]
- [ ] 2.2 Add `tests/test_contract.py` with the generator, `CONTRACT_INTERNAL` and its reasons, and the `--write` mode, plus the generated `tests/contract.json`. Verify with tests that a renamed flag, an added subcommand, a removed status context and a removed ledger field each fail with a diff naming them, and that `--write` makes the test pass again [oracle: unit]

## 3. Release reporting (D5)

- [ ] 3.1 Make `scripts/release status` diff the snapshot at the tag against `HEAD`. It reports public removals and a raised row version under `breaking`, in text and in `--json`, and prints a note that the comparison was skipped when the tag has no snapshot. Make `cut` draft `### Breaking` with `TODO` migrations, and make `publish` refuse while a `TODO` remains. Verify with tests for a removed flag, additions only, a removed `internal` subcommand, a tag with no snapshot, and `publish` refusing a `TODO` before its first write [oracle: unit]

## 4. The supported environment (D6, D7)

- [ ] 4.1 Replace `TESTED_OPENSPEC_VERSION` with `OPENSPEC_MIN` and `OPENSPEC_MAX_TESTED`, and make the doctor compare the installed version against that range. Verify with tests for a version inside the range, above it, below it, and one that can't be parsed [oracle: unit]
- [ ] 4.2 Add the OS × Python × OpenSpec matrix to the `ci` job in `.github/workflows/gatedloop.yml`, with only the primary leg publishing statuses. Add `.github/workflows/openspec-latest.yml`, a weekly run against the latest OpenSpec that publishes no status. Verify on the implementation PR that every leg runs and only one posts `gatedloop/ci` [oracle: none]

## 5. The policy and the docs (D8)

- [ ] 5.1 Write `docs/stability.md`, add RELEASING.md's "Breaking changes" section, and state the supported range in README.md, SETUP.md and the "Upstream coupling" section of `docs/status.md`, leaving "What's next" as it is. Add the test in `tests/test_contract.py` asserting that `OPENSPEC_MIN`/`OPENSPEC_MAX_TESTED` match `docs/stability.md`. Verify that `scripts/release docs` reports no gap, `openspec validate stability-contract --strict` passes and `gates run ci` is green [oracle: unit]
