# Proposal: expand-brace-globs

## Why

Issue #1, independently reconfirmed during the `harden-unattended-loop` run: the
shim's matcher is plain `fnmatch`, which does not expand `{a,b}` alternation, so a
`match: "{bin,tests}/**"` surface selects **nothing** — silently. This repo's own
`.gates.yaml` uses brace globs on both its surfaces, meaning `gates surfaces` and
`gates rules` have been returning empty for every diff here: convention review runs
with an empty rule set and live-check selection selects nothing. That is an
under-selection, the one error direction the `gate-binding` spec forbids ("Surface
matching may only err hot"), and its silence is a `fail-loud-gates` violation. The
same trap awaits any adopter who writes a brace glob, and nothing warns them.

## What Changes

- **The matcher expands brace alternation.** `{a,b}` in a `match` pattern SHALL be
  pre-expanded into its alternatives before `fnmatch`, including nested and multiple
  groups, stdlib-only (`zero-dep-shim`).
- **`gates validate` fails loud on brace patterns it cannot honor.** Unbalanced or
  otherwise unexpandable `{` in a `match` pattern SHALL be a validation error naming
  the surface and the pattern — never a pattern that silently matches nothing.
- **This repo's own manifest is the regression fixture.** The two brace-glob surfaces
  in `.gates.yaml` stay as written and gain tests proving they now select.

## Capabilities

### New Capabilities

<!-- None. -->

### Modified Capabilities

- `gate-binding`: surface matching honors brace alternation, and a `match` pattern the
  matcher cannot honor is a loud validation error instead of a silent empty selection.

## Impact

- `bin/gates`: a brace pre-expansion step in `_matches` (or just before it) and a
  validation rule; both pure stdlib.
- `tests/`: expansion unit tests (single, multiple, nested, unbalanced groups) and a
  selection test against this repo's own `.gates.yaml` shapes.
- No manifest schema change: `schema/gates.schema.json` already types `match` as a
  string; the semantics tighten, no shape changes.
- Adopter impact: previously-dead brace patterns start selecting surfaces — strictly
  in the "err hot" direction the spec already pins.
