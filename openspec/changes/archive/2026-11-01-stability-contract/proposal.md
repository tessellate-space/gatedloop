## Why

Nothing in the repository says which of gatedloop's surfaces an adopter may build on, and nothing notices when one changes. A renamed flag, a dropped `gatedloop/<gate>` status, or a reshaped ledger row reaches adopters as an ordinary release. Today the only defence is that one maintainer remembers. The ledger is the most exposed piece. Its rows are committed into adopters' repositories and read back by `stats`, `--outcomes`, acceptance and the merge. They carry no version, so a reader cannot tell a row written by a newer plugin from a corrupt one. ci tests one Python on one OS against one OpenSpec, while the README promises Python 3.9+.

This change builds the means to keep a compatibility promise. It does not say when the project leaves 0.x, or what a 1.0 claims; those stay the maintainer's decision (`docs/status.md` "What's next"). Whatever that decision is, it needs these pieces first.

## What Changes

- Every ledger row gains a `v` field, starting at `1`. Readers treat a row without `v` as version 1, written before the field existed. A row whose `v` is newer than the reader knows fails loudly, naming the row's file and the plugin version that can read it, instead of being read with today's assumptions.
- A contract snapshot, `tests/contract.json`, records the public surface:
  - every `gates` subcommand and its flags;
  - the reserved exit codes;
  - the `gatedloop/<gate>` status contexts;
  - the `.gates.yaml` top-level keys;
  - the top-level keys of the `gates handoff --json` and `gates stats --json` documents;
  - the ledger row fields.

  A new test module, `tests/test_contract.py`, regenerates it from the code and fails on any difference. Every surface change then shows up as a reviewable diff of that file in the same PR.
- Subcommands that only the bundled hooks call are marked `internal` in the snapshot. They're still recorded, but outside the promise.
- `scripts/release status` diffs the snapshot at the latest tag against `HEAD` and reports each removal or rename as **breaking**. `cut` drafts a `### Breaking` subsection for them. `status` still never suggests `major`.
- A new page, `docs/stability.md`, says what the contract covers, what it doesn't (prompt wording, human-readable output, `internal` subcommands), and the deprecation policy:
  1. deprecate in a minor, with a warning on use;
  2. keep it for at least one further release;
  3. remove it with a `### Breaking` entry and a migration step.

  While the version is 0.x, a removal may ship in a minor. From 1.0, only in a major. `RELEASING.md` gains the procedure.
- ci gains a matrix: Ubuntu and macOS, the declared minimum Python (3.9) and the latest, and the declared OpenSpec minimum and tested maximum. A weekly scheduled job runs `ci` against OpenSpec's latest release, to give early warning without blocking anything.
- `gates doctor` warns when the installed OpenSpec is outside the declared range, instead of when it differs from one exact version.

## Capabilities

### New Capabilities

- `public-contract`: what gatedloop promises adopters it will not change without notice. This covers the recorded surface and its snapshot test, the ledger row version, the declared support range, and the deprecation policy.

### Modified Capabilities

- `plugin-release`: `status` reports contract removals since the tag as breaking, and `cut` drafts them under `### Breaking`.
- `onboarding`: `gates doctor` checks the installed OpenSpec against a declared range, not one exact version.

## Impact

- `bin/gates`:
  - `v` added to `LEDGER_ROW_FIELDS` and to `_append_ledger_row`;
  - one shared row-version check used by the five ledger readers (`_read_ledger_rows`, `_read_ledger_rows_and_skipped`, `_jsonl_objects`, `_parse_jsonl_rows`, `_ledger_rows_at`);
  - the parser built by a `_build_parser()` that `main()` and the test both call;
  - `TESTED_OPENSPEC_VERSION` replaced by `OPENSPEC_MIN` / `OPENSPEC_MAX_TESTED`.
- `tests/test_contract.py` and `tests/contract.json` are new. `scripts/release` gains the snapshot diff.
- `.github/workflows/gatedloop.yml` gains the matrix. A new `.github/workflows/openspec-latest.yml` holds the scheduled run.
- `docs/stability.md` is new. `RELEASING.md`, `docs/status.md`, `README.md` and `SETUP.md` are updated to state the range.
- Existing ledgers stay readable unchanged. No manifest key is added. An older plugin reading a row with `v` sees an extra key and ignores it, as every reader already does for unknown fields.
