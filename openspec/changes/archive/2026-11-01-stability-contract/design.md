# Design

## Context

Today nothing says what an adopter may rely on, and nothing detects a change to it:

- **Ledger rows have no version.** They have a fixed shape (`LEDGER_ROW_FIELDS`, which every row carries in full) and grow by a union rule: new fields are appended last, and absent means `None`. That keeps old rows readable by new code, but not the other way round. Five readers parse rows, and three of them drop lines they can't parse without saying so.
- **The manifest already has a version.** `gatesVersion` must be `1`, and `gates doctor` reports drift.
- **The parser is built inline in `main()`.** There are 71 subparsers, and nothing records them.
- **The bundled hooks read the shim mostly through exit codes.** The stdout they do parse comes from `hook git-cwd`, `discipline merge-scope` and `discipline check-continue`. Those subcommands ship in the same plugin as the hooks, so they can change together.
- **Installed git hooks are stubs** that delegate to `${CLAUDE_PLUGIN_ROOT}/templates/git-hooks/*`, so they always run the current plugin's copy.
- **ci covers one platform.** It runs `ubuntu-latest` with its default Python and OpenSpec pinned at 1.14.3. The README promises Python 3.9+. The shim does parse and run `validate` under 3.9.6, which was checked by hand while writing this plan, but ci never runs it.

The maintainer hasn't yet decided what 1.0 requires, or what it means (`docs/status.md` "What's next"). Nothing here depends on that decision.

## Goals / Non-Goals

**Goals:**
- make every public surface change visible in review;
- make ledger rows from a newer plugin fail loudly;
- test the environment the docs promise;
- write the deprecation policy down.

**Non-Goals:**
- declaring 1.0, or writing the readiness criteria;
- an eval suite for the prompts;
- splitting `bin/gates`;
- Windows support.

## Rejection test

Each piece is checked against the four questions in CLAUDE.md.

- **Ledger version (D1–D2):** it makes a stated guarantee enforceable. The ledger is read back as evidence by acceptance, `--outcomes` and the merge, and a misread row is false evidence. **Ours.**
- **Contract snapshot and release report (D3–D5):** this is repository tooling under `tests/` and `scripts/`, and it ships nothing. It makes the compatibility promise enforceable for the maintainer, the only party who can keep it. **Ours.**
- **The ci matrix (D6):** it makes "Python 3.9+" and the OpenSpec range enforceable, and it names no stack command, since it runs `gates run ci`. **Ours.**
- **Doctor range (D7):** it makes an existing guarantee ("probed, not assumed") honest for more than one version. **Ours.**
- **The policy page (D8):** documentation of the above. It authors no artifact for an adopter. **Ours.**

## Decisions

### D1. The ledger row version is `v`, starting at 1

- **The field.** `v` is added to `LEDGER_ROW_FIELDS`, appended last under the union rule. `_append_ledger_row` sets it, as it already does for `session`, so no caller can omit or forge it.
- **The constant.** `LEDGER_ROW_VERSION = 1` is the highest version this shim writes and reads.
- **Why 1, and why old rows count as 1.** Every row written so far has the full fixed shape. A row without `v` is therefore exactly a version-1 row, and starting at 1 spends no migration on existing ledgers.
- **When to bump.** Only when a row's meaning changes, meaning a field is renamed or removed, or a value is reinterpreted. Appending a field under the union rule stays at the same version, because old readers already ignore unknown keys.
- **The name.** It is short because it is on every row of every committed ledger. It is distinct from `gatesVersion`, which versions the manifest.

### D2. One row check, used by every reader

`_ledger_row_ok(obj, path)` returns the row if it is readable. If its `v` is an integer greater than `LEDGER_ROW_VERSION`, it exits 1 with this message:

> gatedloop: `<path>` holds a ledger row of version `<v>`; this plugin reads up to `<N>`. Update the plugin (a teammate's newer gatedloop wrote it).

A `v` that isn't an integer is treated as an unreadable line, exactly as each reader treats malformed JSON today. The five readers each call the check where they currently test `isinstance(obj, dict)`:
- `_read_ledger_rows`
- `_read_ledger_rows_and_skipped`
- `_jsonl_objects`
- `_parse_jsonl_rows`
- `_ledger_rows_at`, which goes through `_parse_jsonl_rows`

Alternatives considered:
- *Skip newer rows with a warning.* Rejected: a skipped accept row or merge row reads as "never happened", which is the silent wrong answer `fail-loud-gates` forbids.
- *Version the file instead of each row.* Rejected: ledgers are append-only and merged line by line, so a file header would conflict on every merge.

### D3. The snapshot is generated, checked in, and compared

- **The parser.** `main()`'s parser construction moves into `_build_parser()` unchanged. The test imports the shim the way `tests/_plan_fixture.py` already does.
- **The generator.** `tests/test_contract.py` builds the snapshot from:
  - `_build_parser()`, walked recursively over `_SubParsersAction`, recording each subcommand path, its option strings and its positionals;
  - `PRECONDITION_EXIT_CODE` plus the fixed `0`/`1`/`2`;
  - every context `gates marker publish` can post (`STATUS_CONTEXT_PREFIX` plus each gate it accepts, `tests` included);
  - the schema's `properties` keys;
  - `LEDGER_ROW_FIELDS` and `LEDGER_ROW_VERSION`;
  - the top-level keys of `gates handoff --json` and `gates stats --json`, each run in a fixture repository built with the existing fixtures.
- **The comparison.** The generated snapshot is compared with `tests/contract.json`. On a difference, the test prints a unified diff and the rewrite command, `python3 tests/test_contract.py --write`.
- **Formatting.** The file is sorted, indented JSON, so a diff reads as a list of surface changes.

Only those two `--json` documents are pinned. `handoff` is the payload one session sends another, and `stats` is the one adopters script. The other `--json` outputs are deferred; see Deferred.

### D4. `internal` is a recorded mark, not a guess

The snapshot marks a subcommand `internal` when it is listed in `CONTRACT_INTERNAL` in the test module. Each entry carries a one-line reason, as `DOCS_EXEMPT` does in `scripts/release`. The starting list:
- `discipline`, `gate-marker`, `hook git-cwd`, `taint` and `audit`, which only bundled hooks call;
- `ledger record-merge`, which only a bundled skill calls.

Adding an entry is a reviewed edit, the same as for `DOCS_EXEMPT`. Inferring the mark from which files mention a subcommand was rejected: a prompt mention would make it public, and a doc mention would hide that only hooks call it.

### D5. `scripts/release` reports removals; the level stays the maintainer's

- **`status`.** It reads `tests/contract.json` at the tag (`git show <tag>:tests/contract.json`) and at `HEAD`. It reports each removed public entry, and a raised `ledger_row_version`, under `breaking`. If the tag has no snapshot, it prints "contract comparison skipped: the tag has no snapshot".
- **`cut`.** Its drafted section gains `### Breaking` with one `- <entry>: <migration>` line per item, the migration left as `TODO`.
- **`publish`.** It refuses while a `TODO` remains in the section. This is the only new refusal.
- **Unchanged.** "`status` never suggests `major`" stays: the policy (D8) decides whether a removal needs a major release, and the maintainer chooses the level.

### D6. The ci matrix declares what the docs promise

- **The `ci` job's matrix.** `os: [ubuntu-latest, macos-latest]` × `python: ['3.9', '3.13']` × `openspec: [<min>, <max-tested>]`, with Python installed through `actions/setup-python`.
- **The starting range.** It is `1.14.3`–`1.14.3`, the one version verified. The matrix then collapses to the OS and Python legs until the range widens. A widening is a one-line edit to the two constants, plus the matrix entry that proves it.
- **Statuses.** Only the `ubuntu-latest` / latest-Python / max-tested leg publishes the `gatedloop/ci` and `gatedloop/tests` statuses. Branch protection keeps reading one context, and the other legs fail the workflow run. **Open for review:** making every leg required would need one status context per leg.
- **The scheduled run.** `.github/workflows/openspec-latest.yml` runs weekly on `main`. It installs `@fission-ai/openspec@latest` and runs `gates run ci` and `gates doctor`. It publishes no status, and a failure shows as a red scheduled run.
- **The stated values.** The minimum Python stays 3.9, which the README and SETUP already state. If the 3.9 leg finds a construct that 3.9 can't run, raising the minimum is a separate, deliberate change, never a quiet doc edit.
- **OS support.** It is stated as macOS and Linux. Windows is unsupported because the hooks are bash.

### D7. The doctor compares against a range

`TESTED_OPENSPEC_VERSION` becomes `OPENSPEC_MIN` and `OPENSPEC_MAX_TESTED`, both `"1.14.3"` to start. The doctor's check parses `openspec --version` into a tuple of integers:
- inside the range: no warning;
- outside it: the existing warning, naming the range;
- unparseable: the existing warning, unchanged.

It stays a warning (onboarding D4: a pre-1.0 CLI's drift is informative, not conclusive). The test module asserts that the two constants equal the values in `docs/stability.md`, so the page and the code can't drift.

### D8. `docs/stability.md` writes down the contract and the policy

The page covers:
- what is covered: the snapshot, the `tasks.md` oracle-tag and marker syntax, and the `x-gatedloop-*` keys;
- what isn't covered (the spec lists it);
- the deprecation steps;
- the 0.x clause: while the version is 0.x, a removal may ship in a minor;
- the 1.0 clause: from 1.0, only in a major.

It doesn't say when 1.0 comes. It links to `docs/status.md`'s "What's next" for that, and that section is left as the maintainer wrote it.

`RELEASING.md` gains a "Breaking changes" section: deprecate with a warning, keep for one release, then remove under `### Breaking` with a migration step. `README.md` and `SETUP.md` state the supported range, and `docs/status.md`'s "Upstream coupling" names the range instead of one version.

## Deferred

- **Freezing every `--json` document's shape.** There are 18 `--json` flags, and most of them are diagnostic. Pinning their keys now would make the snapshot noisy before anyone scripts them. They can be added one at a time when an adopter depends on one.
- **Freezing human-readable output.** The bundled hooks parse only `internal` subcommands' output, which ships with them, so no human-readable line is an adopter contract. Freezing them would block wording fixes for no reader.
- **Prompt evals.** A separate change. The prompts' oracle is a different problem from the shim's contract.
- **Windows.** Out of scope while the hooks are bash.
- **Readiness criteria for 1.0.** The maintainer's decision. This change only gives that decision something to point at.

## Risks / Trade-offs

- **The snapshot test fails on every surface addition.** That is intended, because no surface should enter unreviewed, but it adds one regenerate step to feature PRs. The failure message prints the command, so the step costs one line.
- **A matrix multiplies ci minutes, and macOS minutes cost more.** Every leg runs the parallel suite of about 3 minutes, against about 13 minutes serially.
- **The `v` check turns an old plugin's silent misread into a hard stop** for a mixed-version team. That is the point, and the message says how to fix it.

## Migration

Nothing for adopters. Existing ledgers read as version 1. A plugin from before this change reads a row with `v` and ignores the extra key.
