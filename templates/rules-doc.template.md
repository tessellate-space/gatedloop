# Project conventions

The convention-review gate resolves each `rules:` id from your `.gates.yaml`
surfaces against this document. Give every rule a stable id (the `### <id>`
heading) so a surface can reference it and a finding can cite it.

Keep rules literal and checkable — the reviewer applies them to a diff, it does
not re-derive your architecture.

> This file, **not** `openspec/config.yaml`, is the rules-doc — point
> `conventions.rules-doc` here. `openspec/config.yaml`'s own `rules:` key
> expects a mapping of artifact id → array of strings, which is a different,
> incompatible shape; using it as a hand-written rules-doc is what silently
> disabled convention review on the project this template ships from.
>
> If your project uses OpenSpec, you don't have to keep the two in sync by
> hand: give a rule an `Applies to: <artifact-id>` line (in addition to
> `Rule: <one-line statement>`, both shown below) naming the artifact step it
> constrains — `proposal`, `specs`, `design`, `tasks`, or `code` for a
> review-only rule with no artifact-authoring counterpart, or `tests` for a
> rule about how this project writes tests (the test author and the reviewer
> both read those, for every change) — then run `gates
> conventions sync` to regenerate `openspec/config.yaml`'s `rules:` block from
> this file. `gates validate` fails loudly if the two drift apart.

### example-layering
Applies to: code
Rule: HTTP handlers never touch the database directly.

Describe a concrete, checkable layering rule. e.g. "HTTP handlers never touch
the database directly — they delegate to a service layer."

### example-naming
Applies to: code
Rule: Follow the project's established naming convention.

Describe a naming/consistency rule the reviewer can apply line-by-line.

### example-ui
Applies to: code
Rule: Follow the project's established UI/component conventions.

Describe a UI/component rule, if the project has a frontend surface.

### example-tests
Applies to: tests
Rule: Put each module's tests beside it in the project's test tree, built on the shared fixtures.

Describe how this project writes tests: where they live and how they are named,
which shared fixtures and factories to build on (by path), what may be faked and
what must be real, and which layer owns which behaviour. The test author reads
this before writing a change's tests; convention review holds every test to it.

### task-oracle-tags
Applies to: tasks
Rule: End each task line with its oracle tag: `[oracle: <gate>]` (red first on that gate), `[oracle: <gate> characterization]` (green first) or `[oracle: none]` (no tests), where <gate> is a gate in .gates.yaml other than ci, live-check, eval and confirm.

Keep this rule if your plans declare each task's oracle (the `task-oracle` adoption
item); delete it otherwise. `gates conventions sync` projects it into
`openspec/config.yaml`'s `rules.tasks`, so `/opsx:propose` writes the tags, and the
test author, the handoff and the commit lock then hold each task to its tag.
