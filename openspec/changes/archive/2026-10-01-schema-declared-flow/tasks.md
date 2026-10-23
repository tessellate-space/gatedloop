## 1. Implementable and declared flow (pure functions)

- [x] 1.1 `schema_apply_info` returns `implementable` (true only when `apply` is present with a non-empty `tracks`); `has_apply` keeps its meaning (design D2)
- [x] 1.2 A pure `schema_flow(data)` returns the declared `specloop.flow`, defaulting to `per-task`, and raises a fail-loud error naming the known flows on any other value (design D1)
- [x] 1.3 A pure `dispatch_route(data)` implements the design D2 table: not implementable → `refuse`; implementable → the declared flow; a flow declared on a non-implementable schema → `refuse` with that contradiction in `reason`
- [x] 1.4 `inspect_schema_data` reports `implementable` and `flow`, and a warning when `apply` has no `tracks` or when a flow is declared on a non-implementable schema; the human-readable output prints both and states that omitting `apply` is the correct spelling for a decision-terminal schema

## 2. Scoped reader (no PyYAML)

- [x] 2.1 A pure `read_dispatch_blocks(text)` extracts `apply.tracks`, the presence of `apply`, and `specloop.flow` from raw schema text per design D4 (column-0 block boundaries, first-child indent, deeper lines skipped, quoted scalars and trailing comments)
- [x] 2.2 It fails loud, naming the line, on every unrecognised shape listed in design D4: flow mapping, anchor or alias, block-scalar indicator on a read key, tab indent, and a repeated top-level key
- [x] 2.3 Parity tests: for `packs/bugfix`, `packs/architecture`, a `spec-driven`-shaped fixture, and the #32 `epic` shape (an `apply` with `requires` and a multi-line `instruction` but no `tracks`), the scoped reader and the PyYAML path produce the same `dispatch_route`

## 3. `gates schema dispatch`

- [x] 3.1 Factor schema-name resolution (`openspec schema which <name> --json`, and `--path`) out of `cmd_schema_inspect` into a shared helper both subcommands use
- [x] 3.2 Add `gates schema dispatch <name> [--path DIR] [--json]`, which uses PyYAML if importable and the scoped reader otherwise, prints the design D3 object, exits 0 for every decided route including `refuse`, and exits non-zero only when it cannot decide
- [x] 3.3 Test the subcommand end-to-end with PyYAML hidden from import, against a temporary project holding a forked regression-first schema under a different name, and against an `apply`-without-`tracks` schema

## 4. Packs and the dispatch prompt

- [x] 4.1 `packs/bugfix/schema.yaml` declares `specloop: { flow: regression-first }`; a test asserts it still passes `openspec schema validate` when OpenSpec is on PATH, and skips with a stated reason otherwise
- [x] 4.2 Rewrite `skills/tdd-apply/SKILL.md` step 2b to call `gates schema dispatch <schema-name> --json` and branch on `route` only; retitle 5-bugfix as the regression-first route and remove every name-based check; state that a non-zero exit is a HALT (cause `environment` or `other`), never a fallback to the default loop
- [x] 4.3 Update `skills/workflow-select/SKILL.md` and `agents/schema-review.md` wherever they cite `has_apply`, so they read `implementable` and mention the declared flow

## 5. Coupling scan reads code only

- [x] 5.1 `scan_tool_names` matches the curated list only inside extracted code spans and fenced blocks (design D6); tests cover a curated name in prose (not flagged), in an inline span (flagged), and in a fence (flagged)
- [x] 5.2 Confirm the existing shipped-pack coupling audit test is unchanged and still green

## 6. Doctor and docs

- [x] 6.1 `doctor_checks` gains a PyYAML row: `ok` when importable, `WARN` otherwise, with the design D5 text; `doctor` still exits 0; tests cover both states
- [x] 6.2 SETUP.md and README prerequisites say PyYAML is optional and name what it enables; SETUP.md's packs section and `docs/field-guide.md` document `specloop.flow`, the known flows, and "omit `apply:` for a decision-terminal schema"

## 7. Close

- [x] 7.1 `gates run ci` green on the final tree; `openspec validate schema-declared-flow --strict` passes
