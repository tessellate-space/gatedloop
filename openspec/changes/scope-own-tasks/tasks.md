# Tasks

## 1. Leave the change's own tasks.md out of the scope (D1–D4)

- [x] 1.1 Add `_scope_paths(root, changed)`, which drops `openspec/changes/<change>/tasks.md` for the change `_resolve_change_name(root, None)` returns, and apply it to the `ci` staged diff before `_select_scoped_gate` and the unmatched-path announcement. Verify with tests: on a change branch, a staged diff of one scoped surface's file plus the change's own `tasks.md` runs the scoped `ci`, both with no surface covering `openspec/**` and with `openspec/**` in a surface of its own; another change's `tasks.md` beside the same file still runs the global `ci` and is named as unmatched; on `main` the same diff runs the global `ci`; a diff of only the change's `tasks.md` runs the global `ci` [oracle: unit]
- [x] 1.2 Apply the same filter to `unit`'s working set before scope selection and `_unit_union`. Verify with tests: a working set of one scoped surface's file plus the change's own `tasks.md` runs that surface's `unit`; two scoped surfaces plus the `tasks.md` run the union of exactly those two; `gates surfaces` still lists the surface covering `openspec/**` for the same diff [oracle: unit]

## 2. Docs (D5)

- [ ] 2.1 Replace the wrong remedy in SETUP.md "Scoped `ci`/`unit`" with the rule (the current change's `tasks.md` is not counted; another change's is). Verify that `scripts/release docs` reports no gap [oracle: none]

## Workflow follow-up

- Open the implementation PR with "Fixes #122".
