# Design

## Context

What already exists:
- **`.openspec.yaml`** carries Specloop's approval keys (`approved_by`, `approved_at`, `approved_sha`). The shim reads them through `_load`, without needing PyYAML. OpenSpec 1.14 reports unknown keys and fails `--strict` on them, except keys prefixed `x-`.
- **`check-implement`**, hooked at `git checkout -b <change>`, refuses an unapproved plan.
- **`check-archive`**, hooked at `openspec archive`, refuses a change not yet merged.
- **`gates stats --outcomes`** classifies one change's ledger into a terminal state: `merged`, `halted` or `in-progress`, plus `accepted` under an acceptance policy (`_outcomes_*`, `OUTCOME_TERMINALS`). A change is `halted` only while its latest halt row is newer than its latest `task-start` row; `ready` rows are not read.
- **A schema with no `apply` block** is decision-terminal: `gates schema dispatch` says so, and `tdd-apply` refuses it. The bundled `architecture` pack is one.

## Decisions

### D1. An epic is a change, named by its children

An epic is any change that at least one other change names. A child names it with one top-level key in its own `.openspec.yaml`:

```yaml
schema: spec-driven
x-specloop-epic: autonomous-dev
```

The `x-` prefix is the form OpenSpec 1.14 reserves for tool metadata, so the key passes `openspec validate --strict`; a bare `epic:` would fail it. The shim reads it the way it reads the approval keys, through `_load` (PyYAML when importable, `_mini_yaml` otherwise), so no PyYAML is needed.

Why not a new artifact type, directory or manifest list:
- the epic's charter is an artifact, and artifacts are OpenSpec's;
- a manifest list would put planning state in the project's gate bindings (Axis A), where it doesn't belong.

The epic change is proposed, reviewed and merged like any plan, through `/specloop:propose`. Its schema is the adopter's choice. A schema with no `apply` block is recommended, because an epic ends at its children, not at code.

### D2. Validation

`gates validate` reads every active change's `x-specloop-epic` and fails, naming the child, when:
1. the name is neither an active change nor an archived one under `openspec/changes/archive/*-<name>`;
2. the child names itself;
3. the named epic's own `.openspec.yaml` names an epic. There is one level only: a story of stories is the adopter's roadmap, not a guarantee the shim can check.

A child may name an **archived** epic only if the child is itself archived. Otherwise the epic was archived while a child was open, which D4 prevents. An old repository that predates D4 gets a validation failure naming both, not a silent pass.

### D3. An epic is never implemented

`discipline check-implement <change>` gains a check that runs first: if any active change names `<change>` as its epic, it refuses with

```
'<change>' is an epic for <child>, <child>; implement its children, not the epic
```

This holds whatever the epic's schema, because an adopter's epic schema might carry an `apply` block by accident.

### D4. An epic archives after its children

`discipline check-archive <epic>` keeps its existing merge check and adds one: every change naming `<epic>` must be archived. If any isn't, it refuses and lists each open child with its D5 state. `gate-archive.sh` already calls `check-archive`, so `/opsx:archive`, `/specloop:archive` and the archive step of `gates merge` / `record-merged` are all covered.

An epic is a plan, merged to the target when its PR merges, so the existing merge check passes on its own. The new check is the only new ordering rule.

### D5. Child states, derived

`gates epics [--json]` lists every epic, active or archived, with its children. For each child it gives:
- a state;
- tasks done of total, from `tasks.md`.

A child's state starts from the outcomes classifier's answer for its ledger, so the two views can't disagree:

| State | Holds when |
|---|---|
| `archived` | its directory is under `openspec/changes/archive/` (checked first) |
| `merged` | the classifier says `merged` or `accepted` |
| `halted` | the classifier says `halted`; the cause is shown |
| `ready` | the classifier says `in-progress` and the latest `ready` or `halt` row is `ready` |
| `implementing` | the classifier says `in-progress` and there is a `task-start` row |
| `approved` | no ledger rows of those kinds, and its `.openspec.yaml` carries an approval |
| `proposed` | none of the above |

Where the classifier answers, it wins. An epic whose children are all archived is listed as `drained`.

### D6. `gates stats --epic <name>`

The existing per-change economics, summed over the epic's children, plus one row per child:
- state;
- tasks done of total;
- gate runs and gate minutes;
- red runs;
- halts by cause.

It accepts `--json`, as `stats` does. No new math: it groups the existing report by child.

### D7. The brief

`_session_brief.py` calls `gates epics --json`, a fast read that runs no gates. Above the flat change list it prints one line per **active** epic:

```
Epic autonomous-dev: 2 archived, 1 merged, 1 implementing (lane-permissions 3/7), 1 approved
```

A child of an active epic is then omitted from the flat list. A repository with no epics prints nothing new, so its brief is byte-identical to before.

### D8. The drain, as an example

`docs/running-at-scale.md` gains "Draining an epic", a loop an orchestrator runs:
1. Read `gates epics --json`.
2. Pick the next `approved` child that the adopter's coordination check passes. That check is the adopter's own command, invoked by name only.
3. Dispatch `tdd-implementer` in its worktree, under the adopter's lane ceiling.
4. Hand each `ready` child to `merge-runner`.
5. Stop at a `halted` child, or when the epic reads `drained`.
6. Archive the epic. D4 makes that the only order that works.

It ships as an example, headed "adapt to your team" like the rest of that document, and adds no command. The manifest gains no `epics:` or `concurrency.lanes` key.

## Risks

- **An adopter wants epics nested.** D2 refuses with a clear message. Nesting can be added later; removing a guarantee is harder than adding one.
- **A child renamed after linking.** Validation fails naming the dangling epic, which is the point of D2.
