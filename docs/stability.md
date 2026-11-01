# Stability

What an adopter of gatedloop can rely on across versions, and how a part of it is
retired. When gatedloop reaches 1.0 is not decided here; [`status.md`](./status.md)'s
"What's next" says what it waits on.

## Supported environment

- **OpenSpec CLI:** `1.14.3` (minimum) to `1.14.3` (highest tested)
- **Python:** 3.9 or later
- **Operating systems:** macOS and Linux

Windows is not supported: the hooks are bash.

Pull-request ci runs `gates run ci` on each of these: both operating systems, the
minimum and the latest Python, and both ends of the OpenSpec range. A weekly job runs
the same `ci` against OpenSpec's latest release, outside the range, as an early
warning. It is not a required check. `gates doctor` warns, without failing, when the
installed OpenSpec is outside the range. The range widens when ci proves a new end;
`OPENSPEC_MIN` and `OPENSPEC_MAX_TESTED` in `bin/gates` and the line above change
together, and a test fails if they don't.

## What the contract covers

The contract is recorded in [`tests/contract.json`](../tests/contract.json), and ci
fails when the code and that file disagree, so no change to it lands unreviewed:

- every public `gates` subcommand, with its flags and positionals;
- the exit codes, including `75` for a failed precondition and `gates merge`'s
  per-step codes;
- the `gatedloop/<gate>` commit status contexts;
- the top-level keys of `.gates.yaml`;
- the top-level keys of `gates handoff --json` and `gates stats --json`;
- the ledger row fields, and the row version `v`.

Three things outside that file are covered too: the `tasks.md` oracle tag syntax
(`[oracle: <gate>]`, `[oracle: <gate> characterization]`, `[oracle: none]`), the
`NO-TESTS` and `CHARACTERIZATION` markers, and the `x-gatedloop-*` keys in
`.openspec.yaml`.

### Ledger rows

Every ledger row carries `v`, its row version, starting at `1`. A row without `v` was
written before the field existed and reads as version 1. A plugin that finds a row
newer than it knows refuses with exit 1, naming the file and both versions, and never
skips the row or reads it as an older one. Adding a field keeps the version; renaming
or removing one, or changing what a value means, raises it.

## What it does not cover

- a prompt's wording, or what a prompt makes a model do;
- a human-readable line the shim prints (the bundled hooks read exit codes, and the
  few outputs they parse come from `internal` subcommands that ship with them);
- an `internal` subcommand: one the bundled hooks or skills call, listed with its
  reason in `tests/test_contract.py`;
- any `--json` document other than `handoff` and `stats`.

These change without a deprecation.

## Deprecation policy

1. A covered surface is **deprecated with a warning** on use, naming its replacement.
2. It is kept for **at least one further release**.
3. It is removed under a `### Breaking` entry in `CHANGELOG.md`, with a **migration
   step** for each removal.

`scripts/release status` lists each public entry removed from `tests/contract.json`
since the latest tag, and a raised row version, as breaking. `cut` drafts the
`### Breaking` entries, and `publish` refuses while one still lacks its migration step.

While the version is 0.x, a removal may ship in a minor release. From 1.0, a removal
may ship only in a major release.
