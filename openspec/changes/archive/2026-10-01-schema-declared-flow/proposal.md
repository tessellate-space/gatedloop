# Proposal: schema-declared-flow

## Why

Issue #32 reports on 0.4.0's workflow packs from an adopter that already runs two
project-local schemas. It found three defects on the dispatch path and one noise
source in inspection. All four are verified in the code.

1. **The regression-first flow is gated on a name.** `tdd-apply` step 2b routes to
   the bugfix flow only when the schema is literally named `bugfix`. The README's
   recommended customisation is to fork a schema, and a fork named
   `<project>-bugfix` silently falls through to the default per-task loop. So an
   adopter can have either their own artifacts or the regression-first flow, never
   both.
2. **`has_apply` only asks whether an `apply:` key exists.** An adopter's `epic` schema
   has an `apply:` block with no `tracks`. Its instruction says "an epic is never
   implemented". Inspection reports `has_apply: true, tracks: null`, so dispatch
   sends the epic to the per-task loop. Only prose then stands between the agent and
   an invented task list, which is the exact failure the workflow-packs design (D4)
   set out to prevent.
3. **PyYAML became a hard dependency on the dispatch path, undeclared and
   unchecked.** Step 2b runs `gates schema inspect` for every change. That command
   exits without PyYAML, so on a machine without it `tdd-apply` fails at dispatch.
   `gates doctor` reports all green, and SETUP.md still says there are no third-party
   dependencies. The suggested `pip install pyyaml` is refused under Homebrew's
   PEP 668 Python.
4. **Stack-coupling flags fire on prose.** The curated tool names are matched
   anywhere in the text, so `postgres`, `keycloak` and `langfuse` written as product
   nouns in an instruction were reported as unbound tools. On a real project schema
   that was 100% noise.

## What Changes

- **The flow becomes a declared property of the schema.** A schema opts into the
  regression-first flow with a namespaced top-level key:
  `specloop: { flow: regression-first }`. OpenSpec 1.13.1 validates a schema that
  carries this key. The shipped `bugfix` pack declares it, and dispatch reads the
  declaration instead of the name, so any fork can opt in. An unknown `flow` value
  fails loud instead of falling back to the default loop.
- **"Implementable" is decided from `apply.tracks`, not from key presence.** An
  `apply:` block with no `tracks` means there is nothing to tick, so dispatch refuses
  it the same way it refuses an apply-less schema. Inspection reports the new
  `implementable` fact next to `has_apply`, and warns when an `apply` block has no
  `tracks`. The pack docs state that omitting `apply:` is the correct spelling for a
  decision-terminal schema.
- **Dispatch stops needing PyYAML.** A new `gates schema dispatch <name> --json`
  returns one route: `refuse`, `regression-first` or `per-task`. It reads only the
  top-level `apply` and `specloop` blocks. With PyYAML it parses the file normally.
  Without it, a scoped reader extracts just those two blocks and fails loud on any
  shape it does not recognise, rather than under-reading. `tdd-apply` step 2b calls
  `dispatch`. `gates schema inspect` keeps its PyYAML requirement, because it parses
  the whole file.
- **PyYAML is declared and checked.** `gates doctor` reports whether PyYAML is
  importable, as an advisory warning. The warning names what needs PyYAML (full
  schema inspection) and gives a PEP 668-aware install hint. SETUP.md and the README
  prerequisites say the same.
- **Curated tool names are flagged only in code.** A curated name counts only inside
  an inline code span or a fenced block, the same scope the command-shaped heuristic
  already uses. Prose nouns stop being findings.

## Capabilities

### Modified Capabilities

- `workflow-packs`: dispatch routes on the schema's declared flow and on whether its
  implementation phase tracks anything, never on the schema's name. The dispatch
  decision needs no third-party dependency. The coupling scan reads code, not prose.
- `onboarding`: the preflight checks for the optional dependency that full schema
  inspection needs.

## Impact

- `bin/gates`: new `schema dispatch` subcommand and a scoped block reader;
  `schema_apply_info` gains `implementable`; `scan_tool_names` restricts the curated
  half to code spans; `doctor_checks` gains a PyYAML row.
- `skills/tdd-apply/SKILL.md` step 2b and the 5-bugfix heading;
  `skills/workflow-select/SKILL.md` and `agents/schema-review.md` wherever they cite
  `has_apply`.
- `packs/bugfix/schema.yaml` gains `specloop: { flow: regression-first }`.
- README, SETUP.md and `docs/field-guide.md`: the prerequisites line, the flow key,
  and the "omit `apply:`" rule for decision-terminal schemas.
- `tests/`: the dispatch table, the scoped reader with and without PyYAML, the
  `implementable` rule, the code-only scan, and the doctor row.
- No change to gates, hooks, the ledger, or any enforcement step. Dispatch still
  decides only the route (design D1 of workflow-packs).
- Ships as 0.4.1 if released alone. The maintainer is holding the next release for
  #34, so it will more likely ride in 0.5.0.
