# Design: schema-declared-flow

## Context

Workflow-packs design D1 says dispatch decides the route and never the loop body. D4
says the implementation-phase fact is resolved in code, never inferred from
`openspec instructions apply`. Both still hold. What #32 shows is that the route was
decided on the wrong facts: a schema's name, and whether an `apply:` key exists. It
also shows that deciding it needed a dependency the prerequisites do not list.

## Decisions

### D1. The flow is declared under a namespaced top-level key

```yaml
specloop:
  flow: regression-first
```

The declaration goes in a top-level `specloop:` block, not in `apply:`, for two reasons.
First, `apply` belongs to OpenSpec. A key like `apply.mode` could collide with a future
upstream field, or be rejected by a stricter validator. Second, a namespaced block says
whose key it is to anyone reading the schema. OpenSpec 1.13.1 accepts both spellings
(`openspec schema validate` passes); checked on a copy of the `bugfix` pack before
this proposal was written.

The known flows are `per-task`, which is the default when nothing is declared, and
`regression-first`. The list is closed and lives in `bin/gates`. An unknown value exits
non-zero naming the known values (fail-loud-gates). Falling back to `per-task` would
repeat the silent fall-through #32 reported.

The rejection test: this makes a stated guarantee enforceable ("a bugfix's repro runs
red first"), for every schema that asks for it. It authors no artifact and names no
stack command.

### D2. Implementable means `apply` with a non-empty `tracks`

| Schema shape | `has_apply` | `implementable` | Route |
|---|---|---|---|
| no `apply:` | false | false | refuse |
| `apply:` without `tracks` | true | false | refuse |
| `apply:` with `tracks` | true | true | declared flow, else `per-task` |

`has_apply` stays in the inspect report, unchanged in meaning, because
`agents/schema-review.md` and existing adopter scripts read it. Dispatch reads
`implementable`. An `apply:` block without `tracks` is refused rather than routed with a
warning. With nothing to tick, the per-task loop's resumability (done ⟺ committed, read
from the tracked file) has nothing to stand on, and the adopter's own instruction ("an
epic is never implemented") already says the same thing in prose.

A flow declared on a non-implementable schema is ignored in favour of `refuse`, and
inspection reports the contradiction.

### D3. `gates schema dispatch` is the one call step 2b makes

`gates schema dispatch <name> [--path DIR] --json` prints:

```json
{"schema": "…", "route": "refuse|per-task|regression-first", "reason": "…",
 "has_apply": true, "implementable": true, "flow": "regression-first"}
```

It exits 0 for every successful decision, `refuse` included. The route is data, and the
skill acts on it. It exits non-zero only when it cannot decide: the schema doesn't
resolve, there's an unknown flow, or the reader failed. Schema resolution is the same
`openspec schema which` call `inspect` makes, and it is factored out and shared.

Keeping `dispatch` separate from `inspect` means dispatch does not inherit `inspect`'s
PyYAML requirement or its tool-name scan, which step 2b never needed.

### D4. A scoped reader for the two blocks dispatch needs

Where PyYAML is importable, `dispatch` uses it. Otherwise it uses a reader scoped to
exactly two top-level blocks, `apply` and `specloop`, and it never parses anything
else. The reader works like this:

- A block starts at a line matching `^(apply|specloop):\s*(#.*)?$` at column 0. Any
  other column-0 key, or end of file, ends it. Folded and literal scalars elsewhere in
  the file are indented, so they can't open or close a block.
- Inside a block, a child key is one at the block's first child indent. Lines indented
  deeper belong to a child's value and are skipped. That's how `instruction: |` and a
  `requires:` list are passed over without being read.
- The only values read are `apply.tracks` and `specloop.flow`, as plain scalars. They
  may be quoted with single or double quotes, and may carry a trailing comment.
- Anything else fails loud with a message naming the line and suggesting PyYAML. That
  covers a flow mapping (`apply: {tracks: x}`), an anchor or alias, a block scalar
  indicator on `tracks` or `flow`, a tab indent, or a top-level key repeated.

This is the `inspect` rationale again: the built-in parser must never under-read
silently. The difference is scope. `inspect` needs the whole file, so it still requires
PyYAML. `dispatch` needs two scalars, so a reader that refuses what it doesn't
recognise is enough. The reader is tested on the shipped packs, on the bundled
`spec-driven` schema's shape, and on the #32 `epic` shape, each with PyYAML hidden. The
results must equal the PyYAML path.

### D5. Doctor reports PyYAML as advisory, with a PEP 668-aware hint

This adds one row to `doctor_checks`, `ok` or `WARN`. The warning text:

> PyYAML not importable — `gates schema inspect` needs it; the loop, hooks and
> `gates schema dispatch` do not. Install with `python3 -m pip install --user pyyaml`,
> or `pipx`/`uv` if your Python is externally managed (PEP 668).

`doctor` stays exit 0 either way. SETUP.md and the README's prerequisite line change
from "no third-party deps" to "no required third-party deps; PyYAML is optional and
enables full schema inspection".

### D6. Curated tool names are matched only inside code

`scan_tool_names` applies the curated list to the extracted code spans and fenced
blocks, the same text the command-shaped heuristic already reads, instead of the whole
lowered text. This drops the prose-noun noise #32 reported (`postgres`, `keycloak`,
`langfuse` as product components).

It also means a pack whose prose tells the reader to run a named tool, without backticks,
is no longer flagged. That tradeoff is acceptable: the scan is advisory (workflow-packs
D8), and the shipped-pack coupling audit is a separate grep test over pack files, which
this change does not touch.

## Risks

- **A future OpenSpec rejects unknown top-level keys.** Then the declaration breaks
  `openspec schema validate` for any schema that opted in. The mitigation is loud and
  local: the pack's own validation test fails in this repo's `ci` on the next OpenSpec
  bump. The fallback is a documented sidecar file (`specloop.yaml` beside
  `schema.yaml`). It is not built now.
- **The scoped reader drifts from YAML semantics.** The reader only has to handle two
  scalars and refuse everything else, and D4's tests require parity with PyYAML.

## Out of scope

- #33's hook, lock and ledger items (separate groups, separate changes).
- Any change to the `architecture` pack's contents. #32 questions its marginal value;
  that's a positioning question, not a defect.
